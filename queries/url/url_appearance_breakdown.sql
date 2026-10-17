-- The impressions and clicks for each search appearance (rich-result type).
--
-- Run this query on the BigQuery export only. The local SQLite copy and the
-- Search Analytics API do not keep the is_* search-appearance columns, so this
-- query does not run against the mirror.
--
-- One impression can have more than one appearance, so the totals can overlap.
-- Do not add the appearance totals together to get a grand total.
-- Add or remove the is_* columns for the appearance types that you need; the
-- export has about 30 of them.
SELECT
  SUM(CASE WHEN is_amp_top_stories   THEN impressions ELSE 0 END) AS amp_top_stories_impressions,
  SUM(CASE WHEN is_amp_top_stories   THEN clicks      ELSE 0 END) AS amp_top_stories_clicks,
  SUM(CASE WHEN is_review_snippet    THEN impressions ELSE 0 END) AS review_snippet_impressions,
  SUM(CASE WHEN is_review_snippet    THEN clicks      ELSE 0 END) AS review_snippet_clicks,
  SUM(CASE WHEN is_recipe_feature    THEN impressions ELSE 0 END) AS recipe_feature_impressions,
  SUM(CASE WHEN is_recipe_feature    THEN clicks      ELSE 0 END) AS recipe_feature_clicks,
  SUM(CASE WHEN is_video            THEN impressions ELSE 0 END) AS video_impressions,
  SUM(CASE WHEN is_video            THEN clicks      ELSE 0 END) AS video_clicks,
  SUM(CASE WHEN is_organic_shopping THEN impressions ELSE 0 END) AS organic_shopping_impressions,
  SUM(CASE WHEN is_organic_shopping THEN clicks      ELSE 0 END) AS organic_shopping_clicks,
  SUM(impressions) AS total_impressions,
  SUM(clicks) AS total_clicks
FROM `your-project-id.searchconsole.searchdata_url_impression`
WHERE data_date BETWEEN '2026-09-01' AND '2026-09-30'
  AND search_type = 'WEB';
