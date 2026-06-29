"""Quintype API client for Daily Waadaa."""
import time
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

    def get_stories(self, limit: int = 20, section: str = None, offset: int = 0) -> list:
        params = {
            "fields": "id,headline,subheadline,slug,hero-image-s3-key,sections,tags,published-at,author-name",
            "limit": limit,
            "offset": offset,
        }
        if section:
            params["section"] = section

        try:
            resp = self.session.get(f"{self.base_url}/stories", params=params, timeout=15)
            resp.raise_for_status()
            stories = resp.json().get("stories", [])
            for s in stories:
                s["_image_url"] = self._image_url(s.get("hero-image-s3-key"))
                s["_section_slug"] = self._primary_section(s)
            return stories
        except Exception as e:
            print(f"[API] Error fetching stories (section={section}): {e}")
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

    def get_config(self) -> dict:
        try:
            resp = self.session.get(f"{self.base_url}/config", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[API] Error fetching config: {e}")
            return {}

    def _image_url(self, s3_key: Optional[str], width: int = 800) -> Optional[str]:
        if not s3_key:
            return None
        return f"{self.image_cdn}/{s3_key}?w={width}&auto=format&compress=true"

    def _primary_section(self, story: dict) -> str:
        sections = story.get("sections", [])
        if sections:
            slug = sections[0].get("slug", "")
            # Normalise sub-sections: cricket → sports
            PARENT_MAP = {
                "cricket": "sports", "football": "sports",
                "economy": "business", "finance": "business",
            }
            return PARENT_MAP.get(slug, slug)
        return "latest"
