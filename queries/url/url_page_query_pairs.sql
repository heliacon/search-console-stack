-- The top page and query pairs by clicks.
-- This query shows which page gets the clicks for each query.
-- Edit the url pattern for your canonical host. This query removes the
-- anonymised-query rows.
SELECT url, query,
       SUM(clicks) AS clicks,
       SUM(impressions) AS impressions,
       ROUND(1.0*SUM(clicks)/NULLIF(SUM(impressions),0), 4) AS ctr,
       ROUND(SUM(sum_position)/NULLIF(SUM(impressions),0)+1, 2) AS avg_position
FROM searchdata_url_impression
WHERE site_url = 'sc-domain:example.com'
  AND data_date BETWEEN '2026-09-01' AND '2026-09-30'
  AND search_type = 'WEB'
  AND url LIKE 'https://example.com/blog/%'
  AND is_anonymized_query = FALSE
GROUP BY url, query
ORDER BY clicks DESC
LIMIT 100;
