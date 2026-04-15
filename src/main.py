"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

from src.recommender import load_songs, recommend_songs


def main() -> None:
    songs = load_songs("data/songs.csv")
    print(f"Loaded songs: {len(songs)}\n")

    profiles = {
        "High-Energy Pop": {
            "genre": "pop",
            "mood": "happy",
            "energy": 0.8,
            "likes_acoustic": False,
        },
        "Chill Lofi": {
            "genre": "lofi",
            "mood": "chill",
            "energy": 0.3,
            "likes_acoustic": True,
        },
        "Deep Intense Rock": {
            "genre": "rock",
            "mood": "intense",
            "energy": 0.9,
            "likes_acoustic": False,
        },
        "Edge Case - Sad but High Energy": {
            "genre": "rock",
            "mood": "sad",
            "energy": 0.9,
            "likes_acoustic": False,
        },
    }

    for profile_name, user_prefs in profiles.items():
        recommendations = recommend_songs(user_prefs, songs, k=5)

        print(f"=== {profile_name} ===\n")
        for song, score, reasons in recommendations:
            print(f"{song['title']} - Score: {score:.2f}")
            print("Reasons:")
            for reason in reasons:
                print(f"  - {reason}")
            print()


if __name__ == "__main__":
    main()