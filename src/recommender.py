import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict


@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float


@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool


# ---------------------------------------------------------------------------
# Shared scoring helpers
# ---------------------------------------------------------------------------

def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    score = 0.0
    reasons = []

    if song["genre"] == user_prefs.get("genre", ""):
        score += 0.30
        reasons.append("genre match (+0.30)")

    if song["mood"] == user_prefs.get("mood", ""):
        score += 0.30
        reasons.append("mood match (+0.30)")

    energy_score = 1.0 - abs(float(song["energy"]) - float(user_prefs.get("energy", 0.5)))
    energy_contribution = energy_score * 0.25
    score += energy_contribution
    reasons.append(f"energy closeness (+{energy_contribution:.2f})")

    likes_acoustic = user_prefs.get("likes_acoustic")
    if likes_acoustic is True:
        acoustic_score = float(song["acousticness"])
    elif likes_acoustic is False:
        acoustic_score = 1.0 - float(song["acousticness"])
    else:
        acoustic_score = 0.5

    acoustic_contribution = acoustic_score * 0.15
    score += acoustic_contribution
    reasons.append(f"acousticness fit (+{acoustic_contribution:.2f})")

    return score, reasons

def _score(song: Dict, user: Dict) -> float:
    """
    Weighted content-based score (max = 1.0):
      genre match        30%
      mood match         30%
      energy proximity   25%
      acousticness fit   15%
    """
    genre_score = 1.0 if song["genre"] == user.get("genre", "") else 0.0
    mood_score  = 1.0 if song["mood"]  == user.get("mood", "")  else 0.0
    energy_score = 1.0 - abs(float(song["energy"]) - float(user.get("energy", 0.5)))

    likes_acoustic = user.get("likes_acoustic")
    if likes_acoustic is True:
        acoustic_score = float(song["acousticness"])
    elif likes_acoustic is False:
        acoustic_score = 1.0 - float(song["acousticness"])
    else:
        acoustic_score = 0.5  # no preference — neutral contribution

    return (
        genre_score   * 0.30 +
        mood_score    * 0.30 +
        energy_score  * 0.25 +
        acoustic_score * 0.15
    )


def _explain(song: Dict, user: Dict) -> str:
    """Builds a human-readable explanation for why a song was recommended."""
    reasons = []

    if song["genre"] == user.get("genre", ""):
        reasons.append(f"matches your favorite genre ({song['genre']})")

    if song["mood"] == user.get("mood", ""):
        reasons.append(f"fits your {song['mood']} mood")

    energy_diff = abs(float(song["energy"]) - float(user.get("energy", 0.5)))
    if energy_diff <= 0.10:
        reasons.append("energy level is a great match")
    elif energy_diff <= 0.25:
        reasons.append("energy level is close to your target")

    likes_acoustic = user.get("likes_acoustic")
    if likes_acoustic is True and float(song["acousticness"]) >= 0.70:
        reasons.append("has the acoustic feel you enjoy")
    elif likes_acoustic is False and float(song["acousticness"]) <= 0.30:
        reasons.append("has the electronic sound you prefer")

    if not reasons:
        reasons.append("is a reasonable match based on your overall preferences")

    return "This song " + ", and ".join(reasons) + "."


# ---------------------------------------------------------------------------
# Functional API  (used by src/main.py)
# ---------------------------------------------------------------------------

def load_songs(csv_path: str) -> List[Dict]:
    """
    Loads songs from a CSV file.
    Required by src/main.py
    """
    songs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            songs.append({
                "id":           int(row["id"]),
                "title":        row["title"],
                "artist":       row["artist"],
                "genre":        row["genre"],
                "mood":         row["mood"],
                "energy":       float(row["energy"]),
                "tempo_bpm":    float(row["tempo_bpm"]),
                "valence":      float(row["valence"]),
                "danceability": float(row["danceability"]),
                "acousticness": float(row["acousticness"]),
            })
    return songs


def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, List[str]]]:
    """
    Functional implementation of the recommendation logic.
    Required by src/main.py

    user_prefs keys: genre, mood, energy, likes_acoustic (optional)
    Returns: list of (song_dict, score, reasons) sorted by score descending.
    """
    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song)
        scored.append((song, score, reasons))

    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:k]

# ---------------------------------------------------------------------------
# OOP API  (used by tests/test_recommender.py)
# ---------------------------------------------------------------------------

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """

    def __init__(self, songs: List[Song]):
        self.songs = songs

    def _user_dict(self, user: UserProfile) -> Dict:
        return {
            "genre":         user.favorite_genre,
            "mood":          user.favorite_mood,
            "energy":        user.target_energy,
            "likes_acoustic": user.likes_acoustic,
        }

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        user_dict = self._user_dict(user)
        ranked = sorted(
            self.songs,
            key=lambda s: _score(asdict(s), user_dict),
            reverse=True,
        )
        return ranked[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        return _explain(asdict(song), self._user_dict(user))
