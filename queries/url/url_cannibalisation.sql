-- The pages that compete for the same query (cannibalisation).
-- For each query that has more than one page, this query lists every page.
-- Two or more pages for one query can divide the ranking. This query removes the
-- anonymised-query rows.
WITH page_query AS (
  SELECT query, url,
         SUM(clicks) AS clicks,
         SUM(impressions) AS impressions,
         SUM(sum_position)/NULLIF(SUM(impressions),0)+1 AS avg_position
  FROM searchdata_url_impression
  WHERE site_url = 'sc-domain:example.com'
    AND data_date BETWEEN '2026-09-01' AND '2026-09-30'
    AND search_type = 'WEB'
    AND is_anonymized_query = FALSE
  GROUP BY query, url
),
cannibalised AS (
  -- Keep the queries that have more than one page and enough impressions.
  SELECT query
  FROM page_query
  GROUP BY query
  HAVING COUNT(*) > 1 AND SUM(impressions) >= 100
)
SELECT page_query.query,
       page_query.url,
       page_query.clicks,
       page_query.impressions,
       ROUND(page_query.avg_position, 2) AS avg_position
FROM page_query
JOIN cannibalised ON cannibalised.query = page_query.query
ORDER BY page_query.query, page_query.impressions DESC
LIMIT 200;
