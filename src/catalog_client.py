"""
catalog_client.py — provider-agnostic abstraction for fetching song candidates.

Concrete implementations:
  GroqCatalogClient     — Groq LLM API (requires GROQ_API_KEY env var)
  LocalCSVCatalogClient — reads from a local CSV file (used as fallback)

All clients return dicts that match the recommender pipeline schema:
  id, title, artist, song_type, genre, mood, energy, danceability,
  acousticness, tempo_bpm, valence
"""

import csv
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from groq import Groq

logger = logging.getLogger(__name__)

VALID_GENRES = {
    "pop", "lofi", "rock", "ambient", "jazz", "synthwave", "indie",
    "hip-hop", "classical", "edm", "country", "metal", "r&b", "folk", "latin",
}
VALID_MOODS = {
    "happy", "chill", "intense", "relaxed", "moody", "focused",
    "energetic", "calm", "romantic", "angry", "sad", "passionate",
}

_SONG_FIELDS = """Each song object must have exactly these fields:
  "title":        string  — real song title
  "artist":       string  — real artist name
  "genre":        string  — one of: pop, lofi, rock, ambient, jazz, synthwave, indie, hip-hop, classical, edm, country, metal, r&b, folk, latin
  "mood":         string  — one of: happy, chill, intense, relaxed, moody, focused, energetic, calm, romantic, angry, sad, passionate
  "energy":       float   — 0.0 (mellow) to 1.0 (intense)
  "danceability": float   — 0.0 to 1.0
  "acousticness": float   — 0.0 (electronic) to 1.0 (fully acoustic)
  "tempo_bpm":    integer — beats per minute, typically 60–200
  "valence":      float   — 0.0 (sad/dark) to 1.0 (happy/bright)"""


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseCatalogClient(ABC):
    @abstractmethod
    def search(self, query: str, limit: int = 20) -> List[Dict]: ...

    @abstractmethod
    def get_by_genre_mood(self, genre: str, mood: str, limit: int = 20) -> List[Dict]: ...


# ---------------------------------------------------------------------------
# Groq implementation
# ---------------------------------------------------------------------------

class GroqCatalogClient(BaseCatalogClient):
    """
    Uses Groq (free) to suggest real song candidates with estimated audio features.

    Required env var: GROQ_API_KEY
    Get a free key at: https://console.groq.com
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "").strip()
        if not self.api_key:
            raise ValueError(
                "Groq API key not found. "
                "Set the GROQ_API_KEY environment variable. "
                "Get a free key at https://console.groq.com"
            )
        self._client = Groq(api_key=self.api_key)
        self._model = model

    def _build_prompt(self, *, genre=None, mood=None, query=None, limit=20) -> str:
        constraints = []
        if query:
            constraints.append(f'related to: "{query}"')
        if genre:
            constraints.append(f"genre: {genre}")
        if mood:
            constraints.append(f"mood: {mood}")
        desc = ", ".join(constraints) if constraints else "a variety of genres and moods"
        return (
            f"Suggest {limit} real, well-known songs that are {desc}.\n"
            f"Return a JSON array of {limit} objects.\n"
            f"{_SONG_FIELDS}\n"
            "Return only the JSON array — no explanation, no markdown fences."
        )

    def _parse(self, text: str) -> List[Dict]:
        text = text.strip()
        if "```" in text:
            for block in text.split("```"):
                block = block.strip()
                if block.startswith("json"):
                    block = block[4:].strip()
                if block.startswith("[") or block.startswith("{"):
                    text = block
                    break
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            for key in ("songs", "tracks", "results"):
                if isinstance(parsed.get(key), list):
                    return parsed[key]
        if isinstance(parsed, list):
            return parsed
        raise ValueError(f"Unexpected response shape: {type(parsed)}")

    def _normalize(self, raw: Dict, index: int) -> Optional[Dict]:
        title  = str(raw.get("title", "")).strip()
        artist = str(raw.get("artist", "")).strip()
        if not title or not artist:
            return None

        genre = str(raw.get("genre", "pop")).lower().strip()
        mood  = str(raw.get("mood",  "chill")).lower().strip()
        if genre not in VALID_GENRES:
            genre = "pop"
        if mood not in VALID_MOODS:
            mood = "chill"

        def _f(key, default):
            try:
                return max(0.0, min(1.0, float(raw.get(key, default))))
            except (TypeError, ValueError):
                return default

        def _i(key, default):
            try:
                return max(40, min(220, int(raw.get(key, default))))
            except (TypeError, ValueError):
                return default

        return {
            "id":           f"groq_{index}",
            "title":        title,
            "artist":       artist,
            "song_type":    "song",
            "genre":        genre,
            "mood":         mood,
            "energy":       _f("energy",       0.60),
            "danceability": _f("danceability",  0.60),
            "acousticness": _f("acousticness",  0.40),
            "tempo_bpm":    _i("tempo_bpm",     100),
            "valence":      _f("valence",       0.55),
        }

    def _call(self, prompt: str, limit: int) -> List[Dict]:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            text = response.choices[0].message.content
            raw_list = self._parse(text)
            results = [
                n for i, r in enumerate(raw_list[:limit])
                if (n := self._normalize(r, i)) is not None
            ]
            logger.info("Groq returned %d normalized songs", len(results))
            return results
        except json.JSONDecodeError as exc:
            logger.error("Groq returned invalid JSON: %s", exc)
            raise ValueError(f"Groq returned invalid JSON: {exc}") from exc
        except Exception as exc:
            logger.error("Groq API call failed: %s", exc)
            raise

    def search(self, query: str, limit: int = 20) -> List[Dict]:
        logger.info("Groq search: query=%r limit=%d", query, limit)
        return self._call(self._build_prompt(query=query, limit=limit), limit)

    def get_by_genre_mood(self, genre: str, mood: str, limit: int = 20) -> List[Dict]:
        logger.info("Groq get_by_genre_mood: genre=%r mood=%r", genre, mood)
        return self._call(self._build_prompt(genre=genre, mood=mood, limit=limit), limit)


# ---------------------------------------------------------------------------
# Local CSV fallback
# ---------------------------------------------------------------------------

class LocalCSVCatalogClient(BaseCatalogClient):
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self._songs: Optional[List[Dict]] = None

    def _load(self) -> List[Dict]:
        if self._songs is not None:
            return self._songs
        songs: List[Dict] = []
        try:
            with open(self.csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    songs.append({
                        "id":           row.get("id", str(i)),
                        "title":        row.get("title", ""),
                        "artist":       row.get("artist", ""),
                        "song_type":    row.get("song_type", "song"),
                        "genre":        row.get("genre", ""),
                        "mood":         row.get("mood", ""),
                        "energy":       float(row.get("energy", 0.5)),
                        "danceability": float(row.get("danceability", 0.5)),
                        "acousticness": float(row.get("acousticness", 0.5)),
                        "tempo_bpm":    int(float(row.get("tempo_bpm", 100))),
                        "valence":      float(row.get("valence", 0.5)),
                    })
            logger.info("LocalCSVCatalogClient loaded %d songs from %s", len(songs), self.csv_path)
        except FileNotFoundError:
            logger.error("CSV catalog not found: %s", self.csv_path)
        except Exception as exc:
            logger.error("Failed to load CSV catalog: %s", exc)
        self._songs = songs
        return songs

    def search(self, query: str, limit: int = 20) -> List[Dict]:
        songs = self._load()
        if not songs:
            return []
        q = query.lower()
        matches = [s for s in songs if q in s["title"].lower() or q in s["artist"].lower()]
        return (matches if matches else songs)[:limit]

    def get_by_genre_mood(self, genre: str, mood: str, limit: int = 20) -> List[Dict]:
        songs = self._load()
        if not songs:
            return []
        matches = [
            s for s in songs
            if (not genre or s["genre"].lower() == genre.lower())
            and (not mood or s["mood"].lower() == mood.lower())
        ]
        return (matches if matches else songs)[:limit]
