-- The page and query pairs at position 11 to 20 with many impressions.
-- These pairs are close to page one. A small gain in rank can add clicks.
-- Edit the url pattern for your canonical host. This query removes the
-- anonymised-query rows.
SELECT url, query,
       SUM(impressions) AS impressions,
       SUM(clicks) AS clicks,
       ROUND(1.0*SUM(clicks)/NULLIF(SUM(impressions),0), 4) AS ctr,
       ROUND(SUM(sum_position)/NULLIF(SUM(impressions),0)+1, 2) AS avg_position
FROM searchdata_url_impression
WHERE site_url = 'sc-domain:example.com'
  AND data_date BETWEEN '2026-09-01' AND '2026-09-30'
  AND search_type = 'WEB'
  AND url LIKE 'https://example.com/blog/%'
  AND is_anonymized_query = FALSE
GROUP BY url, query
HAVING SUM(sum_position)/NULLIF(SUM(impressions),0)+1 BETWEEN 11 AND 20
   AND SUM(impressions) >= 50
ORDER BY SUM(impressions) DESC
LIMIT 100;
