"""Copy the Search Console BigQuery bulk export into a local SQLite database.

The local database uses the same table names and column names as the export. So
the queries in the queries folder operate on the local database and on the
export in BigQuery. Only the table prefix is different. For BigQuery, use
project.dataset.searchdata_url_impression.

Run this script each day. If you use basic_gsc_pull.py first to get the history,
this script writes each day again when its export is available. For each day, the
last script to write wins. So BigQuery replaces the approximate API values with
the correct values from the export.

The export has about 30 search-appearance (is_*) columns. This script adds the
values of these columns together. Each day then agrees with the core-column
schema below.
"""
import datetime as dt
import sqlite3
from google.cloud import bigquery
from google.oauth2 import service_account

# --- Change these settings ---
PROJECT = "your-project-id"
DATASET = "searchconsole"
START_DATE = "2025-01-01"
END_DATE = ""              # optional "YYYY-MM-DD" to limit the range; "" = up to today-3
DB_FILE = "gsc.db"
REFRESH_DAYS = 7

# SQLite does not have a DATE type or a BOOL type. So data_date is TEXT in ISO
# format, and the is_anonymized_* flags are INTEGER values 0 or 1.
# search_type keeps the export's own case (WEB, IMAGE, VIDEO, NEWS, DISCOVER,
# GOOGLE_NEWS).
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

# Select the core columns in the same order as the local schema. Add the values
# together across the appearance columns. The URL table has the column
# sum_position. The site table has the column sum_top_position. This is Google's
# naming difference. This copy keeps it.
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
        # ExportLog shows the day that each namespace published. The script queries
        # only the days that exist. It does not query a gap again.
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
                # Exports for older days do not change, so do not query a stored
                # day again. Recent days can still change, so re-query them.
                recent = dt.date.fromisoformat(day) >= end - dt.timedelta(days=REFRESH_DAYS - 1)
                if not recent and db.execute(
                    f"SELECT 1 FROM {table} WHERE data_date=? LIMIT 1",
                    (day,),
                ).fetchone():
                    continue

                # Put the data in a temporary table first. If the BigQuery query
                # fails, the script does not remove the SQLite data from before.
                # The URL table and the site table have different widths. So make
                # the staging table again for each table.
                db.execute("DROP TABLE IF EXISTS temp.staging")
                db.execute(f"CREATE TEMP TABLE staging AS SELECT * FROM {table} WHERE 0")
                count = 0
                try:
                    for row in client.query(query, job_config=date_parameter(day)).result(page_size=1000):
                        values = tuple(row[key] for key in row.keys())
                        placeholders = ",".join("?" for _ in values)
                        db.execute(f"INSERT INTO staging VALUES ({placeholders})", values)
                        count += 1

                    # Replace the full day for each property in this export. The
                    # staging table holds every search type for the day, so a
                    # delete by day and property also removes a slice that dropped
                    # to zero. The script does not change the other properties or
                    # the other days.
                    properties = db.execute("SELECT DISTINCT site_url FROM staging").fetchall()
                    for (site_url_value,) in properties:
                        db.execute(
                            f"DELETE FROM {table} WHERE data_date=? AND site_url=?",
                            (day, site_url_value),
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
