"""Bengali translator with SQLite translation cache.

Two backends:
  - Google Translate (default): free, no API key, used for hourly auto-updates
  - Claude (--use-claude flag): higher quality, used for one-time full rebuilds

Every string is hashed (MD5) and cached so it is never translated twice,
regardless of which backend produced the translation.
"""
import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Optional


_CHUNK = 4500  # max chars for Google Translate per call


class Translator:
    def __init__(self, db_path: Path, use_claude: bool = False):
        self.db_path = db_path
        self.use_claude = use_claude
        self._init_db()
        self._gt_backend = None

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS cache (
                    key  TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    ts   INTEGER NOT NULL
                )"""
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def translate_batch(self, texts: list) -> list:
        """Translate a list of strings in as few Claude calls as possible.

        Hits the cache first; only uncached strings go to Claude (one call).
        Falls back to sequential Google calls in non-Claude mode.
        """
        if not texts:
            return []
        if not self.use_claude:
            return [self.translate(t) for t in texts]

        results = [None] * len(texts)
        uncached = []  # (original_index, text)

        for i, text in enumerate(texts):
            if not text or not str(text).strip():
                results[i] = text
                continue
            key = hashlib.md5(str(text).encode()).hexdigest()
            cached = self._get(key)
            if cached is not None:
                results[i] = cached
            else:
                uncached.append((i, text))

        if uncached:
            batch_texts = [t for _, t in uncached]
            translated = self._claude_translate_batch(batch_texts)
            for (orig_i, orig_text), trans in zip(uncached, translated):
                results[orig_i] = trans
                key = hashlib.md5(str(orig_text).encode()).hexdigest()
                self._set(key, trans)

        return [r if r is not None else t for r, t in zip(results, texts)]

    def translate(self, text: str) -> str:
        if not text or not text.strip():
            return text
        key = hashlib.md5(text.encode()).hexdigest()
        cached = self._get(key)
        if cached is not None:
            return cached
        result = self._claude_translate(text) if self.use_claude else self._google_translate(text)
        self._set(key, result)
        return result

    def translate_html(self, html: str) -> str:
        """Translate visible text inside an HTML snippet, preserving tags."""
        if not html:
            return html
        if self.use_claude:
            return self._claude_translate_html(html)
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
    # Claude backend
    # ------------------------------------------------------------------

    def _claude_translate(self, text: str, retries: int = 3) -> str:
        """Translate via the `claude` CLI binary (uses existing VS Code auth)."""
        import subprocess
        prompt = (
            "You are a professional Bengali news translator. "
            "Translate the following English text into fluent, natural Bengali. "
            "Return ONLY the Bengali translation — no explanation, no quotes.\n\n"
            + text
        )
        for attempt in range(retries):
            try:
                result = subprocess.run(
                    ["claude", "-p", prompt],
                    capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
                print(f"[Claude] Attempt {attempt+1}: {result.stderr[:100]}")
            except Exception as e:
                print(f"[Claude] Attempt {attempt+1} failed: {e}")
            time.sleep(2 * (attempt + 1))
        return text

    def _claude_translate_html(self, html: str) -> str:
        """Send full HTML to Claude; it translates text while preserving tags."""
        import subprocess
        key = "html:" + hashlib.md5(html.encode()).hexdigest()
        cached = self._get(key)
        if cached is not None:
            return cached

        prompt = (
            "You are a professional Bengali news translator. "
            "Translate ALL English text in the following HTML to fluent Bengali. "
            "Preserve every HTML tag, attribute, and structure exactly as-is. "
            "Return ONLY the translated HTML — nothing else.\n\n"
            + html
        )
        for attempt in range(3):
            try:
                result = subprocess.run(
                    ["claude", "-p", prompt],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0 and result.stdout.strip():
                    translated = result.stdout.strip()
                    self._set(key, translated)
                    return translated
                print(f"[Claude HTML] Attempt {attempt+1}: {result.stderr[:100]}")
            except Exception as e:
                print(f"[Claude HTML] Attempt {attempt+1} failed: {e}")
            time.sleep(2 * (attempt + 1))
        return html

    def _claude_translate_batch(self, texts: list) -> list:
        """Translate N strings in a single Claude subprocess call."""
        import subprocess, re
        numbered = "\n".join(f"[{i + 1}] {t}" for i, t in enumerate(texts))
        prompt = (
            "You are a professional Bengali news translator. "
            "Translate each numbered English text into fluent, natural Bengali. "
            "Preserve any HTML tags exactly as-is. "
            "Return ONLY the Bengali translations in the same numbered format — one per line.\n"
            "Format: [N] <Bengali translation>\n\n"
            + numbered
        )
        for attempt in range(3):
            try:
                result = subprocess.run(
                    ["claude", "-p", prompt],
                    capture_output=True, text=True, timeout=180,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return self._parse_batch_response(result.stdout.strip(), len(texts), texts)
                print(f"[Claude batch] Attempt {attempt + 1}: {result.stderr[:120]}")
            except Exception as e:
                print(f"[Claude batch] Attempt {attempt + 1} failed: {e}")
            time.sleep(2 * (attempt + 1))
        return list(texts)  # fallback: return originals untranslated

    @staticmethod
    def _parse_batch_response(response: str, count: int, originals: list) -> list:
        """Parse [N] translation lines from a Claude batch response."""
        import re
        results = list(originals)
        for line in response.split("\n"):
            m = re.match(r"\[(\d+)\]\*?\*?\s*(.+)", line.strip())
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < count:
                    results[idx] = m.group(2).strip()
        return results

    # ------------------------------------------------------------------
    # Google Translate backend
    # ------------------------------------------------------------------

    def _google_backend(self):
        if self._gt_backend is None:
            from deep_translator import GoogleTranslator
            self._gt_backend = GoogleTranslator(source="en", target="bn")
        return self._gt_backend

    def _google_translate(self, text: str) -> str:
        chunks = self._split(text)
        parts = []
        for chunk in chunks:
            parts.append(self._google_call(chunk))
            if len(chunks) > 1:
                time.sleep(0.15)
        return " ".join(parts)

    def _google_call(self, text: str, retries: int = 3) -> str:
        for attempt in range(retries):
            try:
                result = self._google_backend().translate(text)
                return result or text
            except Exception as e:
                print(f"[Google] Attempt {attempt+1} failed: {e}")
                self._gt_backend = None
                time.sleep(1.5 * (attempt + 1))
        return text

    @staticmethod
    def _split(text: str) -> list:
        if len(text) <= _CHUNK:
            return [text]
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
    # Cache
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
