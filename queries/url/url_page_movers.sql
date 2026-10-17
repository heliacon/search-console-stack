-- The pages with the largest change in clicks between two periods.
-- The result shows the increases and the decreases. Edit the two date ranges.
WITH current_period AS (
  SELECT url,
         SUM(clicks) AS clicks,
         SUM(impressions) AS impressions,
         SUM(sum_position)/NULLIF(SUM(impressions),0)+1 AS avg_position
  FROM searchdata_url_impression
  WHERE site_url = 'sc-domain:example.com'
    AND data_date BETWEEN '2026-09-01' AND '2026-09-30'
    AND search_type = 'WEB'
  GROUP BY url
),
previous_period AS (
  SELECT url,
         SUM(clicks) AS clicks,
         SUM(impressions) AS impressions,
         SUM(sum_position)/NULLIF(SUM(impressions),0)+1 AS avg_position
  FROM searchdata_url_impression
  WHERE site_url = 'sc-domain:example.com'
    AND data_date BETWEEN '2026-08-01' AND '2026-08-31'
    AND search_type = 'WEB'
  GROUP BY url
),
-- Two LEFT JOIN operations with a UNION make a full outer join.
-- The result includes the pages in one period or in both periods.
movers AS (
  SELECT COALESCE(current_period.url, previous_period.url) AS url,
         COALESCE(current_period.clicks, 0) AS clicks_now,
         COALESCE(previous_period.clicks, 0) AS clicks_prev,
         COALESCE(current_period.clicks, 0) - COALESCE(previous_period.clicks, 0) AS clicks_change,
         ROUND(current_period.avg_position, 2) AS position_now,
         ROUND(previous_period.avg_position, 2) AS position_prev
  FROM current_period LEFT JOIN previous_period ON previous_period.url = current_period.url
  UNION
  SELECT previous_period.url,
         COALESCE(current_period.clicks, 0),
         previous_period.clicks,
         COALESCE(current_period.clicks, 0) - previous_period.clicks,
         ROUND(current_period.avg_position, 2),
         ROUND(previous_period.avg_position, 2)
  FROM previous_period LEFT JOIN current_period ON current_period.url = previous_period.url
  WHERE current_period.url IS NULL
)
-- Order by the size of the change, so the largest rises and falls are at the top.
SELECT * FROM movers
ORDER BY ABS(clicks_change) DESC
LIMIT 100;
