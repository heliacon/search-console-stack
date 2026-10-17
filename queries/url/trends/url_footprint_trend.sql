-- The number of different queries and pages for each month.
-- A rising count shows more topic reach, often before the clicks increase.
-- This query removes the anonymised-query rows, so the query count is of real
-- query strings. For BigQuery, change strftime to FORMAT_DATE('%Y-%m', data_date).
SELECT strftime('%Y-%m', data_date) AS year_month,
       COUNT(DISTINCT query) AS queries,
       COUNT(DISTINCT url) AS pages,
       SUM(clicks) AS clicks,
       SUM(impressions) AS impressions
FROM searchdata_url_impression
WHERE site_url = 'sc-domain:example.com'
  AND data_date BETWEEN '2024-01-01' AND '2026-09-30'
  AND search_type = 'WEB'
  AND is_anonymized_query = FALSE
GROUP BY 1
ORDER BY 1;
