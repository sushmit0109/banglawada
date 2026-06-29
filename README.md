# বাংলাওয়াদা (BanglaWada)

Auto-translating Bengali mirror of [Daily Waadaa](https://www.dailywaadaa.com).

## How it works

```
GitHub Actions (every 6 hours)
  → Fetches articles via Quintype public API
  → Translates to Bengali (SQLite cache — nothing is ever translated twice)
  → Generates static HTML under output/
  → Deploys output/ to GitHub Pages (free hosting)
```

**Zero recurring cost** — uses the unofficial Google Translate backend via `deep-translator`.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# First build (translates everything, takes a few minutes)
python build.py

# Subsequent builds (mostly cache hits, very fast)
python build.py

# Force-regenerate all article pages
python build.py --full

# Limit stories per section (for testing)
python build.py --limit 5
```

The generated site is in `output/`. Open `output/index.html` in your browser.

## Deploy to GitHub Pages

1. Push this repo to GitHub (make it public for free Pages)
2. Go to **Settings → Pages** → set source to **gh-pages branch**
3. The GitHub Actions workflow (`.github/workflows/update.yml`) runs every 6 hours automatically
4. First run: trigger manually via **Actions → Build & Deploy BanglaWada → Run workflow**

Your site will be live at `https://<your-username>.github.io/<repo-name>/`

For a custom domain, add a `CNAME` file to `output/` with your domain name and update your DNS.

## Project structure

```
build.py                    Main entry point
scraper/
  api.py                    Quintype API client
  translator.py             Bengali translator + SQLite cache
  generator.py              Static HTML generator (Jinja2)
templates/
  base.html                 Shared layout, header, footer, nav
  home.html                 Homepage (hero + section strips)
  article.html              Individual article page
  section.html              Category listing page
static/style.css            CSS (responsive, Bengali typography)
cache/translations.db       SQLite translation cache (grows over time)
output/                     Generated site (git-ignored locally, pushed to gh-pages)
.github/workflows/update.yml  Scheduled GitHub Actions workflow
```

## Tweaking

- **Update frequency**: Edit the cron in `.github/workflows/update.yml`
- **Add/remove sections**: Edit `SECTIONS` in `build.py`
- **Styling**: Edit `static/style.css`
- **Translation engine**: Swap `GoogleTranslator` in `scraper/translator.py` for any `deep-translator` backend
