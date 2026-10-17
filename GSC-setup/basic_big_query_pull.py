"""Download Search Console BigQuery exports to the same gsc.db."""
import datetime as dt
import sqlite3
from google.cloud import bigquery
from google.oauth2 import service_account

# --- Change these settings ---
PROJECT = "your-project-id"
DATASET = "searchconsole"
START_DATE = "2026-01-01"
DB_FILE = "gsc.db"
REFRESH_DAYS = 7

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

# BigQuery supplies zero-based position sums; +1 gives GSC average position.
SQL = {
    "gsc": """
        SELECT CAST(data_date AS STRING) AS date, COALESCE(site_url,'') AS site_url,
               COALESCE(query,'') AS query, COALESCE(url,'') AS page,
               COALESCE(country,'') AS country, COALESCE(device,'') AS device,
               CASE LOWER(search_type) WHEN 'googlenews' THEN 'googleNews'
                    ELSE LOWER(search_type) END AS search_type,
               CAST(COALESCE(is_anonymized_query,FALSE) AS INT64) AS is_anonymized_query,
               CAST(COALESCE(is_anonymized_discover,FALSE) AS INT64) AS is_anonymized_discover,
               SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               SAFE_DIVIDE(SUM(clicks),SUM(impressions)) AS ctr,
               SAFE_DIVIDE(SUM(sum_position),SUM(impressions))+1 AS position,
               SUM(sum_position) AS position_sum
        FROM `{project}.{dataset}.searchdata_url_impression`
        WHERE data_date=@day
        GROUP BY 1,2,3,4,5,6,7,8,9
    """,
    "gsc_site": """
        SELECT CAST(data_date AS STRING) AS date, COALESCE(site_url,'') AS site_url,
               COALESCE(query,'') AS query, COALESCE(country,'') AS country,
               COALESCE(device,'') AS device,
               CASE LOWER(search_type) WHEN 'googlenews' THEN 'googleNews'
                    ELSE LOWER(search_type) END AS search_type,
               CAST(COALESCE(is_anonymized_query,FALSE) AS INT64) AS is_anonymized_query,
               SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               SAFE_DIVIDE(SUM(clicks),SUM(impressions)) AS ctr,
               SAFE_DIVIDE(SUM(sum_top_position),SUM(impressions))+1 AS position,
               SUM(sum_top_position) AS position_sum
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
    start = dt.date.fromisoformat(START_DATE)
    end = dt.date.today() - dt.timedelta(days=3)

    with sqlite3.connect(DB_FILE) as db:
        db.executescript(SCHEMA)
        log_query = f"""
            SELECT DISTINCT CAST(data_date AS STRING) AS date, namespace
            FROM `{PROJECT}.{DATASET}.ExportLog`
            WHERE data_date BETWEEN @start AND @end
              AND namespace IN ('searchdata_url_impression', 'searchdata_site_impression')
        """
        log_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("start", "DATE", START_DATE),
            bigquery.ScalarQueryParameter("end", "DATE", end.isoformat()),
        ])
        published = client.query(log_query, job_config=log_config).result()
        available = {"gsc": set(), "gsc_site": set()}
        for row in published:
            table = ("gsc" if row["namespace"] == "searchdata_url_impression"
                     else "gsc_site")
            available[table].add(row["date"])

        for table in ("gsc", "gsc_site"):
            query = SQL[table].format(project=PROJECT, dataset=DATASET)
            for day in sorted(available[table]):
                # Existing BigQuery rows older than refresh window can be reused.
                recent = dt.date.fromisoformat(day) >= end - dt.timedelta(days=REFRESH_DAYS - 1)
                if not recent and db.execute(
                    f"SELECT 1 FROM {table} WHERE date=? AND is_anonymized_query IN (0,1) LIMIT 1",
                    (day,),
                ).fetchone():
                    continue

                # Fresh staging schema for this table (URL and site widths differ).
                db.execute("DROP TABLE IF EXISTS temp.staging")
                db.execute(f"CREATE TEMP TABLE staging AS SELECT * FROM {table} WHERE 0")
                count = 0
                try:
                    for row in client.query(query, job_config=date_parameter(day)).result(page_size=1000):
                        values = tuple(row[key] for key in row.keys())
                        markers = ",".join("?" for _ in values)
                        db.execute(f"INSERT INTO staging VALUES ({markers})", values)
                        count += 1

                    # Replace only the properties present in the export.
                    # All changes to permanent tables commit together.
                    coverage = db.execute("SELECT DISTINCT site_url, search_type FROM staging").fetchall()
                    for site, kind in coverage:
                        db.execute(
                            f"DELETE FROM {table} WHERE date=? AND site_url=? AND search_type=?",
                            (day, site, kind),
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
