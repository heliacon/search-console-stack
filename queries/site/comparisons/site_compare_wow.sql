-- The week-over-week totals: the current period and the previous period.
-- This query keeps all rows. Edit the two date ranges.
WITH current_period AS (
  SELECT SUM(clicks) AS clicks,
         SUM(impressions) AS impressions,
         SUM(sum_top_position) AS position_sum
  FROM searchdata_site_impression
  WHERE site_url = 'sc-domain:example.com'
    AND data_date BETWEEN '2026-09-23' AND '2026-09-29'
    AND search_type = 'WEB'
),
previous_period AS (
  SELECT SUM(clicks) AS clicks,
         SUM(impressions) AS impressions,
         SUM(sum_top_position) AS position_sum
  FROM searchdata_site_impression
  WHERE site_url = 'sc-domain:example.com'
    AND data_date BETWEEN '2026-09-16' AND '2026-09-22'
    AND search_type = 'WEB'
)
SELECT current_period.clicks AS clicks_now,
       previous_period.clicks AS clicks_prev,
       current_period.clicks - previous_period.clicks AS clicks_change,
       ROUND(100.0*(current_period.clicks - previous_period.clicks)/NULLIF(previous_period.clicks,0), 1) AS clicks_pct,
       current_period.impressions AS impressions_now,
       previous_period.impressions AS impressions_prev,
       ROUND(100.0*(current_period.impressions - previous_period.impressions)/NULLIF(previous_period.impressions,0), 1) AS impressions_pct,
       ROUND(current_period.position_sum/NULLIF(current_period.impressions,0)+1, 2) AS position_now,
       ROUND(previous_period.position_sum/NULLIF(previous_period.impressions,0)+1, 2) AS position_prev
FROM current_period, previous_period;
