"""
VibeFinder — Streamlit music recommender app.

Catalog priority:
  1. Last.fm API (if LASTFM_API_KEY is set)
  2. Local CSV fallback (data/songs.csv)

Run:  streamlit run src/app.py
"""

import logging
import os
from pathlib import Path

import streamlit as st

from catalog_client import GroqCatalogClient, LocalCSVCatalogClient
from recommender import recommend_songs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).parent.parent / "data" / "songs.csv"

GENRES = [
    "pop", "lofi", "rock", "ambient", "jazz", "synthwave",
    "indie", "hip-hop", "classical", "edm", "country",
    "metal", "r&b", "folk", "latin",
]
MOODS = [
    "happy", "chill", "intense", "relaxed", "moody", "focused",
    "energetic", "calm", "romantic", "angry", "sad", "passionate",
]


# ---------------------------------------------------------------------------
# Catalog client factory (cached per session)
# ---------------------------------------------------------------------------

@st.cache_resource
def _build_catalog_client():
    """Try the Groq API client; fall back to CSV if the key is absent."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if api_key:
        try:
            client = GroqCatalogClient(api_key=api_key)
            logger.info("Using Groq catalog")
            return client, False  # (client, is_fallback)
        except Exception as exc:
            logger.warning("Could not initialise Groq client: %s", exc)
    logger.info("GROQ_API_KEY not set — using local CSV catalog")
    return LocalCSVCatalogClient(str(CSV_PATH)), True


def _fetch_candidates(client, genre: str, mood: str, query: str, limit: int = 30):
    """Fetch candidates, returning (songs, error_message)."""
    try:
        if query.strip():
            songs = client.search(query.strip(), limit=limit)
        else:
            songs = client.get_by_genre_mood(genre, mood, limit=limit)
        return songs, None
    except Exception as exc:
        logger.error("Catalog fetch failed: %s", exc)
        return [], str(exc)


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="VibeFinder", page_icon="🎵", layout="centered")
    st.title("VibeFinder 🎵")
    st.caption("Content-based music recommender — powered by Gemini + local ranking")

    client, is_fallback = _build_catalog_client()

    if is_fallback:
        st.warning(
            "**Fallback mode active:** `GROQ_API_KEY` not found. "
            "Recommendations are drawn from the local CSV catalog (18 songs). "
            "Get a free key at https://console.groq.com",
            icon="⚠️",
        )

    # ------------------------------------------------------------------
    # Preference inputs
    # ------------------------------------------------------------------
    st.subheader("Your Preferences")
    col1, col2 = st.columns(2)

    with col1:
        genre = st.selectbox("Favorite Genre", GENRES)
        mood  = st.selectbox("Mood", MOODS)
        energy = st.slider("Energy Level (0 = mellow, 1 = intense)", 0.0, 1.0, 0.6, 0.05)

    with col2:
        acoustic_pref = st.radio(
            "Acoustic Preference",
            ["No preference", "Acoustic", "Electronic"],
        )
        query = st.text_input(
            "Search by song or artist (optional)",
            placeholder="e.g. lofi study, Neon Echo",
        )
        k = st.slider("Number of recommendations", 1, 10, 5)

    # ------------------------------------------------------------------
    # Recommendation
    # ------------------------------------------------------------------
    if st.button("Find My Vibes", type="primary"):
        likes_acoustic = {"Acoustic": True, "Electronic": False, "No preference": None}[acoustic_pref]

        # Keys must match what score_song() expects: "genre", "mood", "energy", "likes_acoustic"
        user_prefs = {
            "genre":         genre,
            "mood":          mood,
            "energy":        energy,
            "likes_acoustic": likes_acoustic,
        }

        # 1. Fetch candidates
        with st.spinner("Fetching candidates from catalog…"):
            candidates, fetch_error = _fetch_candidates(client, genre, mood, query)

        # 2. If API gave nothing, try CSV fallback
        used_csv_fallback = is_fallback
        if not candidates and not is_fallback:
            if fetch_error:
                st.warning(f"API error: {fetch_error}. Falling back to local catalog.", icon="⚠️")
            else:
                st.info("API returned no results — falling back to local catalog.", icon="ℹ️")
            csv_client = LocalCSVCatalogClient(str(CSV_PATH))
            candidates, _ = _fetch_candidates(csv_client, genre, mood, query)
            used_csv_fallback = True

        if not candidates:
            st.error("No songs found even in the local catalog. Check that data/songs.csv exists.")
            return

        # 3. Rank candidates with existing scoring pipeline
        with st.spinner("Ranking…"):
            recommendations = recommend_songs(user_prefs, candidates, k=k)

        # 4. Display results
        source_label = "local CSV catalog (fallback)" if used_csv_fallback else "Last.fm API"
        st.subheader(f"Top {len(recommendations)} Recommendations")
        st.caption(f"Source: {source_label} · {len(candidates)} candidates ranked")

        for rank, (song, score, reasons) in enumerate(recommendations, 1):
            confidence = "High" if score >= 0.75 else "Medium" if score >= 0.50 else "Low"
            badge = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}[confidence]

            with st.expander(
                f"{rank}. **{song['title']}** — {song['artist']}  "
                f"{badge} {confidence} confidence ({score:.2f})"
            ):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Genre",  song.get("genre", "—"))
                c2.metric("Mood",   song.get("mood",  "—"))
                c3.metric("Energy", f"{song.get('energy', 0):.2f}")
                c4.metric("Valence", f"{song.get('valence', 0):.2f}")

                if reasons:
                    st.caption("Why this song: " + " · ".join(reasons))

        if used_csv_fallback:
            st.caption("ℹ️ Results sourced from local CSV — set GROQ_API_KEY for live AI-powered search.")


if __name__ == "__main__":
    main()
