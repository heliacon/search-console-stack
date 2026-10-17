"""Download Search Console data into a local copy of the BigQuery bulk export.

This script uses the Search Analytics API. It writes the same table names and
column names as the BigQuery bulk export. So the queries in the queries folder
operate on this local copy and on the export. Only the table prefix is different.

Use this script to get about 16 months of history. Then run
basic_big_query_pull.py each day. The two scripts write the same tables. For
each day, the last script to write wins. So BigQuery becomes the data source
after its export is available, because you continue to run it.

Limitations of the API as a data source (the per-query reports are not affected):
  - The API gives an average position with rounding. This script calculates
    sum_position as (position - 1) * impressions. This value is an approximation.
  - The API does not supply the anonymised queries when you ask for the query
    dimension. So the site totals and the page totals from this source are a
    little low until BigQuery writes the day again.
  - This script does not write DISCOVER or GOOGLE_NEWS rows to the site table,
    because those surfaces have no query dimension at property level. BigQuery
    adds them later. So site_search_type_breakdown.sql shows no DISCOVER or
    GOOGLE_NEWS rows until the export writes the day.
"""
import datetime as dt
import os
import sqlite3
from googleapiclient.discovery import build

# --- Change these settings ---
SITE_URL = "sc-domain:example.com"
START_DATE = "2025-01-01"
END_DATE = ""              # optional "YYYY-MM-DD" to limit the backfill; "" = up to today-3
DB_FILE = "gsc.db"
AUTH_METHOD = "service_account"  # or "oauth"
REFRESH_DAYS = 7
SEARCH_TYPES = ("web", "image", "video", "news", "discover", "googleNews")

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# The API uses camelCase search types. The export uses these names.
SEARCH_TYPE_NATIVE = {
    "web": "WEB", "image": "IMAGE", "video": "VIDEO", "news": "NEWS",
    "discover": "DISCOVER", "googleNews": "GOOGLE_NEWS",
}

# These are the core columns of the BigQuery bulk export.
# SQLite does not have a DATE type or a BOOL type. So data_date is TEXT in ISO
# format, and the is_anonymized_* flags are INTEGER values 0 or 1.
# The export also has about 30 search-appearance (is_*) columns. This copy does
# not keep them.
SCHEMA = """
CREATE TABLE IF NOT EXISTS searchdata_url_impression (
    data_date TEXT, site_url TEXT, url TEXT, query TEXT,
    is_anonymized_query INTEGER, is_anonymized_discover INTEGER,
    country TEXT, search_type TEXT, device TEXT,
    impressions INTEGER, clicks INTEGER, sum_position REAL,
    PRIMARY KEY (data_date, site_url, url, query, country, device,
                 search_type, is_anonymized_query, is_anonymized_discover)
);
CREATE TABLE IF NOT EXISTS searchdata_site_impression (
    data_date TEXT, site_url TEXT, query TEXT,
    is_anonymized_query INTEGER,
    country TEXT, search_type TEXT, device TEXT,
    impressions INTEGER, clicks INTEGER, sum_top_position REAL,
    PRIMARY KEY (data_date, site_url, query, country, device,
                 search_type, is_anonymized_query)
);
"""


def connect_google():
    if AUTH_METHOD == "service_account":
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(
            "service_account.json", scopes=SCOPES
        )
    elif AUTH_METHOD == "oauth":
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow

        credentials = (Credentials.from_authorized_user_file("token.json", SCOPES)
                       if os.path.exists("token.json") else None)
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                credentials = InstalledAppFlow.from_client_secrets_file(
                    "client_secret.json", SCOPES
                ).run_local_server(port=0)
            with open("token.json", "w") as f:
                f.write(credentials.to_json())
            os.chmod("token.json", 0o600)
    else:
        raise ValueError("AUTH_METHOD must be 'service_account' or 'oauth'")
    return build("searchconsole", "v1", credentials=credentials)


def download_day(client, day, api_search_type, level):
    # Discover and Google News do not give search queries.
    if level == "url":
        dimensions = (["page", "country", "device"] if api_search_type in ("discover", "googleNews")
                      else ["query", "page", "country", "device"])
    else:
        dimensions = ["query", "country", "device"]

    native_type = SEARCH_TYPE_NATIVE[api_search_type]
    results = []
    offset = 0
    while True:
        response = client.searchanalytics().query(
            siteUrl=SITE_URL,
            body={
                "startDate": day, "endDate": day,
                "dimensions": dimensions, "type": api_search_type,
                "aggregationType": "byPage" if level == "url" else "byProperty",
                "rowLimit": 25000, "startRow": offset, "dataState": "final",
            },
        ).execute()
        rows = response.get("rows", [])
        for row in rows:
            keys = dict(zip(dimensions, row["keys"]))
            impressions = int(row["impressions"])
            position = row.get("position")
            # The API gives an average position with rounding. The export gives
            # the sum of the zero-based position. Calculate the sum again, so the
            # column agrees with the export.
            position_sum = (position - 1) * impressions if position is not None else None
            if level == "url":
                results.append((
                    day, SITE_URL, keys.get("page", ""), keys.get("query", ""),
                    0, 0, keys.get("country", ""), native_type,
                    keys.get("device", ""),
                    impressions, int(row["clicks"]), position_sum,
                ))
            else:
                results.append((
                    day, SITE_URL, keys.get("query", ""),
                    0, keys.get("country", ""), native_type,
                    keys.get("device", ""),
                    impressions, int(row["clicks"]), position_sum,
                ))
        if len(rows) < 25000:
            break
        offset += len(rows)
    return results


def main():
    client = connect_google()
    start = dt.date.fromisoformat(START_DATE)
    end = dt.date.today() - dt.timedelta(days=3)
    if END_DATE:
        end = min(end, dt.date.fromisoformat(END_DATE))

    with sqlite3.connect(DB_FILE) as db:
        db.executescript(SCHEMA)
        for table, api_search_types in (
            ("searchdata_url_impression", SEARCH_TYPES),
            ("searchdata_site_impression", ("web", "image", "video", "news")),
        ):
            level = "url" if table == "searchdata_url_impression" else "site"
            for api_search_type in api_search_types:
                native_type = SEARCH_TYPE_NATIVE[api_search_type]
                latest = db.execute(
                    f"SELECT MAX(data_date) FROM {table} "
                    f"WHERE site_url=? AND search_type=?",
                    (SITE_URL, native_type),
                ).fetchone()[0]
                refresh = (max(start, dt.date.fromisoformat(latest) -
                               dt.timedelta(days=REFRESH_DAYS - 1)) if latest else start)

                for ordinal in range(start.toordinal(), end.toordinal() + 1):
                    current_day = dt.date.fromordinal(ordinal)
                    day = current_day.isoformat()

                    # The day is before the refresh window and is already in the
                    # database. Keep it.
                    if current_day < refresh and db.execute(
                        f"SELECT 1 FROM {table} WHERE data_date=? AND site_url=? "
                        f"AND search_type=? LIMIT 1",
                        (day, SITE_URL, native_type),
                    ).fetchone():
                        continue

                    records = download_day(client, day, api_search_type, level)
                    # Get the data first. Do not delete the stored data if the
                    # fetch fails.
                    with db:
                        db.execute(
                            f"DELETE FROM {table} WHERE data_date=? AND site_url=? "
                            f"AND search_type=?",
                            (day, SITE_URL, native_type),
                        )
                        if records:
                            placeholders = ",".join("?" for _ in records[0])
                            db.executemany(f"INSERT INTO {table} VALUES ({placeholders})", records)
                    print(f"{day} {native_type} {level}: {len(records)} rows")
    print("Done:", DB_FILE)


if __name__ == "__main__":
    main()
