🎵 Spotigai: Mood-Based Music Player

Spotigai is a Flask web application that generates personalized music playlists based on your mood and streams them using YouTube. It combines songs from a large dataset with tracks from your own Spotify library to create a unique listening experience.

✨ Overview

1. Users log in with their Spotify account, select a mood (Happy, Sad, Calm, Energetic), choose one of their Spotify playlists, optionally set a year range, and specify the desired number of songs. The application then:

2. Loads a pre-processed dataset (standardized_song_list.csv) containing songs with mood labels.

3. Fetches tracks from the user's selected Spotify playlist.

4. Filters both datasets based on the selected mood (for the CSV) and year range (for both).

5. Creates a combined playlist, prioritizing songs (~80%) matching the mood from the dataset and supplementing (~20%) with songs from the user's playlist within the year range.

6. Searches YouTube for corresponding music videos for the selected songs.

7. Presents an embedded YouTube player that streams the generated playlist with looping and basic playback controls.

🚀 Features

🔐 Spotify Authentication: Securely log in using your Spotify account via OAuth.

🧐 Mood Selection: Choose from Happy, Sad, Calm, or Energetic.

🧶 Playlist Integration: Select one of your own Spotify playlists to add variety.

📅 Year Range Filtering (Optional): Specify a start and end year to narrow down the song selection.

🔢 Custom Playlist Size: Select how many songs you want (1-50).

🦸🏽 Combined Music Source: Leverages a large external dataset and the user's own music tastes.

🔎 YouTube Video Search: Automatically finds playable YouTube videos.

▶️ Embedded YouTube Player: Streams the playlist with Play/Pause/Next/Previous controls, auto-skipping, looping, and a track list display.

🔧 Setup

Prerequisites

 - Python 3.7+

 - pip (Python package installer)

 - Git

 - Spotify Developer Account & App Credentials

 - Google Cloud Platform Account & YouTube Data API v3 Key

Installation

<details>
<summary>Click to expand Installation steps</summary>

1. Clone the repository:

git clone [https://github.com/JhonerLou/Spotigai.git](https://github.com/JhonerLou/Spotigai.git)
cd Spotigai


2. Create and activate a virtual environment:

# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate


3. Install dependencies:

pip install -r requirements.txt


(If requirements.txt is missing, create it: pip freeze > requirements.txt after installing Flask, Spotipy, python-dotenv, pandas, google-api-python-client, numpy)

</details>

Configuration

<details>
<summary>Click to expand Configuration steps</summary>

1. API Keys:

   - Spotify:

     Go to the Spotify Developer Dashboard.

     Create/Select your app. Note Client ID & Secret.

     Add Redirect URI: http://127.0.0.1:8888/callback

     Save.

   - YouTube:

     Go to the Google Cloud Console.

     Create/Select project. Enable YouTube Data API v3.

     Create an API Key. Note it down.

     Environment Variables (.env file):

2. Create .env in the project root.

   Add your keys:

   SPOTIPY_CLIENT_ID=YOUR_SPOTIFY_CLIENT_ID_HERE
   SPOTIPY_CLIENT_SECRET=YOUR_SPOTIFY_CLIENT_SECRET_HERE
   SPOTIPY_REDIRECT_URI=[http://127.0.0.1:8888/callback](http://127.0.0.1:8888/callback)
   YOUTUBE_API_KEY=YOUR_YOUTUBE_API_KEY_HERE
   FLASK_SECRET_KEY=generate_a_strong_random_secret_key_here


   Replace placeholders. FLASK_SECRET_KEY should be a long, random string.

</details>

Data Preparation

The application requires standardized_song_list.csv.

Place your raw data (e.g., full_song_list.csv) in the project directory.

Run the standardization script:

python standardize_data.py


This creates standardized_song_list.csv. Check the script output for errors or warnings (e.g., if no valid data remains).

🚦 Usage

Activate your virtual environment.

Ensure standardized_song_list.csv exists.

Run the Flask app:

python app.py


Open your browser to http://127.0.0.1:8888/.

Log in with Spotify.

Make your selections on the /select page.

Click "Generate Playlist".

The player page will load and start playing.

📁 File Structure

Spotigai/
│
├── .env                  # Stores API keys and secrets (!! DO NOT COMMIT !!)
├── .gitignore            # Specifies files/folders Git should ignore
├── app.py                # Main Flask application logic
├── standardize_data.py   # Script to clean and prepare the input CSV
├── full_song_list.csv    # Original raw data file (Input for standardize_data.py)
├── standardized_song_list.csv # Cleaned data used by app.py
├── requirements.txt      # List of Python dependencies
│
└── templates/            # HTML templates for Flask
    ├── index.html        # Login page
    ├── select.html       # Selection page (Playlist, Mood, etc.)
    └── player.html       # Page with the YouTube player


⚠️ Known Issues & Limitations

YouTube Quota: Daily limit (default 10,000 units). Searches cost 100 units. Frequent use can exhaust the quota. Resets midnight PT.

YouTube Search Accuracy: Uses title/artist search; top result might be inaccurate.

Video Availability: Found videos might be unavailable/restricted. Player attempts auto-skip.

Spotify API Limitations: Relies on mood labels in the dataset as direct audio feature access is deprecated for new apps.

🧩 Dependencies

Flask

Spotipy

python-dotenv

pandas

google-api-python-client

numpy

(Ensure requirements.txt lists these)
