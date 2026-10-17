-- The new pages and the lost pages between two periods.
-- A new page has clicks now but no clicks before. A lost page is the opposite.
-- A lost page can be an early sign of a deindex or decay. Edit the two date ranges.
WITH current_period AS (
  SELECT url, SUM(clicks) AS clicks
  FROM searchdata_url_impression
  WHERE site_url = 'sc-domain:example.com'
    AND data_date BETWEEN '2026-09-01' AND '2026-09-30'
    AND search_type = 'WEB'
  GROUP BY url
),
previous_period AS (
  SELECT url, SUM(clicks) AS clicks
  FROM searchdata_url_impression
  WHERE site_url = 'sc-domain:example.com'
    AND data_date BETWEEN '2026-08-01' AND '2026-08-31'
    AND search_type = 'WEB'
  GROUP BY url
)
-- A new page is in the current period only.
SELECT 'new' AS status,
       current_period.url,
       current_period.clicks AS clicks_now,
       0 AS clicks_prev
FROM current_period
LEFT JOIN previous_period ON previous_period.url = current_period.url
WHERE previous_period.url IS NULL AND current_period.clicks > 0
UNION ALL
-- A lost page is in the previous period only.
SELECT 'lost' AS status,
       previous_period.url,
       0 AS clicks_now,
       previous_period.clicks AS clicks_prev
FROM previous_period
LEFT JOIN current_period ON current_period.url = previous_period.url
WHERE current_period.url IS NULL AND previous_period.clicks > 0
ORDER BY status, clicks_prev DESC, clicks_now DESC
LIMIT 200;
