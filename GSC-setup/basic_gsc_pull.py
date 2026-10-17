"""Download Search Console performance into a local mirror of the BigQuery
bulk export schema (Search Analytics API version).

This writes the same table and column names that Google's BigQuery bulk export
uses, so the canned queries in ../queries run unchanged here and against the
live export: only the table prefix differs. Use this to backfill ~16 months of
history up front, then run basic_big_query_pull.py daily going forward. Both
write the same tables and resolve to last-writer-wins per day, so the day you
keep running (BigQuery) quietly takes over as its exports land.

Caveats of the API as a source (per-query reports are unaffected):
  * position is a rounded average, so sum_position is reconstructed as
    (position - 1) * impressions and is approximate.
  * anonymised queries are omitted entirely when the query dimension is
    requested, so site/page totals built from this source run slightly low
    until BigQuery overwrites the day.
"""
import datetime as dt
import os
import sqlite3
from googleapiclient.discovery import build

# --- Change these settings ---
SITE_URL = "sc-domain:example.com"
START_DATE = "2025-01-01"
END_DATE = ""              # optional "YYYY-MM-DD" to cap the backfill; "" = up to today-3
DB_FILE = "gsc.db"
AUTH_METHOD = "service_account"  # or "oauth"
REFRESH_DAYS = 7
SEARCH_TYPES = ("web", "image", "video", "news", "discover", "googleNews")

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# The API uses camelCase search types; the export stores them like this.
SEARCH_TYPE_NATIVE = {
    "web": "WEB", "image": "IMAGE", "video": "VIDEO", "news": "NEWS",
    "discover": "DISCOVER", "googleNews": "GOOGLE_NEWS",
}

# Mirror of the BigQuery bulk export core columns. SQLite has no DATE or BOOL,
# so data_date is TEXT (ISO) and the is_anonymized_* flags are INTEGER 0/1.
# Google adds ~30 volatile search-appearance (is_*) columns to the export over
# time; those are not mirrored here.
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
    # Discover and Google News do not provide search queries.
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
            # The API gives a rounded average position; the export gives the
            # summed zero-based position. Rebuild the sum so the column matches.
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

                    # Older than the refresh window and already stored: leave it.
                    if current_day < refresh and db.execute(
                        f"SELECT 1 FROM {table} WHERE data_date=? AND site_url=? "
                        f"AND search_type=? LIMIT 1",
                        (day, SITE_URL, native_type),
                    ).fetchone():
                        continue

                    records = download_day(client, day, api_search_type, level)
                    with db:  # Fetch first; never delete existing data on a failed fetch.
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
