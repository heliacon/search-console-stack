"""Download Search Console performance to gsc.db (API version)."""
import datetime as dt
import os
import sqlite3
from googleapiclient.discovery import build

# --- Change these settings ---
SITE_URL = "sc-domain:example.com"
START_DATE = "2026-01-01"
DB_FILE = "gsc.db"
AUTH_METHOD = "service_account"  # or "oauth"
REFRESH_DAYS = 7
SEARCH_TYPES = ("web", "image", "video", "news", "discover", "googleNews")

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
SCHEMA = """
CREATE TABLE IF NOT EXISTS gsc (
    date TEXT, site_url TEXT, query TEXT, page TEXT, country TEXT, device TEXT,
    search_type TEXT, is_anonymized_query INTEGER, is_anonymized_discover INTEGER,
    clicks INTEGER, impressions INTEGER, ctr REAL, position REAL, position_sum REAL,
    PRIMARY KEY (date, site_url, query, page, country, device, search_type,
                 is_anonymized_query, is_anonymized_discover)
);
CREATE TABLE IF NOT EXISTS gsc_site (
    date TEXT, site_url TEXT, query TEXT, country TEXT, device TEXT,
    search_type TEXT, is_anonymized_query INTEGER,
    clicks INTEGER, impressions INTEGER, ctr REAL, position REAL, position_sum REAL,
    PRIMARY KEY (date, site_url, query, country, device, search_type,
                 is_anonymized_query)
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
    else:
        raise ValueError("AUTH_METHOD must be 'service_account' or 'oauth'")
    return build("searchconsole", "v1", credentials=credentials)


def download_day(client, day, kind, level):
    # Discover and Google News do not provide search queries.
    if level == "url":
        dimensions = (["page", "country", "device"] if kind in ("discover", "googleNews")
                      else ["query", "page", "country", "device"])
    else:
        dimensions = ["query", "country", "device"]

    results = []
    offset = 0
    while True:
        response = client.searchanalytics().query(
            siteUrl=SITE_URL,
            body={
                "startDate": day, "endDate": day,
                "dimensions": dimensions, "type": kind,
                "aggregationType": "byPage" if level == "url" else "byProperty",
                "rowLimit": 25000, "startRow": offset,
            },
        ).execute()
        rows = response.get("rows", [])
        for row in rows:
            keys = dict(zip(dimensions, row["keys"]))
            impressions = int(row["impressions"])
            position = row.get("position")
            metrics = (
                int(row["clicks"]), impressions, row.get("ctr"), position,
                (position - 1) * impressions if position is not None else None,
            )
            if level == "url":
                results.append((
                    day, SITE_URL, keys.get("query", ""), keys.get("page", ""),
                    keys.get("country", ""), keys.get("device", ""),
                    kind, -1, -1, *metrics,
                ))
            else:
                results.append((
                    day, SITE_URL, keys.get("query", ""),
                    keys.get("country", ""), keys.get("device", ""),
                    kind, -1, *metrics,
                ))
        if len(rows) < 25000:
            break
        offset += len(rows)
    return results


def main():
    client = connect_google()
    start = dt.date.fromisoformat(START_DATE)
    end = dt.date.today() - dt.timedelta(days=3)

    with sqlite3.connect(DB_FILE) as db:
        db.executescript(SCHEMA)
        for table, kinds in (
            ("gsc", SEARCH_TYPES),
            ("gsc_site", ("web", "image", "video", "news")),
        ):
            level = "url" if table == "gsc" else "site"
            for kind in kinds:
                latest = db.execute(
                    f"""SELECT MAX(date) FROM {table}
                        WHERE site_url=? AND search_type=? AND is_anonymized_query=-1""",
                    (SITE_URL, kind),
                ).fetchone()[0]
                refresh = (max(start, dt.date.fromisoformat(latest) -
                               dt.timedelta(days=REFRESH_DAYS - 1)) if latest else start)

                for ordinal in range(start.toordinal(), end.toordinal() + 1):
                    current = dt.date.fromordinal(ordinal)
                    day = current.isoformat()

                    # Preserve BigQuery rows when both scripts share gsc.db.
                    if db.execute(
                        f"""SELECT 1 FROM {table} WHERE date=? AND site_url=?
                            AND search_type=? AND is_anonymized_query IN (0,1) LIMIT 1""",
                        (day, SITE_URL, kind),
                    ).fetchone():
                        continue
                    if current < refresh and db.execute(
                        f"""SELECT 1 FROM {table} WHERE date=? AND site_url=?
                            AND search_type=? AND is_anonymized_query=-1 LIMIT 1""",
                        (day, SITE_URL, kind),
                    ).fetchone():
                        continue

                    records = download_day(client, day, kind, level)
                    with db:  # Fetch first; never delete existing data on failed fetch.
                        db.execute(
                            f"""DELETE FROM {table} WHERE date=? AND site_url=?
                                AND search_type=? AND is_anonymized_query=-1""",
                            (day, SITE_URL, kind),
                        )
                        if records:
                            markers = ",".join("?" for _ in records[0])
                            db.executemany(f"INSERT INTO {table} VALUES ({markers})", records)
                    print(f"{day} {kind} {level}: {len(records)} rows")
    print("Done:", DB_FILE)


if __name__ == "__main__":
    main()
