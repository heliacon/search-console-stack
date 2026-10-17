"""Sanity-check a local gsc.db mirror: row counts, date coverage and headline
totals for both native tables. Read-only; run it after a pull to confirm the
data landed and the numbers look sane.

Weighted average position is SUM(position_sum)/SUM(impressions)+1, never
AVG(position): the export stores a summed zero-based position, so an unweighted
average would be wrong.
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
