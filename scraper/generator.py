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
    def __init__(self, output_dir: Path, translator, image_cdn: str, sections: list):
        self.out = output_dir
        self.tr = translator
        self.image_cdn = image_cdn
        self.sections = sections
        self.env = Environment(
            loader=FileSystemLoader(Path(__file__).parent.parent / "templates"),
            autoescape=True,
        )
        self.env.globals.update(
            image_cdn=image_cdn,
            all_sections=sections,
            last_updated=datetime.now(timezone.utc).strftime("%-d %B %Y, %H:%M UTC"),
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
            sec_data.append({
                **sec,
                "stories": [self._enrich(s) for s in section_stories.get(slug, [])[:6]],
            })
        html = self.env.get_template("home.html").render(
            featured=enriched[:1],
            secondary=enriched[1:7],
            rest=enriched[7:19],
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
        enriched = self._enrich(story)
        enriched["bn_cards"] = self._translate_cards(story.get("cards", []))
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
