#!/usr/bin/env python3
"""
BanglaWada build script
=======================
Fetches articles from Daily Waadaa via the Quintype public API,
translates them to Bengali (cached in SQLite — never re-translated),
and generates a fully static HTML site under output/.

Usage:
    python build.py              # incremental: skip articles already built
    python build.py --full       # rebuild all article pages
    python build.py --limit 20   # cap stories fetched per section
"""
import argparse
import os
import sys
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────
API_BASE   = "https://www.dailywaadaa.com/api/v1"
IMAGE_CDN  = "https://media.assettype.com"
OUTPUT_DIR = Path("output")
CACHE_DB   = Path("cache/translations.db")
SITE_BASE  = os.environ.get("SITE_BASE", "/")

# Section slugs mapped to their Quintype section IDs (from /api/v1/config)
SECTIONS = [
    {"slug": "bangladesh", "name": "Bangladesh", "bn": "বাংলাদেশ", "id": 103182},
    {"slug": "politics",   "name": "Politics",   "bn": "রাজনীতি",   "id": 103183},
    {"slug": "business",   "name": "Business",   "bn": "ব্যবসা",    "id": 103200},
    {"slug": "opinion",    "name": "Opinion",    "bn": "মতামত",     "id": 103184},
    {"slug": "world",      "name": "World",      "bn": "বিশ্ব",     "id": 103185},
    {"slug": "sports",     "name": "Sports",     "bn": "খেলাধুলা",  "id": 103196},
    {"slug": "lifestyle",  "name": "Lifestyle",  "bn": "জীবনধারা",  "id": 103186},
    {"slug": "arts",       "name": "Arts",       "bn": "শিল্পকলা",  "id": 103286},
]
# ──────────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="BanglaWada static site builder")
    parser.add_argument("--full",  action="store_true", help="Rebuild all article pages")
    parser.add_argument("--limit", type=int, default=20, help="Stories per section (default 20)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "static").mkdir(exist_ok=True)
    Path("cache").mkdir(exist_ok=True)

    from scraper.api        import QuintypeAPI
    from scraper.translator import Translator
    from scraper.generator  import SiteGenerator

    api        = QuintypeAPI(API_BASE, IMAGE_CDN)
    translator = Translator(CACHE_DB)
    generator  = SiteGenerator(OUTPUT_DIR, translator, IMAGE_CDN, SECTIONS, SITE_BASE)

    # ── 1. Fetch global latest stories for homepage hero/secondary ────────────
    print(f"[build] Fetching latest {args.limit} stories …")
    home_stories = api.get_stories(limit=args.limit)
    if not home_stories:
        print("[build] ERROR: Could not fetch any stories. Aborting.", file=sys.stderr)
        sys.exit(1)

    # ── 2. Fetch section-specific stories using section-id ────────────────────
    section_stories: dict[str, list] = {}
    for sec in SECTIONS:
        print(f"[build] Fetching section: {sec['name']} (id={sec['id']}) …")
        section_stories[sec["slug"]] = api.get_stories(
            limit=args.limit, section_id=sec["id"]
        )

    # ── 3. Generate homepage ──────────────────────────────────────────────────
    print("[build] Generating homepage …")
    generator.generate_home(home_stories, section_stories)

    # ── 4. Generate section pages ─────────────────────────────────────────────
    for sec in SECTIONS:
        print(f"[build] Generating section page: {sec['name']} …")
        generator.generate_section(sec, section_stories.get(sec["slug"], []))

    # ── 5. Generate article pages (incremental) ───────────────────────────────
    seen_ids: set[str] = set()
    all_stories = list(home_stories)
    for stories in section_stories.values():
        all_stories.extend(stories)

    generated = skipped = errors = 0
    for story in all_stories:
        sid = story["id"]
        if sid in seen_ids:
            continue
        seen_ids.add(sid)

        slug = story.get("slug", sid)
        if not args.full and generator.article_exists(slug):
            skipped += 1
            continue

        print(f"[build] Article: {story.get('headline', sid)[:65]} …")
        full = api.get_story(sid)
        if full:
            try:
                generator.generate_article(full)
                generated += 1
            except Exception as e:
                print(f"[build] ERROR generating {slug}: {e}")
                errors += 1
        else:
            errors += 1

    # ── 6. Copy static assets ─────────────────────────────────────────────────
    generator.copy_static()

    print(
        f"\n[build] Done! "
        f"Articles: {generated} generated, {skipped} skipped (cached), {errors} errors."
    )


if __name__ == "__main__":
    main()
