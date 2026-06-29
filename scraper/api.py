"""Quintype API client for Daily Waadaa."""
import requests
from typing import Optional


class QuintypeAPI:
    def __init__(self, base_url: str, image_cdn: str):
        self.base_url = base_url.rstrip("/")
        self.image_cdn = image_cdn.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; BanglaWada/1.0; +https://github.com)"
        })

    def get_stories(self, limit: int = 20, section_id: int = None, offset: int = 0) -> list:
        params = {
            "fields": "id,headline,subheadline,slug,hero-image-s3-key,sections,tags,published-at,author-name",
            "limit": limit,
            "offset": offset,
        }
        if section_id:
            params["section-id"] = section_id

        try:
            resp = self.session.get(f"{self.base_url}/stories", params=params, timeout=15)
            resp.raise_for_status()
            stories = resp.json().get("stories", [])
            for s in stories:
                s["_image_url"] = self._image_url(s.get("hero-image-s3-key"))
                s["_section_slug"] = self._primary_section(s)
            return stories
        except Exception as e:
            print(f"[API] Error fetching stories (section_id={section_id}): {e}")
            return []

    def get_story(self, story_id: str) -> Optional[dict]:
        try:
            resp = self.session.get(f"{self.base_url}/stories/{story_id}", timeout=15)
            resp.raise_for_status()
            data = resp.json()
            story = data.get("story", data)
            story["_image_url"] = self._image_url(story.get("hero-image-s3-key"))
            story["_section_slug"] = self._primary_section(story)
            return story
        except Exception as e:
            print(f"[API] Error fetching story {story_id}: {e}")
            return None

    def _image_url(self, s3_key: Optional[str], width: int = 800) -> Optional[str]:
        if not s3_key:
            return None
        return f"{self.image_cdn}/{s3_key}?w={width}&auto=format&compress=true"

    def _primary_section(self, story: dict) -> str:
        sections = story.get("sections", [])
        if sections:
            slug = sections[0].get("slug", "")
            PARENT_MAP = {
                "cricket": "sports", "football": "sports", "fifa-world-cup-2026": "sports",
                "economy": "business", "finance": "business", "banking": "business",
                "dhaka": "bangladesh", "chittagong": "bangladesh", "sylhet": "bangladesh",
                "bnp": "politics", "jamaat": "politics",
                "south-asia": "world", "middle-east": "world", "europe": "world",
            }
            return PARENT_MAP.get(slug, slug)
        return "latest"
