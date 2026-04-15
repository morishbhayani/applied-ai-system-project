# 🎵 Music Recommender Simulation

## Project Summary

This project builds a simple content-based music recommender system. The system suggests songs based on a user’s preferences such as genre, mood, energy, and acousticness.

It reads song data from a CSV file, scores each song using a weighted formula, and returns the top recommendations along with explanations. This project demonstrates how recommendation systems can work using simple logic instead of complex machine learning models.

---

## How The System Works

This recommender uses a simple content-based approach to suggest songs based on a user's preferences. In real-world systems, platforms like Spotify use large-scale behavioral data and machine learning models, but this version focuses on a smaller and more interpretable scoring system.

Each song is represented using features such as genre, mood, energy, and acousticness. The user profile stores preferences including favorite genre, preferred mood, target energy level, and whether the user prefers acoustic or electronic music.

The recommender computes a score for each song using a weighted formula. It rewards songs that match the user’s genre and mood, and also gives higher scores to songs whose energy level is closer to the user’s target. Acousticness is used to adjust the score based on whether the user prefers acoustic or electronic sound.

After scoring all songs, the system ranks them from highest to lowest score and returns the top recommendations.

---

### User Profile Design

The user profile is defined using four features: favorite_genre, favorite_mood, target_energy, and likes_acoustic.

This profile works well for distinguishing very different types of music, such as intense rock and chill lofi. However, it is limited when comparing similar genres, and it assumes mood labels are always accurate.

---

### Data Flow Diagram

```mermaid
flowchart TD
    A[User Profile Input] --> B[Load songs from songs.csv]
    B --> C[Loop through each song]
    C --> D[Compute score]
    D --> E[Store score]
    E --> F[Sort songs]
    F --> G[Return Top K]