-- Queries ranked by clicks change between two periods. Edit both date ranges.
WITH current_period AS (
  SELECT query,
         SUM(clicks) AS clicks,
         SUM(impressions) AS impressions,
         SUM(sum_top_position)/NULLIF(SUM(impressions),0)+1 AS avg_position
  FROM searchdata_site_impression
  WHERE site_url = 'sc-domain:example.com'
    AND data_date BETWEEN '2026-09-01' AND '2026-09-30'
    AND search_type = 'WEB'
    AND is_anonymized_query = FALSE
  GROUP BY query
),
previous_period AS (
  SELECT query,
         SUM(clicks) AS clicks,
         SUM(impressions) AS impressions,
         SUM(sum_top_position)/NULLIF(SUM(impressions),0)+1 AS avg_position
  FROM searchdata_site_impression
  WHERE site_url = 'sc-domain:example.com'
    AND data_date BETWEEN '2026-08-01' AND '2026-08-31'
    AND search_type = 'WEB'
    AND is_anonymized_query = FALSE
  GROUP BY query
)
-- Two LEFT JOINs union to a full outer join: queries present in either period.
SELECT COALESCE(current_period.query, previous_period.query) AS query,
       COALESCE(current_period.clicks, 0) AS clicks_now,
       COALESCE(previous_period.clicks, 0) AS clicks_prev,
       COALESCE(current_period.clicks, 0) - COALESCE(previous_period.clicks, 0) AS clicks_change,
       ROUND(current_period.avg_position, 2) AS position_now,
       ROUND(previous_period.avg_position, 2) AS position_prev
FROM current_period LEFT JOIN previous_period ON previous_period.query = current_period.query
UNION
SELECT previous_period.query,
       COALESCE(current_period.clicks, 0),
       previous_period.clicks,
       COALESCE(current_period.clicks, 0) - previous_period.clicks,
       ROUND(current_period.avg_position, 2),
       ROUND(previous_period.avg_position, 2)
FROM previous_period LEFT JOIN current_period ON current_period.query = previous_period.query
WHERE current_period.query IS NULL
ORDER BY clicks_change DESC
LIMIT 100;
