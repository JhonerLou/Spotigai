🎵 Spotigai: Mood-Based Music Player

Spotigai is a Flask web application that generates personalized music playlists based on your mood and streams them using YouTube. It combines songs from a large dataset with tracks from your own Spotify library to create a unique listening experience.

✨ Overview

Users log in with their Spotify account, select a mood (Happy, Sad, Calm, Energetic), 
choose one of their Spotify playlists, optionally set a year range, and specify 
the desired number of songs. The application then:

1. Loads a pre-processed dataset (`standardized_song_list.csv`) containing songs 
   with mood labels.
2. Fetches tracks from the user's selected Spotify playlist.
3. Filters both datasets based on the selected mood (for the CSV) and year range 
   (for both).
4. Creates a combined playlist, prioritizing songs (~80%) matching the mood from 
   the dataset and supplementing (~20%) with songs from the user's playlist 
   within the year range.
5. Searches YouTube for corresponding music videos for the selected songs.
6. Presents an embedded YouTube player that streams the generated playlist with 
   looping and basic playback controls.


🚀 Features

- Spotify Authentication: Securely log in using Spotify OAuth.
- Mood Selection:       Choose from Happy, Sad, Calm, or Energetic.
- Playlist Integration: Select one of your Spotify playlists to mix in.
- Year Range Filter:    Optionally filter songs by release year.
- Custom Playlist Size: Request between 1 and 50 songs.
- Combined Source:      Uses a large CSV dataset + user's Spotify playlist.
- YouTube Search:       Finds playable YouTube videos for selected tracks.
- Embedded Player:      Streams YouTube videos with Play/Pause/Next/Prev controls, 
                        auto-skipping, looping, and track list display.


🔧 Setup

Prerequisites

- Python 3.7+
- pip (Python package installer)
- Git
- Spotify Developer Account & App Credentials (Client ID, Client Secret)
- Google Cloud Platform Account & YouTube Data API v3 Key


Installation

<details>
<summary>Click to expand Installation steps</summary>

Clone the repository:

git clone https://github.com/JhonerLou/Spotigai.git
cd Spotigai


Create and activate a virtual environment:

# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate


Install dependencies:

pip install -r requirements.txt


(If requirements.txt is missing, create it: pip freeze > requirements.txt)

</details>

Configuration

<details>
<summary>Click to expand Configuration steps</summary>

API Keys:

Spotify: Go to Spotify Dev Dashboard. Create/Select app. Note Client ID & Secret. Add Redirect URI: http://127.0.0.1:8888/callback. Save.

YouTube: Go to Google Cloud Console. Create/Select project. Enable YouTube Data API v3. Create an API Key. Note it.

Environment Variables (.env file):

Create .env in the project root.

Add your keys:

SPOTIPY_CLIENT_ID=YOUR_SPOTIFY_CLIENT_ID_HERE
SPOTIPY_CLIENT_SECRET=YOUR_SPOTIFY_CLIENT_SECRET_HERE
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
YOUTUBE_API_KEY=YOUR_YOUTUBE_API_KEY_HERE
FLASK_SECRET_KEY=generate_a_strong_random_secret_key_here


Replace placeholders. Generate a random string for FLASK_SECRET_KEY.

</details>

Data Preparation

1. Place your raw data (e.g., `full_song_list.csv`) in the project directory.
2. Run the standardization script:
   >>> python standardize_data.py
3. This creates `standardized_song_list.csv`. Check script output for errors.


🚦 Usage

1. Activate your virtual environment.
2. Ensure `standardized_song_list.csv` exists.
3. Run the Flask app:
   >>> python app.py
4. Open browser to http://127.0.0.1:8888/
5. Log in with Spotify.
6. Make selections on the /select page.
7. Click "Generate Playlist".
8. Player page loads and starts playing.

⚠️ Known Issues & Limitations

- YouTube Quota: Daily limit (default 10k units). Searches cost 100 units. Can be 
                 exhausted quickly. Resets midnight PT.
- YouTube Search: Top result might be inaccurate (cover, live, wrong song).
- Video Availability: Found videos might be unavailable/restricted (player attempts auto-skip).
- Spotify API: Relies on mood labels in the dataset; direct audio feature access is 
               deprecated for new apps.


🧩 Dependencies

- Flask
- Spotipy
- python-dotenv
- pandas
- google-api-python-client
- numpy


(Ensure requirements.txt lists these)
