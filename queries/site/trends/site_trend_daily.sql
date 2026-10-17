-- Daily totals with a 7-day moving average of clicks.
-- The moving average uses ROWS 6 PRECEDING, which assumes one row per day; the
-- GROUP BY data_date guarantees that.
SELECT data_date,
       SUM(clicks) AS clicks,
       SUM(impressions) AS impressions,
       ROUND(AVG(SUM(clicks)) OVER (ORDER BY data_date
             ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1) AS clicks_7day_avg
FROM searchdata_site_impression
WHERE site_url = 'sc-domain:example.com'
  AND data_date BETWEEN '2024-01-01' AND '2026-09-30'
  AND search_type = 'WEB'
GROUP BY data_date
ORDER BY data_date;
