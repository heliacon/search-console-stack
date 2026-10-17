# Search Console Stack

A reporting stack for Google Search Console. It keeps a local copy of your
Search Console data in the same schema as the BigQuery bulk export and it comes
with ready made SQL reports that run on the local copy and on the export without
a change.

## What you get

- A local SQLite database that mirrors the native Big Query bulk export schema.
- Two pull scripts: one for the Search Console API, one for the Big Query export.
- SQL reports for site level and page level analysis.
- A one step installer for macOS, Linux and Windows.

## How it works

The pull scripts write the same table names and column names that the Big Query
bulk export uses (`searchdata_site_impression` and `searchdata_url_impression`).
So the reports in `queries/` run on the local SQLite database and on the export
in BigQuery. Only two things change for Big Query:

- The table name gets the project and dataset prefix, for example
  `project.dataset.searchdata_url_impression`.
- `strftime` becomes `FORMAT_DATE` in the trend reports. Each of those reports
  has a comment with the exact change.

Use the API script to backfill about 16 months of history. Then run the
Big Query script each day. The two scripts write the same tables. For each day,
the last script to write wins, so Big Query replaces the API figures with the
exact export figures as it becomes available.

## Requirements

- A Google Search Console property that you own.
- For the Big Query path: the Search Console [bulk data export](https://support.google.com/webmasters/answer/12919192) set up for that property.
- Python 3.9 or later. The installer adds it if it is not present.

## Install

macOS and Linux:

```
./setup.sh
```

Windows (PowerShell):

```
.\setup.ps1
```

The installer makes sure Python is present, makes a local environment in
`.venv` and installs the Python packages. It is safe to run again. Add `--yes`
(or `-Yes` on Windows) to answer yes to every prompt, for an agent or an
unattended run.

## Credentials

Put your Google credentials in the `GSC-setup` folder:

- `service_account.json` for the service account method, or
- `client_secret.json` for the OAuth method.

The `.gitignore` file excludes these, the `token.json` file and the `*.db`
files. Never commit them.

## Get the data

1. Open `GSC-setup/basic_gsc_pull.py` (API) or `GSC-setup/basic_big_query_pull.py`
   (Big Query). Set `SITE_URL` or `PROJECT` and set the dates at the top.
2. Run a pull, then check the result:

   ```
   source .venv/bin/activate      # Windows: .\.venv\Scripts\Activate.ps1
   cd GSC-setup
   python basic_gsc_pull.py       # the API backfill
   python basic_check.py          # a summary of the database
   ```

## Run the reports

Each report in `queries/` has placeholders at the top. Edit them before you run
the report:

- `site_url` the property, for example `sc-domain:example.com`.
- The date range.
- For page-level reports, the `url` pattern, for example
  `https://example.com/blog/%`.

Run a report against the local database with the `sqlite3` tool:

```
sqlite3 GSC-setup/gsc.db < queries/site/site_overview.sql
```

## The reports

Site-level reports read `searchdata_site_impression`. Page-level reports read
`searchdata_url_impression`.

### Site-level (`queries/site/`)

| Report | What it shows |
|---|---|
| `site_overview` | The headline totals for a date range. |
| `site_top_queries` | The top queries by clicks. |
| `site_query_movers` | The queries with the largest rise or fall in clicks between two periods. |
| `site_ctr_opportunities` | The page-one queries with many impressions and a low CTR. |
| `site_striking_distance` | The queries at position 11 to 20 with many impressions. |
| `site_position_buckets` | The count of queries in each ranking band. |
| `site_search_type_breakdown` | The totals for each search type. |
| `site_device_breakdown` | The totals for each device. |
| `site_country_breakdown` | The totals for each country. |
| `trends/site_trend_daily` | The daily totals with a 7-day moving average. |
| `trends/site_trend_weekly` | The weekly totals. |
| `trends/site_trend_monthly` | The monthly totals. |
| `trends/site_trend_yearly` | The yearly totals. |
| `comparisons/site_compare_wow` | Week over week totals. |
| `comparisons/site_compare_mom` | Month over month totals. |
| `comparisons/site_compare_yoy` | Year over year totals, for equal-length periods. |
| `comparisons/site_new_lost_queries` | The new queries and the lost queries between two periods. |

### Page-level (`queries/url/`)

| Report | What it shows |
|---|---|
| `url_top_pages` | The top pages by clicks. |
| `url_queries_for_url` | The queries that bring traffic to a page or a folder. |
| `url_page_query_pairs` | The top page and query pairs by clicks. |
| `url_page_movers` | The pages with the largest rise or fall in clicks between two periods. |
| `url_striking_distance` | The page and query pairs at position 11 to 20 with many impressions. |
| `url_cannibalisation` | The queries where more than one page competes. |
| `url_discover_pages` | The Discover and Google News data for each page. |
| `url_device_breakdown` | The totals for each device for a page or a folder. |
| `url_country_breakdown` | The totals for each country for a page or a folder. |
| `url_appearance_breakdown` | The clicks and impressions for each search appearance. BigQuery only, see below. |
| `trends/url_trend_daily` | The daily totals for a page or a folder with a 7-day moving average. |
| `trends/url_trend_weekly` | The weekly totals for a page or a folder. |
| `trends/url_trend_monthly` | The monthly totals for a page or a folder. |
| `trends/url_trend_yearly` | The yearly totals for a page or a folder. |
| `trends/url_footprint_trend` | The number of different queries and pages for each month. |
| `comparisons/url_compare_wow` | Week over week totals for a page or a folder. |
| `comparisons/url_compare_mom` | Month over month totals for a page or a folder. |
| `comparisons/url_compare_yoy` | Year over year totals for a page or a folder, for equal-length periods. |
| `comparisons/url_new_lost_pages` | The new pages and the lost pages between two periods. |

## Things to know about the data

- **Average position** is `SUM(sum_top_position or sum_position) / SUM(impressions) + 1`.
  The export stores a summed zero-based position, so a plain average would be wrong.
- **Anonymised queries.** Google hides rare queries. The per-query reports drop
  the anonymised rows so each query is a real string. The totals and trends keep
  all rows, so they are complete.
- **The API is approximate.** The API gives an average position with rounding and
  it omits the anonymised queries. The Big Query export is exact. So the API
  backfill is a little low until the export writes the same day.
- **Search appearance is BigQuery only.** The export has about 30 search-appearance
  (`is_*`) columns, for rich results. The local copy and the API do not keep them,
  so `url_appearance_breakdown` runs on the export only.
- **Discover and Google News** have no query dimension, so those surfaces are
  page-level only.

## Layout

```
GSC-setup/      the pull scripts and the check script
queries/site/   site-level reports (trends/ and comparisons/ inside)
queries/url/    page-level reports (trends/ and comparisons/ inside)
setup.sh        installer for macOS and Linux
setup.ps1       installer for Windows
requirements.txt the Python packages
```

## Licence

MIT. See [LICENSE](LICENSE).
