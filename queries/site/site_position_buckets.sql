-- The count of queries and their clicks and impressions, in ranking bands.
SELECT CASE
         WHEN avg_position <= 3  THEN '1 (3 or less)'
         WHEN avg_position <= 10 THEN '2 (more than 3, up to 10)'
         WHEN avg_position <= 20 THEN '3 (more than 10, up to 20)'
         ELSE '4 (more than 20)'
       END AS bucket,
       COUNT(*) AS queries,
       SUM(clicks) AS clicks,
       SUM(impressions) AS impressions
FROM (
  -- First calculate the average position for each query.
  -- Then put those averages into bands.
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
)
GROUP BY bucket
ORDER BY bucket;
