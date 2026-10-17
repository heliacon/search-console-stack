-- Count of queries, and their clicks and impressions, grouped into ranking bands.
SELECT CASE
         WHEN avg_position <= 3  THEN '1 top 3'
         WHEN avg_position <= 10 THEN '2 page one (4-10)'
         WHEN avg_position <= 20 THEN '3 page two (11-20)'
         ELSE '4 beyond (21+)'
       END AS bucket,
       COUNT(*) AS queries,
       SUM(clicks) AS clicks,
       SUM(impressions) AS impressions
FROM (
  -- Average position per query first, then bucket those per-query averages.
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
