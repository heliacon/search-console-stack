-- The yearly totals for a page or a folder.
-- The current year is not complete, so its totals are lower than a full year.
-- Edit the url pattern. For BigQuery, change strftime to FORMAT_DATE('%Y', data_date).
SELECT strftime('%Y', data_date) AS year,
       SUM(clicks) AS clicks,
       SUM(impressions) AS impressions,
       ROUND(1.0*SUM(clicks)/NULLIF(SUM(impressions),0), 4) AS ctr,
       ROUND(SUM(sum_position)/NULLIF(SUM(impressions),0)+1, 2) AS avg_position
FROM searchdata_url_impression
WHERE site_url = 'sc-domain:example.com'
  AND data_date BETWEEN '2024-01-01' AND '2026-09-30'
  AND search_type = 'WEB'
  AND url LIKE 'https://example.com/blog/%'
GROUP BY 1
ORDER BY 1;
