-- The totals for each search type (WEB, IMAGE, VIDEO, NEWS, DISCOVER, GOOGLE_NEWS).
-- This query has no search_type filter, so it counts all the surfaces.
-- Note: for DISCOVER and GOOGLE_NEWS, the avg_position value is not a search rank.
SELECT search_type,
       SUM(clicks) AS clicks,
       SUM(impressions) AS impressions,
       ROUND(1.0*SUM(clicks)/NULLIF(SUM(impressions),0), 4) AS ctr,
       ROUND(SUM(sum_top_position)/NULLIF(SUM(impressions),0)+1, 2) AS avg_position
FROM searchdata_site_impression
WHERE site_url = 'sc-domain:example.com'
  AND data_date BETWEEN '2026-09-01' AND '2026-09-30'
GROUP BY search_type
ORDER BY clicks DESC;
