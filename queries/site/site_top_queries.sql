-- The top queries by clicks for a property.
-- This query removes the anonymised-query rows. Each query is then a real text string.
-- As a result, the totals are a little less than the property total.
SELECT query,
       SUM(clicks) AS clicks,
       SUM(impressions) AS impressions,
       ROUND(1.0*SUM(clicks)/NULLIF(SUM(impressions),0), 4) AS ctr,
       ROUND(SUM(sum_top_position)/NULLIF(SUM(impressions),0)+1, 2) AS avg_position
FROM searchdata_site_impression
WHERE site_url = 'sc-domain:example.com'
  AND data_date BETWEEN '2026-09-01' AND '2026-09-30'
  AND search_type = 'WEB'
  AND is_anonymized_query = FALSE
GROUP BY query
ORDER BY clicks DESC
LIMIT 100;
