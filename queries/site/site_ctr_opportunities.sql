-- Queries with high impressions and a page-one or page-two position but low CTR.
SELECT query,
       SUM(impressions) AS impressions,
       SUM(clicks) AS clicks,
       ROUND(1.0*SUM(clicks)/NULLIF(SUM(impressions),0), 4) AS ctr,
       ROUND(SUM(sum_top_position)/NULLIF(SUM(impressions),0)+1, 2) AS avg_position
FROM searchdata_site_impression
WHERE site_url = 'sc-domain:example.com'
  AND data_date BETWEEN '2026-09-01' AND '2026-09-30'
  AND search_type = 'WEB'
  AND is_anonymized_query = FALSE
GROUP BY query
-- Filter on the aggregate expressions, not the output aliases: a bare column
-- name in HAVING binds to the base column rather than the SUM and misfires.
HAVING SUM(impressions) >= 100
   AND SUM(sum_top_position)/NULLIF(SUM(impressions),0)+1 BETWEEN 3 AND 20
   AND 1.0*SUM(clicks)/NULLIF(SUM(impressions),0) < 0.05
ORDER BY SUM(impressions) DESC
LIMIT 100;
