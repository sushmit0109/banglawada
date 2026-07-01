"""Static site generator — turns API stories into Bengali HTML pages."""
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

BENGALI_MONTHS = [
    "জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন",
    "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর",
]


def _bn_date(ts_ms: Optional[int]) -> str:
    if not ts_ms:
        return ""
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    return f"{dt.day} {BENGALI_MONTHS[dt.month - 1]} {dt.year}"


class SiteGenerator:
    def __init__(self, output_dir: Path, translator, image_cdn: str, sections: list, base_url: str = "/"):
        self.out = output_dir
        self.tr = translator
        self.image_cdn = image_cdn
        self.sections = sections
        self.base_url = base_url.rstrip("/") + "/"  # always ends with /
        self.env = Environment(
            loader=FileSystemLoader(Path(__file__).parent.parent / "templates"),
            autoescape=True,
        )
        dt = datetime.now(timezone.utc)
        last_updated_iso = dt.isoformat()
        bn_last_updated = (
            f"{dt.day} {BENGALI_MONTHS[dt.month - 1]} {dt.year},"
            f" {dt.hour:02d}:{dt.minute:02d} UTC"
        )
        self.env.globals.update(
            image_cdn=image_cdn,
            all_sections=sections,
            base_url=self.base_url,
            last_updated=bn_last_updated,
            last_updated_iso=last_updated_iso,
        )
        self.env.filters["bn_date"] = _bn_date

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_home(self, stories: list, section_stories: dict):
        enriched = [self._enrich(s) for s in stories]
        sec_data = []
        for sec in self.sections:
            slug = sec["slug"]
            # Use section-specific stories; show up to 4 per strip
            sec_data.append({
                **sec,
                "stories": [self._enrich(s) for s in section_stories.get(slug, [])[:13]],
            })
        html = self.env.get_template("home.html").render(
            featured=enriched[:1],
            secondary=enriched[1:6],
            section_blocks=sec_data,
        )
        (self.out / "index.html").write_text(html, encoding="utf-8")
        print("[Gen] index.html")

    def generate_section(self, section: dict, stories: list):
        enriched = [self._enrich(s) for s in stories]
        html = self.env.get_template("section.html").render(
            section=section,
            stories=enriched,
        )
        sec_dir = self.out / section["slug"]
        sec_dir.mkdir(parents=True, exist_ok=True)
        (sec_dir / "index.html").write_text(html, encoding="utf-8")
        print(f"[Gen] {section['slug']}/index.html")

    def generate_article(self, story: dict):
        # ── 1. Collect every translatable string into one flat list ────────────
        texts: list = []

        def add(val: str) -> int:
            idx = len(texts)
            texts.append(val or "")
            return idx

        headline_i    = add(story.get("headline"))
        subheadline_i = add(story.get("subheadline"))

        # Plan entries: (card_idx, elem_idx, field_name, text_idx_or_None, raw_html_if_deferred)
        # "text" elements contain long HTML bodies → deferred to translate_html() to avoid
        # batch timeout; all other fields are short strings and go into the batch.
        plan: list = []
        cards = story.get("cards", [])
        for ci, card in enumerate(cards):
            for ei, elem in enumerate(card.get("story-elements", [])):
                etype = elem.get("type", "")
                if etype == "text":
                    # Deferred: long HTML handled outside the batch
                    plan.append((ci, ei, "bn_html", None, elem.get("text", "")))
                elif etype in ("title", "summary"):
                    plan.append((ci, ei, "bn_text",        add(elem.get("text", "")), None))
                elif etype == "bigfact":
                    plan.append((ci, ei, "bn_text",        add(elem.get("text", "")),          None))
                    plan.append((ci, ei, "bn_label",       add(elem.get("label", "") or ""),   None))
                elif etype == "blockquote":
                    plan.append((ci, ei, "bn_text",        add(elem.get("text", "")),                  None))
                    plan.append((ci, ei, "bn_attribution", add(elem.get("attribution", "") or ""), None))
                elif etype == "image":
                    plan.append((ci, ei, "bn_title",       add(elem.get("title", "") or ""), None))

        # ── 2. One batch call translates everything (cache-aware) ──────────────
        translated = self.tr.translate_batch(texts)

        # ── 3. Build enriched story dict ───────────────────────────────────────
        enriched = dict(story)
        enriched["bn_headline"]    = translated[headline_i]
        enriched["bn_subheadline"] = translated[subheadline_i]
        enriched["bn_date"]        = _bn_date(story.get("published-at"))
        enriched["bn_section"]     = ""
        for sec in self.sections:
            if sec["slug"] == enriched.get("_section_slug"):
                enriched["bn_section"] = sec["bn"]
                break

        # ── 4. Reconstruct cards with translated fields ────────────────────────
        elem_fields: dict = {}  # (ci, ei) → {field: value}
        for ci, ei, field, ti, raw_html in plan:
            if ti is None:
                # Long HTML body — translate node-by-node (handles caching internally)
                value = self.tr.translate_html(raw_html)
            else:
                value = translated[ti]
            elem_fields.setdefault((ci, ei), {})[field] = value

        bn_cards = []
        for ci, card in enumerate(cards):
            new_elems = []
            for ei, elem in enumerate(card.get("story-elements", [])):
                e = dict(elem)
                e.update(elem_fields.get((ci, ei), {}))
                if elem.get("type") == "image":
                    e["_image_url"] = self._elem_image_url(elem)
                new_elems.append(e)
            bn_cards.append({**card, "story-elements": new_elems})
        enriched["bn_cards"] = bn_cards

        # ── 5. Render ──────────────────────────────────────────────────────────
        html = self.env.get_template("article.html").render(story=enriched)
        slug = story.get("slug", story["id"])
        article_path = self.out / "article" / slug
        article_path.mkdir(parents=True, exist_ok=True)
        (article_path / "index.html").write_text(html, encoding="utf-8")
        print(f"[Gen] article/{slug}")

    def article_exists(self, slug: str) -> bool:
        return (self.out / "article" / slug / "index.html").exists()

    def copy_static(self):
        src = Path(__file__).parent.parent / "static"
        dst = self.out / "static"
        if src.exists():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        print("[Gen] static assets copied")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _enrich(self, story: dict) -> dict:
        s = dict(story)
        s["bn_headline"] = self.tr.translate(s.get("headline") or "")
        s["bn_subheadline"] = self.tr.translate(s.get("subheadline") or "")
        s["bn_date"] = _bn_date(s.get("published-at"))
        # Find the section label
        for sec in self.sections:
            if sec["slug"] == s.get("_section_slug"):
                s["bn_section"] = sec["bn"]
                break
        else:
            s["bn_section"] = ""
        return s

    def _translate_cards(self, cards: list) -> list:
        result = []
        for card in cards:
            new_elements = []
            for elem in card.get("story-elements", []):
                e = dict(elem)
                etype = elem.get("type", "")
                if etype == "text":
                    e["bn_html"] = self.tr.translate_html(elem.get("text", ""))
                elif etype in ("title", "summary"):
                    e["bn_text"] = self.tr.translate(elem.get("text", ""))
                elif etype == "bigfact":
                    e["bn_text"] = self.tr.translate(elem.get("text", ""))
                    e["bn_label"] = self.tr.translate(elem.get("label", "") or "")
                elif etype == "blockquote":
                    e["bn_text"] = self.tr.translate(elem.get("text", ""))
                    e["bn_attribution"] = self.tr.translate(elem.get("attribution", "") or "")
                elif etype == "image":
                    e["_image_url"] = self._elem_image_url(elem)
                    e["bn_title"] = self.tr.translate(elem.get("title", "") or "")
                new_elements.append(e)
            result.append({**card, "story-elements": new_elements})
        return result

    def _elem_image_url(self, elem: dict, width: int = 800) -> Optional[str]:
        key = elem.get("image-s3-key") or elem.get("image_s3_key")
        if not key:
            return None
        return f"{self.image_cdn}/{key}?w={width}&auto=format&compress=true"
