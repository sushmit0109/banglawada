"""Bengali translator with SQLite translation cache.

Uses deep-translator (free Google Translate backend) — no API key required.
Every string is hashed and cached so it is never translated twice.
"""
import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Optional


# Maximum characters deep-translator accepts per call
_CHUNK = 4500


class Translator:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
        self._backend = None

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS cache (
                    key  TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    ts   INTEGER NOT NULL
                )"""
            )

    def _backend_fn(self):
        if self._backend is None:
            from deep_translator import GoogleTranslator
            self._backend = GoogleTranslator(source="en", target="bn")
        return self._backend

    # ------------------------------------------------------------------
    def translate(self, text: str) -> str:
        """Translate English text to Bengali, using cache."""
        if not text or not text.strip():
            return text

        key = hashlib.md5(text.encode()).hexdigest()
        cached = self._get(key)
        if cached is not None:
            return cached

        result = self._do_translate(text)
        self._set(key, result)
        return result

    def translate_html(self, html: str) -> str:
        """Translate visible text inside an HTML snippet, preserving tags."""
        if not html:
            return html
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for node in soup.find_all(string=True):
                stripped = node.strip()
                if stripped:
                    node.replace_with(self.translate(stripped))
            return str(soup.body or soup)
        except Exception as e:
            print(f"[Translator] HTML parse error: {e}")
            return html

    # ------------------------------------------------------------------
    def _do_translate(self, text: str) -> str:
        chunks = self._split(text)
        parts = []
        for chunk in chunks:
            translated = self._call_api(chunk)
            parts.append(translated)
            if len(chunks) > 1:
                time.sleep(0.15)
        return " ".join(parts)

    def _call_api(self, text: str, retries: int = 3) -> str:
        for attempt in range(retries):
            try:
                fn = self._backend_fn()
                result = fn.translate(text)
                return result or text
            except Exception as e:
                print(f"[Translator] Attempt {attempt+1} failed: {e}")
                self._backend = None  # reset so next call recreates
                time.sleep(1.5 * (attempt + 1))
        return text  # fallback: return original

    @staticmethod
    def _split(text: str) -> list[str]:
        if len(text) <= _CHUNK:
            return [text]
        # Split on sentence boundaries
        chunks, current = [], ""
        for sentence in text.replace("\n", " ").split(". "):
            if len(current) + len(sentence) > _CHUNK:
                if current:
                    chunks.append(current.strip())
                current = sentence + ". "
            else:
                current += sentence + ". "
        if current.strip():
            chunks.append(current.strip())
        return chunks or [text]

    # ------------------------------------------------------------------
    def _get(self, key: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT value FROM cache WHERE key=?", (key,)).fetchone()
            return row[0] if row else None

    def _set(self, key: str, value: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache(key,value,ts) VALUES(?,?,?)",
                (key, value, int(time.time())),
            )
