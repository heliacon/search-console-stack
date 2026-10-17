-- Weekly totals. On BigQuery, swap strftime for FORMAT_DATE('%Y-%W', data_date).
SELECT strftime('%Y-%W', data_date) AS year_week,
       MIN(data_date) AS week_start,
       SUM(clicks) AS clicks,
       SUM(impressions) AS impressions,
       ROUND(1.0*SUM(clicks)/NULLIF(SUM(impressions),0), 4) AS ctr,
       ROUND(SUM(sum_top_position)/NULLIF(SUM(impressions),0)+1, 2) AS avg_position
FROM searchdata_site_impression
WHERE site_url = 'sc-domain:example.com'
  AND data_date BETWEEN '2024-01-01' AND '2026-09-30'
  AND search_type = 'WEB'
GROUP BY 1
ORDER BY 1;
