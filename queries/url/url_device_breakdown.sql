-- The totals for each device for a page or a folder.
-- Edit the url pattern for your canonical host.
SELECT device,
       SUM(clicks) AS clicks,
       SUM(impressions) AS impressions,
       ROUND(1.0*SUM(clicks)/NULLIF(SUM(impressions),0), 4) AS ctr,
       ROUND(SUM(sum_position)/NULLIF(SUM(impressions),0)+1, 2) AS avg_position
FROM searchdata_url_impression
WHERE site_url = 'sc-domain:example.com'
  AND data_date BETWEEN '2026-09-01' AND '2026-09-30'
  AND search_type = 'WEB'
  AND url LIKE 'https://example.com/blog/%'
GROUP BY device
ORDER BY clicks DESC;
