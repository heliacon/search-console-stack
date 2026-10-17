"""Examine a local gsc.db database and show a summary.

This script shows the row counts, the date range, and the headline totals for the
two tables. The script reads the database only. Run it after a pull to make sure
that the data is correct.

The script calculates the average position as SUM(position_sum)/SUM(impressions)
+ 1. It does not use AVG(position). The export stores the sum of the zero-based
position. So an average without weights would be wrong.
"""
import sqlite3

DB_FILE = "gsc.db"

TABLES = {
    "searchdata_site_impression": "sum_top_position",
    "searchdata_url_impression": "sum_position",
}


def main():
    db = sqlite3.connect(DB_FILE)
    db.row_factory = sqlite3.Row
    for table, position_col in TABLES.items():
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        print(f"\n=== {table} ===")
        if not exists:
            print("  (table not present)")
            continue

        totals = db.execute(
            f"""SELECT COUNT(*) AS rows,
                       MIN(data_date) AS first_day, MAX(data_date) AS last_day,
                       COUNT(DISTINCT data_date) AS days,
                       COUNT(DISTINCT site_url) AS properties,
                       SUM(clicks) AS clicks, SUM(impressions) AS impressions,
                       ROUND(SUM({position_col})/NULLIF(SUM(impressions),0)+1, 2) AS avg_position
                FROM {table}"""
        ).fetchone()
        if not totals["rows"]:
            print("  (no rows)")
            continue
        print(f"  rows        : {totals['rows']:,}")
        print(f"  date range  : {totals['first_day']} -> {totals['last_day']} "
              f"({totals['days']} days)")
        print(f"  properties  : {totals['properties']}")
        print(f"  clicks      : {totals['clicks']:,}")
        print(f"  impressions : {totals['impressions']:,}")
        print(f"  avg position: {totals['avg_position']}")

        print("  by search_type:")
        for row in db.execute(
            f"""SELECT search_type,
                       SUM(clicks) AS clicks, SUM(impressions) AS impressions
                FROM {table}
                GROUP BY search_type ORDER BY SUM(impressions) DESC"""
        ):
            print(f"    {row['search_type']:<12} "
                  f"clicks {row['clicks']:>12,}  impressions {row['impressions']:>14,}")

        anon_counts = db.execute(
            f"""SELECT is_anonymized_query AS flag, COUNT(*) AS rows
                FROM {table} GROUP BY is_anonymized_query ORDER BY is_anonymized_query"""
        ).fetchall()
        print("  anonymised-query rows: "
              + ", ".join(f"flag={entry['flag']}:{entry['rows']:,}" for entry in anon_counts))

    db.close()


if __name__ == "__main__":
    main()
