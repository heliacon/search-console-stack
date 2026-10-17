-- The queries that have many impressions and a low CTR on page one.
-- For queries at position 11 to 20, use site_striking_distance.sql instead.
-- This query removes the anonymised-query rows.
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
-- Use the aggregate expressions in the HAVING clause, not the output aliases.
-- A column name alone in a HAVING clause points to the base column, not to the
-- SUM. Then the filter does not operate correctly.
HAVING SUM(impressions) >= 100
   AND SUM(sum_top_position)/NULLIF(SUM(impressions),0)+1 <= 10
   AND 1.0*SUM(clicks)/NULLIF(SUM(impressions),0) < 0.05
ORDER BY SUM(impressions) DESC
LIMIT 100;
