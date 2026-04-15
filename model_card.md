# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  

VibeFinder 1.0  

---

## 2. Intended Use  

This recommender suggests songs based on a user’s preferences such as genre, mood, and energy level. It assumes that users have clear preferences and that these preferences can be represented using simple features. This system is designed for classroom exploration and learning purposes, not for real-world deployment.

---

## 3. How the Model Works  

The model uses a simple scoring system to rank songs based on how well they match user preferences. Each song has features such as genre, mood, energy, and acousticness. The user profile contains preferred values for these features.

The model gives points when the song matches the user’s genre and mood. It also gives higher scores to songs whose energy level is closer to the user’s target energy. Acousticness is used to adjust whether the song fits the user’s preference for acoustic or electronic sound.

All songs are scored individually, and then sorted from highest to lowest score. The top songs are returned as recommendations. Compared to the starter logic, this version uses weighted scoring and provides explanations for each recommendation.

---

## 4. Data  

The dataset contains 18 songs with features such as genre, mood, energy, tempo, and acousticness. It includes a variety of genres like pop, lofi, rock, jazz, EDM, and classical, along with moods such as happy, chill, intense, sad, and romantic.

Additional songs were added to increase diversity and improve coverage across energy levels and moods. However, the dataset is still small and does not fully represent all types of music or user preferences.

---

## 5. Strengths  

The system works well for users with clear and consistent preferences. For example, the High-Energy Pop and Chill Lofi profiles produced recommendations that closely matched expectations.

The scoring system captures important patterns such as matching genre, mood, and energy level. In many cases, the top recommendations aligned well with intuitive expectations, showing that the model can correctly prioritize relevant features.

---

## 6. Limitations and Bias  

This recommender can create filter bubbles because it gives strong weight to exact genre and mood matches. As a result, songs from related genres may be ignored even if they are otherwise a good fit for the user. The system also struggles with conflicting profiles, such as users who want both high energy and sad mood, because it can only balance the signals rather than understand the context. Another limitation is the small dataset, which reduces variety and makes some recommendations repetitive. These weaknesses show that the model is useful for simple matching, but not for nuanced real-world music taste.

---

## 7. Evaluation  

The system was tested using four user profiles: High-Energy Pop, Chill Lofi, Deep Intense Rock, and an edge case profile with sad mood but high energy. In general, the top-ranked songs matched expectations for the first three profiles. For example, Sunrise City ranked first for High-Energy Pop, Library Rain ranked first for Chill Lofi, and Storm Runner ranked first for Deep Intense Rock.

One surprising result was that Gym Hero ranked highly for multiple profiles, even when the genre did not fully match. This happened because the current scoring system gives strong importance to energy and mood, so a song can still rank high if those features align well. The edge case profile also showed that conflicting preferences can produce mixed recommendations rather than one clearly correct answer.

---

## 8. Future Work  

- Add more songs to increase diversity and reduce repetition  
- Include additional features such as lyrics or artist similarity  
- Improve handling of conflicting user preferences  
- Introduce diversity constraints to avoid recommending similar songs repeatedly  

---

## 9. Personal Reflection  

This project showed how simple data and scoring rules can be used to build a recommender system. It was interesting to see how changing weights or user preferences directly affected the results. One unexpected finding was how strongly energy and mood influenced rankings, sometimes even more than genre. This project helped in understanding that real-world recommendation systems are more complex and must handle much more nuanced user behavior.