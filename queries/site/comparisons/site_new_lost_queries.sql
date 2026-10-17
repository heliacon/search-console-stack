-- The new queries and the lost queries between two periods.
-- A new query has clicks now but no clicks before. A lost query is the opposite.
-- A lost query can be an early sign of content decay. Edit the two date ranges.
-- This query removes the anonymised-query rows.
WITH current_period AS (
  SELECT query, SUM(clicks) AS clicks
  FROM searchdata_site_impression
  WHERE site_url = 'sc-domain:example.com'
    AND data_date BETWEEN '2026-09-01' AND '2026-09-30'
    AND search_type = 'WEB'
    AND is_anonymized_query = FALSE
  GROUP BY query
),
previous_period AS (
  SELECT query, SUM(clicks) AS clicks
  FROM searchdata_site_impression
  WHERE site_url = 'sc-domain:example.com'
    AND data_date BETWEEN '2026-08-01' AND '2026-08-31'
    AND search_type = 'WEB'
    AND is_anonymized_query = FALSE
  GROUP BY query
)
-- A new query is in the current period only.
SELECT 'new' AS status,
       current_period.query,
       current_period.clicks AS clicks_now,
       0 AS clicks_prev
FROM current_period
LEFT JOIN previous_period ON previous_period.query = current_period.query
WHERE previous_period.query IS NULL AND current_period.clicks > 0
UNION ALL
-- A lost query is in the previous period only.
SELECT 'lost' AS status,
       previous_period.query,
       0 AS clicks_now,
       previous_period.clicks AS clicks_prev
FROM previous_period
LEFT JOIN current_period ON current_period.query = previous_period.query
WHERE current_period.query IS NULL AND previous_period.clicks > 0
ORDER BY status, clicks_prev DESC, clicks_now DESC
LIMIT 200;
