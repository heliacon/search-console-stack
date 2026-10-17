"""Copy the Search Console BigQuery bulk export into a local SQLite mirror that
keeps the export's own table and column names.

The canned queries in ../queries target those native names, so they run
unchanged here and against the live export in BigQuery: only the table prefix
differs (`project.dataset.searchdata_url_impression` vs the local table). Run
this daily. If you backfilled history with basic_gsc_pull.py first, this
overwrites each day as its export lands (last-writer-wins per day), replacing
the API's approximate figures with the authoritative export.

The raw export carries ~30 volatile search-appearance (is_*) columns; those are
summed away here so each day aggregates to the core-column schema below.
"""
import datetime as dt
import sqlite3
from google.cloud import bigquery
from google.oauth2 import service_account

# --- Change these settings ---
PROJECT = "your-project-id"
DATASET = "searchconsole"
START_DATE = "2025-01-01"
END_DATE = ""              # optional "YYYY-MM-DD" to cap the range; "" = up to today-3
DB_FILE = "gsc.db"
REFRESH_DAYS = 7

# SQLite has no DATE or BOOL: data_date is TEXT (ISO), the is_anonymized_* flags
# are INTEGER 0/1. search_type is stored exactly as the export gives it (upper
# case: WEB, IMAGE, VIDEO, NEWS, DISCOVER, GOOGLE_NEWS).
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

# Select the core columns in the exact order of the local schema, summing over
# the appearance columns. The URL table carries sum_position; the site table
# carries sum_top_position (Google's own naming inconsistency, preserved).
SQL = {
    "searchdata_url_impression": """
        SELECT CAST(data_date AS STRING) AS data_date,
               COALESCE(site_url,'') AS site_url, COALESCE(url,'') AS url,
               COALESCE(query,'') AS query,
               CAST(COALESCE(is_anonymized_query,FALSE) AS INT64) AS is_anonymized_query,
               CAST(COALESCE(is_anonymized_discover,FALSE) AS INT64) AS is_anonymized_discover,
               COALESCE(country,'') AS country,
               COALESCE(search_type,'') AS search_type,
               COALESCE(device,'') AS device,
               SUM(impressions) AS impressions, SUM(clicks) AS clicks,
               SUM(sum_position) AS sum_position
        FROM `{project}.{dataset}.searchdata_url_impression`
        WHERE data_date=@day
        GROUP BY 1,2,3,4,5,6,7,8,9
    """,
    "searchdata_site_impression": """
        SELECT CAST(data_date AS STRING) AS data_date,
               COALESCE(site_url,'') AS site_url, COALESCE(query,'') AS query,
               CAST(COALESCE(is_anonymized_query,FALSE) AS INT64) AS is_anonymized_query,
               COALESCE(country,'') AS country,
               COALESCE(search_type,'') AS search_type,
               COALESCE(device,'') AS device,
               SUM(impressions) AS impressions, SUM(clicks) AS clicks,
               SUM(sum_top_position) AS sum_top_position
        FROM `{project}.{dataset}.searchdata_site_impression`
        WHERE data_date=@day
        GROUP BY 1,2,3,4,5,6,7
    """,
}


def date_parameter(day):
    return bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("day", "DATE", day)
    ])


def main():
    credentials = service_account.Credentials.from_service_account_file(
        "service_account.json"
    )
    client = bigquery.Client(project=PROJECT, credentials=credentials)
    end = dt.date.today() - dt.timedelta(days=3)
    if END_DATE:
        end = min(end, dt.date.fromisoformat(END_DATE))

    with sqlite3.connect(DB_FILE) as db:
        db.executescript(SCHEMA)
        # ExportLog records which day each namespace actually published, so we
        # only query days that exist and never re-query a gap.
        log_query = f"""
            SELECT DISTINCT CAST(data_date AS STRING) AS data_date, namespace
            FROM `{PROJECT}.{DATASET}.ExportLog`
            WHERE data_date BETWEEN @start AND @end
              AND namespace IN ('searchdata_url_impression', 'searchdata_site_impression')
        """
        log_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("start", "DATE", START_DATE),
            bigquery.ScalarQueryParameter("end", "DATE", end.isoformat()),
        ])
        published = client.query(log_query, job_config=log_config).result()
        available = {"searchdata_url_impression": set(),
                     "searchdata_site_impression": set()}
        for row in published:
            available[row["namespace"]].add(row["data_date"])

        for table in ("searchdata_url_impression", "searchdata_site_impression"):
            query = SQL[table].format(project=PROJECT, dataset=DATASET)
            for day in sorted(available[table]):
                # Days older than the refresh window that are already stored can
                # be left alone; recent days are always re-pulled.
                recent = dt.date.fromisoformat(day) >= end - dt.timedelta(days=REFRESH_DAYS - 1)
                if not recent and db.execute(
                    f"SELECT 1 FROM {table} WHERE data_date=? LIMIT 1",
                    (day,),
                ).fetchone():
                    continue

                # Stage in a temp table so a failed BigQuery query never removes
                # the previous day's SQLite data. URL and site widths differ, so
                # rebuild staging per table.
                db.execute("DROP TABLE IF EXISTS temp.staging")
                db.execute(f"CREATE TEMP TABLE staging AS SELECT * FROM {table} WHERE 0")
                count = 0
                try:
                    for row in client.query(query, job_config=date_parameter(day)).result(page_size=1000):
                        values = tuple(row[key] for key in row.keys())
                        placeholders = ",".join("?" for _ in values)
                        db.execute(f"INSERT INTO staging VALUES ({placeholders})", values)
                        count += 1

                    # Replace only the (property, search_type) slices present in
                    # this export; everything else in the db is left untouched.
                    coverage = db.execute(
                        "SELECT DISTINCT site_url, search_type FROM staging"
                    ).fetchall()
                    for site_url_value, search_type in coverage:
                        db.execute(
                            f"DELETE FROM {table} WHERE data_date=? AND site_url=? AND search_type=?",
                            (day, site_url_value, search_type),
                        )
                    db.execute(f"INSERT INTO {table} SELECT * FROM staging")
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.execute("DROP TABLE IF EXISTS temp.staging")
                print(f"{day} {table}: {count} rows")
    print("Done:", DB_FILE)


if __name__ == "__main__":
    main()
