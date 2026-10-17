-- Discover and Google News performance by page.
-- These surfaces have no query dimension, so the breakdown is page-level only.
SELECT url, search_type,
       SUM(clicks) AS clicks,
       SUM(impressions) AS impressions,
       ROUND(1.0*SUM(clicks)/NULLIF(SUM(impressions),0), 4) AS ctr
FROM searchdata_url_impression
WHERE site_url = 'sc-domain:example.com'
  AND data_date BETWEEN '2026-09-01' AND '2026-09-30'
  AND search_type IN ('DISCOVER', 'GOOGLE_NEWS')
GROUP BY url, search_type
ORDER BY clicks DESC
LIMIT 100;
