"""
Tests for catalog_client.py covering:
  - GroqCatalogClient: successful retrieval (mocked Groq client)
  - GroqCatalogClient: missing API key
  - GroqCatalogClient: API failure / invalid JSON
  - GroqCatalogClient: markdown-wrapped JSON, out-of-range clamping
  - LocalCSVCatalogClient: happy path, fallback-to-all, missing file
  - Fallback integration: Groq error → CSV rescue
  - Low-confidence ranking scenario
"""

import json

import pytest
from unittest.mock import MagicMock, patch

from src.catalog_client import (
    GroqCatalogClient,
    LocalCSVCatalogClient,
    VALID_GENRES,
    VALID_MOODS,
)
from src.recommender import recommend_songs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_song(
    title="Test Song", artist="Test Artist", genre="pop", mood="happy",
    energy=0.8, danceability=0.75, acousticness=0.2, tempo_bpm=120, valence=0.8,
):
    return {
        "title": title, "artist": artist, "genre": genre, "mood": mood,
        "energy": energy, "danceability": danceability,
        "acousticness": acousticness, "tempo_bpm": tempo_bpm, "valence": valence,
    }


def _make_groq_client(response_text: str) -> GroqCatalogClient:
    """Build a GroqCatalogClient whose HTTP calls are fully mocked."""
    mock_groq = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = response_text
    mock_groq.chat.completions.create.return_value.choices = [mock_choice]
    with patch("src.catalog_client.Groq", return_value=mock_groq):
        client = GroqCatalogClient(api_key="fake")
    client._client = mock_groq
    return client


CSV_HEADER = "id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness\n"
CSV_ROW_1  = "1,Sunrise City,Neon Echo,pop,happy,0.82,118,0.84,0.79,0.18\n"
CSV_ROW_2  = "2,Midnight Coding,LoRoom,lofi,chill,0.42,78,0.56,0.62,0.71\n"


# ---------------------------------------------------------------------------
# GroqCatalogClient — init
# ---------------------------------------------------------------------------

class TestGroqCatalogClientInit:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with patch("src.catalog_client.Groq"):
            with pytest.raises(ValueError, match="GROQ_API_KEY"):
                GroqCatalogClient()

    def test_accepts_explicit_api_key(self):
        with patch("src.catalog_client.Groq"):
            client = GroqCatalogClient(api_key="fake_key")
        assert client.api_key == "fake_key"

    def test_reads_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "env_key")
        with patch("src.catalog_client.Groq"):
            client = GroqCatalogClient()
        assert client.api_key == "env_key"


# ---------------------------------------------------------------------------
# GroqCatalogClient — search
# ---------------------------------------------------------------------------

class TestGroqSearch:
    def test_returns_normalized_tracks(self):
        client = _make_groq_client(json.dumps([_make_song()]))
        results = client.search("pop songs", limit=1)

        assert len(results) == 1
        s = results[0]
        assert s["title"] == "Test Song"
        assert s["artist"] == "Test Artist"
        assert s["genre"] == "pop"
        assert s["mood"] == "happy"
        assert s["song_type"] == "song"
        assert s["id"].startswith("groq_")
        for field in ("energy", "danceability", "acousticness", "tempo_bpm", "valence"):
            assert field in s

    def test_handles_markdown_wrapped_json(self):
        wrapped = f"```json\n{json.dumps([_make_song()])}\n```"
        results = _make_groq_client(wrapped).search("pop", limit=1)
        assert len(results) == 1
        assert results[0]["title"] == "Test Song"

    def test_clamps_out_of_range_energy(self):
        results = _make_groq_client(json.dumps([_make_song(energy=5.0)])).search("x", limit=1)
        assert results[0]["energy"] == 1.0

    def test_clamps_negative_values(self):
        results = _make_groq_client(json.dumps([_make_song(acousticness=-0.5)])).search("x", limit=1)
        assert results[0]["acousticness"] == 0.0

    def test_unknown_genre_falls_back_to_pop(self):
        results = _make_groq_client(json.dumps([_make_song(genre="bluegrass_fusion")])).search("x", limit=1)
        assert results[0]["genre"] == "pop"

    def test_unknown_mood_falls_back_to_chill(self):
        results = _make_groq_client(json.dumps([_make_song(mood="melancholic_nostalgia")])).search("x", limit=1)
        assert results[0]["mood"] == "chill"

    def test_skips_songs_missing_title_or_artist(self):
        songs = [
            {**_make_song(), "title": ""},
            _make_song(title="Good Song"),
        ]
        results = _make_groq_client(json.dumps(songs)).search("x", limit=2)
        assert len(results) == 1
        assert results[0]["title"] == "Good Song"

    def test_invalid_json_raises_value_error(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            _make_groq_client("not json at all").search("x")

    def test_api_exception_propagates(self):
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.side_effect = Exception("quota exceeded")
        with patch("src.catalog_client.Groq", return_value=mock_groq):
            client = GroqCatalogClient(api_key="fake")
        client._client = mock_groq
        with pytest.raises(Exception, match="quota exceeded"):
            client.search("anything")


# ---------------------------------------------------------------------------
# GroqCatalogClient — get_by_genre_mood
# ---------------------------------------------------------------------------

class TestGroqGetByGenreMood:
    def test_returns_songs_with_requested_genre_mood(self):
        results = _make_groq_client(
            json.dumps([_make_song(genre="lofi", mood="chill")])
        ).get_by_genre_mood("lofi", "chill", limit=1)
        assert len(results) == 1
        assert results[0]["genre"] == "lofi"
        assert results[0]["mood"] == "chill"

    def test_respects_limit(self):
        songs = [_make_song(title=f"Song {i}") for i in range(10)]
        results = _make_groq_client(json.dumps(songs)).get_by_genre_mood("pop", "happy", limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# LocalCSVCatalogClient
# ---------------------------------------------------------------------------

class TestLocalCSVCatalogClient:
    def test_loads_and_searches_by_title(self, tmp_path):
        p = tmp_path / "songs.csv"
        p.write_text(CSV_HEADER + CSV_ROW_1 + CSV_ROW_2)
        results = LocalCSVCatalogClient(str(p)).search("Sunrise")
        assert len(results) == 1
        assert results[0]["energy"] == pytest.approx(0.82)

    def test_search_by_artist(self, tmp_path):
        p = tmp_path / "songs.csv"
        p.write_text(CSV_HEADER + CSV_ROW_1 + CSV_ROW_2)
        assert LocalCSVCatalogClient(str(p)).search("loroom")[0]["title"] == "Midnight Coding"

    def test_no_text_match_returns_all_songs(self, tmp_path):
        p = tmp_path / "songs.csv"
        p.write_text(CSV_HEADER + CSV_ROW_1 + CSV_ROW_2)
        assert len(LocalCSVCatalogClient(str(p)).search("zzznomatch")) == 2

    def test_genre_mood_filter(self, tmp_path):
        p = tmp_path / "songs.csv"
        p.write_text(CSV_HEADER + CSV_ROW_1 + CSV_ROW_2)
        results = LocalCSVCatalogClient(str(p)).get_by_genre_mood("pop", "happy")
        assert len(results) == 1
        assert results[0]["title"] == "Sunrise City"

    def test_no_match_returns_all(self, tmp_path):
        p = tmp_path / "songs.csv"
        p.write_text(CSV_HEADER + CSV_ROW_1 + CSV_ROW_2)
        assert len(LocalCSVCatalogClient(str(p)).get_by_genre_mood("metal", "angry")) == 2

    def test_missing_csv_returns_empty(self):
        c = LocalCSVCatalogClient("/nonexistent/path.csv")
        assert c.search("x") == []
        assert c.get_by_genre_mood("pop", "happy") == []

    def test_normalizes_numeric_types(self, tmp_path):
        p = tmp_path / "songs.csv"
        p.write_text(CSV_HEADER + CSV_ROW_1)
        s = LocalCSVCatalogClient(str(p)).search("Sunrise")[0]
        assert isinstance(s["energy"], float)
        assert isinstance(s["tempo_bpm"], int)


# ---------------------------------------------------------------------------
# Fallback integration
# ---------------------------------------------------------------------------

class TestCSVFallbackIntegration:
    def test_csv_used_when_groq_raises(self, tmp_path):
        p = tmp_path / "songs.csv"
        p.write_text(CSV_HEADER + CSV_ROW_1)

        mock_groq = MagicMock()
        mock_groq.chat.completions.create.side_effect = Exception("network error")
        with patch("src.catalog_client.Groq", return_value=mock_groq):
            groq_client = GroqCatalogClient(api_key="fake")
        groq_client._client = mock_groq
        csv_client = LocalCSVCatalogClient(str(p))

        try:
            candidates = groq_client.search("pop")
        except Exception:
            candidates = csv_client.get_by_genre_mood("pop", "happy")

        assert candidates[0]["title"] == "Sunrise City"

    def test_csv_used_when_groq_returns_empty(self, tmp_path):
        p = tmp_path / "songs.csv"
        p.write_text(CSV_HEADER + CSV_ROW_1 + CSV_ROW_2)

        groq_client = _make_groq_client(json.dumps([]))
        csv_client = LocalCSVCatalogClient(str(p))

        candidates = groq_client.search("obscure query")
        if not candidates:
            candidates = csv_client.get_by_genre_mood("pop", "happy")

        assert len(candidates) == 1
        assert candidates[0]["title"] == "Sunrise City"


# ---------------------------------------------------------------------------
# Low-confidence ranking
# ---------------------------------------------------------------------------

class TestLowConfidenceScenario:
    GOOD = {
        "id": "1", "title": "Good Match", "artist": "A", "song_type": "song",
        "genre": "pop", "mood": "happy", "energy": 0.8,
        "danceability": 0.8, "acousticness": 0.2, "tempo_bpm": 120, "valence": 0.8,
    }
    POOR = {
        "id": "2", "title": "Poor Match", "artist": "B", "song_type": "song",
        "genre": "metal", "mood": "angry", "energy": 0.95,
        "danceability": 0.4, "acousticness": 0.05, "tempo_bpm": 168, "valence": 0.2,
    }
    USER = {"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": None}

    def test_well_matched_song_ranks_first(self):
        assert recommend_songs(self.USER, [self.GOOD, self.POOR], k=2)[0][0]["title"] == "Good Match"

    def test_scores_ordered_descending(self):
        r = recommend_songs(self.USER, [self.GOOD, self.POOR], k=2)
        assert r[0][1] > r[1][1]

    def test_poor_match_low_confidence(self):
        assert recommend_songs(self.USER, [self.GOOD, self.POOR], k=2)[1][1] < 0.50

    def test_good_match_high_confidence(self):
        assert recommend_songs(self.USER, [self.GOOD], k=1)[0][1] >= 0.75
