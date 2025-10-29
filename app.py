import os
import time
import pandas as pd # Import pandas
from flask import Flask, redirect, request, session, render_template, url_for, jsonify
import spotipy
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import datetime
import random
import math # Import math for ceiling function
import numpy as np # Import numpy for NaN comparison

# --- CONFIGURATION ---
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_default_secret_key")

# Spotify Credentials
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

# YouTube API Key
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Scopes needed for Spotify OAuth (Required for login flow and reading playlists)
SCOPE = "playlist-read-private user-library-read"

# Available Moods for Mood Generation feature
AVAILABLE_MOODS = ["Happy", "Sad", "Calm", "Energetic"]

# --- CSV Dataset Path ---
EXTERNAL_CSV_PATH = 'standardized_song_list.csv' # Use the standardized CSV


# --- HELPER FUNCTIONS ---
# (get_spotify_oauth, get_token, search_youtube remain the same)
def get_spotify_oauth():
    """Creates a SpotifyOAuth instance."""
    return SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE,
        cache_path=".spotify_cache-" + session.get('uuid', 'default') # Session-specific cache
    )

def get_token():
    """Checks for and refreshes the Spotify token."""
    token_info = session.get('token_info', None)
    if not token_info: return None
    now = int(time.time())
    is_expired = token_info.get('expires_at', 0) - now < 60
    if is_expired:
        try:
            sp_oauth = get_spotify_oauth()
            refresh_token = token_info.get('refresh_token')
            if refresh_token:
                 token_info = sp_oauth.refresh_access_token(refresh_token)
                 session['token_info'] = token_info
                 print("Spotify token refreshed.")
            else:
                 session.pop('token_info', None); session.pop('uuid', None)
                 print("No refresh token found. User needs to re-authenticate.")
                 return None
        except Exception as e:
            print(f"Error refreshing token: {e}. User needs to re-authenticate.")
            session.pop('token_info', None); session.pop('uuid', None)
            return None
    return token_info

def search_youtube(query, max_results=1):
    """Searches YouTube and returns the top video ID and title."""
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "YOUR_API_KEY_HERE":
        print("❌ ERROR: YouTube API key missing or invalid.")
        return None
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        search_response = youtube.search().list(
            q=query,
            part='id,snippet',
            maxResults=max_results,
            type='video',
            videoEmbeddable='true' # Try to find videos that can be embedded
        ).execute()
        results = search_response.get('items', [])
        if results:
            return {'id': results[0]['id']['videoId'], 'title': results[0]['snippet']['title']}
        else:
            return None
    except HttpError as e:
        print(f"DEBUG: YouTube API HttpError: Status {e.resp.status}, Reason: {e.reason}")
        raise e
    except Exception as e:
        print(f"❌ Unexpected YouTube search error: {e}")
        return None

# (get_playlist_tracks remains the same)
def get_playlist_tracks(sp, playlist_id):
    """Fetches all tracks from a Spotify playlist, handling pagination."""
    tracks_data = []
    offset = 0
    limit = 50 # Max limit per request
    total_tracks = None # Store total number later

    print(f"Fetching tracks for Spotify playlist ID: {playlist_id}")
    while True:
        try:
            fields = 'items(track(id,name,artists(name),album(release_date,release_date_precision),is_local)),next,offset,total' # Added is_local
            results = sp.playlist_items(playlist_id, fields=fields, limit=limit, offset=offset, additional_types=['track']) # Ensure we only get tracks

            if results is None: break
            if total_tracks is None: total_tracks = results.get('total', 0)
            items = results.get('items', [])
            if not items: break

            tracks_data.extend(items)
            print(f"Fetched {len(tracks_data)}/{total_tracks if total_tracks is not None else '?'} tracks...")

            if results.get('next'): offset += limit
            else: print("Reached end of playlist."); break

        except spotipy.SpotifyException as e: print(f"Spotify API error fetching playlist items (offset {offset}): {e}"); break
        except Exception as e: print(f"Unexpected error fetching playlist items: {e}"); break

    print(f"Finished fetching. Total items received: {len(tracks_data)}")
    processed_tracks = []
    processed_ids = set()
    for item in tracks_data:
        track = item.get('track')
        if (not track or not isinstance(track, dict) or not track.get('id') or
            not track.get('name') or not track.get('artists') or track.get('is_local')): # Skip local tracks
            # print("Skipping invalid or local track item:", item.get('track', {}).get('name', 'N/A'))
            continue

        track_id = track['id']
        if track_id in processed_ids: continue
        processed_ids.add(track_id)

        album_info = track.get('album', {})
        release_date = album_info.get('release_date', '')
        release_precision = album_info.get('release_date_precision', '')
        year = None
        if release_date:
            try:
                if release_precision == 'year' and len(release_date) == 4: year = int(release_date)
                elif release_precision in ['month', 'day'] and len(release_date) >= 4: year = int(release_date.split('-')[0])
            except (ValueError, IndexError, TypeError): year = None

        artist_name = 'Unknown Artist'
        if track.get('artists') and isinstance(track['artists'], list) and len(track['artists']) > 0:
            artist_name = track['artists'][0].get('name', 'Unknown Artist')

        processed_tracks.append({
            'id': track_id,
            'name': track.get('name', 'Unknown Track'),
            'artist': artist_name,
            'year': year,
            'source': 'spotify_playlist',
            'mood': None
        })
    print(f"Processed {len(processed_tracks)} valid, unique, non-local tracks from Spotify playlist.")
    return processed_tracks

# (load_csv_tracks remains the same)
def load_csv_tracks(csv_path):
    """Loads tracks from the standardized CSV file."""
    if not os.path.exists(csv_path):
        print(f"❌ ERROR: Standardized CSV file not found at '{csv_path}'.")
        return None
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        print(f"Loaded {len(df)} tracks from standardized CSV '{csv_path}'.")
        expected_cols = ['track_id', 'track_name', 'artist_name', 'Mood', 'year']
        if not all(col in df.columns for col in expected_cols):
             missing = [col for col in expected_cols if col not in df.columns]
             print(f"❌ ERROR: Standardized CSV missing expected columns: {', '.join(missing)}")
             return None
        df['year'] = pd.to_numeric(df['year'], errors='coerce')
        df['Mood'] = df['Mood'].astype(str).str.strip().replace(['nan', 'NaN','None', ''], pd.NA, regex=False)
        df['track_id'] = df['track_id'].astype(str).str.strip().replace(['nan', 'NaN', 'None', ''], pd.NA, regex=False)
        df['track_name'] = df['track_name'].astype(str).str.strip().replace(['nan', 'NaN', 'None', ''], pd.NA, regex=False)
        df['artist_name'] = df['artist_name'].astype(str).str.strip().replace(['nan', 'NaN','None', ''], pd.NA, regex=False)
        initial_rows = len(df)
        df.dropna(subset=['Mood', 'track_id', 'track_name', 'artist_name'], inplace=True)
        print(f"Dropped {initial_rows - len(df)} rows due to missing critical data.")
        print(f"DataFrame shape after cleaning and dropping NA: {df.shape}")
        if df.empty: print("❌ Warning: DataFrame empty after cleaning."); return df
        print(f"Found unique mood labels in standardized CSV: {list(df['Mood'].unique())}")
        return df
    except Exception as e:
        print(f"❌ ERROR: Failed to load or process standardized CSV file '{csv_path}'. {e}")
        import traceback; traceback.print_exc(); return None


# --- FLASK ROUTES ---
# (/, /login, /logout, /callback remain the same)
@app.route('/')
def index():
    token_info = get_token()
    if not token_info:
         if 'uuid' not in session: session['uuid'] = os.urandom(16).hex()
         return render_template('index.html')
    else: return redirect(url_for('select_options'))

@app.route('/login')
def login():
    if 'uuid' not in session: session['uuid'] = os.urandom(16).hex()
    session.pop('token_info', None)
    sp_oauth = get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    print(f"Redirecting to Spotify auth URL: {auth_url}")
    return redirect(auth_url)

@app.route('/logout')
def logout():
    uuid = session.get('uuid', None)
    cache_file = f".spotify_cache-{uuid}" if uuid else None
    session.clear()
    if cache_file and os.path.exists(cache_file):
        try: os.remove(cache_file); print(f"Removed Spotipy cache file: {cache_file}")
        except OSError as e: print(f"Warning: Could not remove cache file {cache_file}. Error: {e}")
    print("User logged out.")
    return redirect(url_for('index'))

@app.route('/callback')
def callback():
    sp_oauth = get_spotify_oauth()
    code = request.args.get('code')
    error = request.args.get('error')
    if error: print(f"Error received from Spotify callback: {error}"); return f"Authentication failed: {error}.", 400
    if not code: print("No authorization code received in callback."); return "Authentication failed: No code.", 400
    try:
        token_info = sp_oauth.get_access_token(code, check_cache=False)
        session['token_info'] = token_info
        print("Successfully obtained and stored Spotify token.")
        return redirect(url_for('select_options')) # Redirect to mood selection after login
    except Exception as e: print(f"Error getting access token from Spotify: {e}"); return "Failed to get access token.", 500

# (select_options remains mostly the same, fetches playlists)
@app.route('/select')
def select_options():
    token_info = get_token()
    if not token_info: return redirect(url_for('login'))
    username = "User"; user_playlists = []
    try:
        sp = Spotify(auth=token_info['access_token'])
        user_profile = sp.current_user()
        username = user_profile.get('display_name', 'User')
        user_playlists_data = sp.current_user_playlists(limit=50)
        user_playlists = user_playlists_data.get('items', [])
        print(f"Fetched {len(user_playlists)} playlists for user {username}.")
    except spotipy.SpotifyException as e:
        print(f"Spotify API error fetching user data: {e}")
        if e.http_status in [401, 403]: return redirect(url_for('logout'))
        return "Error communicating with Spotify.", 500
    except Exception as e: print(f"Warning: Could not fetch Spotify user data. Error: {e}")
    # Render select.html for mood playlist generation
    return render_template('select.html',
                           moods=AVAILABLE_MOODS,
                           username=username,
                           playlists=user_playlists) # Pass playlists for the 20% mix

# (/generate remains mostly the same - uses 80/20 split)
@app.route('/generate', methods=['POST'])
def generate_playlist():
    token_info = get_token()
    if not token_info: return render_template('mood_player.html', video_ids_json='[]', track_names_json='[]', error="Your session has expired. Please log in again."), 401

    selected_playlist_id = request.form.get('playlist_id')
    selected_mood_label = request.form.get('mood')
    try:
        num_songs_str = request.form.get('num_songs', '20')
        num_songs = min(max(1, int(num_songs_str)), 50)
    except (TypeError, ValueError): return "Invalid number of songs provided.", 400

    if not selected_mood_label or not selected_playlist_id: return "Missing Mood or Playlist selection.", 400

    print(f"Generating MOOD playlist for Mood: {selected_mood_label}, Target Songs: {num_songs}, From Playlist: {selected_playlist_id}")

    try:
        # Load CSV
        csv_df = load_csv_tracks(EXTERNAL_CSV_PATH)
        if csv_df is None or csv_df.empty: return render_template('mood_player.html', video_ids_json='[]', track_names_json='[]', error=f"Could not load valid track data.")

        # Filter CSV by mood
        mood_filter = csv_df['Mood'].str.lower() == selected_mood_label.strip().lower()
        filtered_csv_df = csv_df.loc[mood_filter].copy()
        print(f"Found {len(filtered_csv_df)} tracks in CSV matching mood criteria.")

        # Fetch User Playlist Tracks
        sp = Spotify(auth=token_info['access_token'])
        playlist_tracks_list = get_playlist_tracks(sp, selected_playlist_id)
        print(f"Found {len(playlist_tracks_list)} total tracks in the selected Spotify playlist.")

        # Convert filtered DataFrame rows to list of dicts
        filtered_csv_tracks_list = []
        for _, row in filtered_csv_df.iterrows():
            filtered_csv_tracks_list.append({ 'id': row['track_id'], 'name': row['track_name'], 'artist': row['artist_name'], 'mood': row['Mood'], 'source': 'csv_dataset' })

        # Combine Tracks with Ratio
        num_csv_target = math.ceil(num_songs * 0.8)
        num_playlist_target = num_songs - num_csv_target
        selected_csv = random.sample(filtered_csv_tracks_list, min(len(filtered_csv_tracks_list), num_csv_target))
        selected_playlist = random.sample(playlist_tracks_list, min(len(playlist_tracks_list), num_playlist_target)) if isinstance(playlist_tracks_list, list) else []
        combined_selection = selected_csv + selected_playlist

        # Deduplicate and Shuffle
        final_selection_dict = {}
        for track in combined_selection:
            track_id = track.get('id')
            if track_id:
                if track_id not in final_selection_dict or track.get('source') == 'csv_dataset': final_selection_dict[track_id] = track
        selected_tracks = list(final_selection_dict.values())
        random.shuffle(selected_tracks)
        print(f"Final selected count for mood playlist: {len(selected_tracks)}")

        if not selected_tracks: return render_template('mood_player.html', video_ids_json='[]', track_names_json='[]', error=f"No tracks found matching criteria.")

        # --- Iterative YouTube Search --- (Remains the same logic)
        print(f"\nSearching YouTube iteratively...")
        youtube_video_ids = []; final_track_names = []; youtube_titles = []
        processed_track_ids_yt = set(); search_candidates = selected_tracks[:]
        youtube_search_attempts = 0; max_youtube_attempts = len(selected_tracks) + 10
        quota_exceeded = False; target_yt_videos = len(selected_tracks)

        while len(youtube_video_ids) < target_yt_videos and search_candidates and youtube_search_attempts < max_youtube_attempts:
            youtube_search_attempts += 1; current_track = search_candidates.pop(0)
            track_id = current_track.get('id'); artist = current_track.get('artist', 'N/A'); name = current_track.get('name', 'N/A')
            if not track_id or not name or not artist or track_id in processed_track_ids_yt: continue
            processed_track_ids_yt.add(track_id)
            query = f"{artist} - {name} official audio video lyrics"
            print(f"  Attempt {youtube_search_attempts}: Searching '{query}'")
            video_info = None
            try:
                video_info = search_youtube(query)
                if video_info:
                    youtube_video_ids.append(video_info['id']); final_track_names.append(f"{artist} - {name}"); youtube_titles.append(video_info['title'])
                    print(f"    -> SUCCESS [{len(youtube_video_ids)} found]")
                else: print(f"    -> FAILED: Video not found.")
            except HttpError as e:
                 if e.resp.status == 403: print("🛑 YouTube Quota likely exceeded."); quota_exceeded = True; break
                 else: print(f"  - YouTube HTTP Error: {e}")
            except Exception as e: print(f"  - Unexpected YT search error: {e}")
            time.sleep(0.1)
        # --- End Search ---

        found_videos_count = len(youtube_video_ids)
        print(f"\nFinished YouTube search. Found {found_videos_count} videos.")
        if quota_exceeded: print("Warning: YouTube quota likely exceeded.")
        if not youtube_video_ids: return render_template('mood_player.html', video_ids_json='[]', track_names_json='[]', error="Could not find YouTube videos.")

        # --- Render Mood Player ---
        video_ids_json = jsonify(youtube_video_ids).get_data(as_text=True)
        track_names_json = jsonify(final_track_names).get_data(as_text=True)
        youtube_titles_json = jsonify(youtube_titles).get_data(as_text=True)
        # --- UPDATE: Render mood_player.html ---
        return render_template('mood_player.html', video_ids_json=video_ids_json, track_names_json=track_names_json, youtube_titles_json=youtube_titles_json)
        # --- End Update ---

    except spotipy.SpotifyException as e:
         print(f"Spotify API error during mood generation: {e}")
         if e.http_status in [401, 403]: return redirect(url_for('logout'))
         return render_template('mood_player.html', video_ids_json='[]', track_names_json='[]', error=f"Spotify error: {e.msg}")
    except Exception as e:
        print(f"Unexpected error in /generate: {e}")
        import traceback; traceback.print_exc()
        return render_template('mood_player.html', video_ids_json='[]', track_names_json='[]', error="Unexpected server error.")


# --- Route to browse user's playlists ---
@app.route('/browse', endpoint='browse_playlists') # Explicit endpoint name
def browse_playlists():
    token_info = get_token()
    if not token_info: return redirect(url_for('login'))
    username = "User"; user_playlists = []
    try:
        sp = Spotify(auth=token_info['access_token'])
        user_profile = sp.current_user()
        username = user_profile.get('display_name', 'User')
        user_playlists_data = sp.current_user_playlists(limit=50)
        user_playlists = user_playlists_data.get('items', [])
        print(f"Fetched {len(user_playlists)} playlists for browsing page.")
        # --- Render browse.html ---
        return render_template('browse.html', playlists=user_playlists, username=username)
    except spotipy.SpotifyException as e:
        print(f"Spotify API error browsing playlists: {e}")
        if e.http_status in [401, 403]: return redirect(url_for('logout'))
        return "Error fetching Spotify playlists.", 500
    except Exception as e:
        print(f"Unexpected error browsing playlists: {e}")
        return "An unexpected error occurred.", 500


# --- Route to play a specific Spotify playlist ---
@app.route('/play_playlist/<playlist_id>')
def play_playlist(playlist_id):
    token_info = get_token()
    if not token_info: return redirect(url_for('login'))

    print(f"Request received to play Spotify playlist ID: {playlist_id}")
    playlist_title = f"Spotify Playlist" # Default title

    try:
        sp = Spotify(auth=token_info['access_token'])

        # Get playlist details for the title
        try:
            playlist_details = sp.playlist(playlist_id, fields='name')
            playlist_title = playlist_details.get('name', playlist_title)
        except spotipy.SpotifyException as e:
             print(f"Warning: Could not fetch playlist name for {playlist_id}. Error: {e}")


        # Fetch all tracks from the selected playlist
        selected_tracks = get_playlist_tracks(sp, playlist_id)

        if not selected_tracks:
            # --- UPDATE: Render playlist_player.html with error ---
            return render_template('playlist_player.html', video_ids_json='[]', track_names_json='[]', playlist_title=playlist_title, error=f"Could not find any playable tracks in the selected Spotify playlist.")

        # --- Iterative YouTube Search for Playlist Tracks ---
        print(f"\nSearching YouTube iteratively for {len(selected_tracks)} playlist tracks...")
        youtube_video_ids = []; final_track_names = []; youtube_titles = []
        processed_track_ids_yt = set(); search_candidates = selected_tracks[:] # Use the fetched tracks
        # No need to shuffle playlist tracks, keep original order
        youtube_search_attempts = 0; max_youtube_attempts = len(selected_tracks) + 10
        quota_exceeded = False; target_yt_videos = len(selected_tracks)

        while len(youtube_video_ids) < target_yt_videos and search_candidates and youtube_search_attempts < max_youtube_attempts:
            # (Search logic is identical to /generate route)
            youtube_search_attempts += 1; current_track = search_candidates.pop(0)
            track_id = current_track.get('id'); artist = current_track.get('artist', 'N/A'); name = current_track.get('name', 'N/A')
            if not track_id or not name or not artist or track_id in processed_track_ids_yt: continue
            processed_track_ids_yt.add(track_id)
            query = f"{artist} - {name} official audio video lyrics"
            print(f"  Attempt {youtube_search_attempts}: Searching '{query}'")
            video_info = None
            try:
                video_info = search_youtube(query)
                if video_info:
                    youtube_video_ids.append(video_info['id']); final_track_names.append(f"{artist} - {name}"); youtube_titles.append(video_info['title'])
                    print(f"    -> SUCCESS [{len(youtube_video_ids)} found]")
                else: print(f"    -> FAILED: Video not found.")
            except HttpError as e:
                 if e.resp.status == 403: print("🛑 YouTube Quota likely exceeded."); quota_exceeded = True; break
                 else: print(f"  - YouTube HTTP Error: {e}")
            except Exception as e: print(f"  - Unexpected YT search error: {e}")
            time.sleep(0.1)
        # --- End Search ---

        found_videos_count = len(youtube_video_ids)
        print(f"\nFinished YouTube search for playlist. Found {found_videos_count} videos.")
        if quota_exceeded: print("Warning: YouTube quota likely exceeded during playlist search.")

        if not youtube_video_ids:
            # --- UPDATE: Render playlist_player.html with error ---
             return render_template('playlist_player.html', video_ids_json='[]', track_names_json='[]', playlist_title=playlist_title, error="Found Spotify tracks, but couldn't find any matching YouTube videos.")

        # --- Render Playlist Player ---
        video_ids_json = jsonify(youtube_video_ids).get_data(as_text=True)
        track_names_json = jsonify(final_track_names).get_data(as_text=True)
        youtube_titles_json = jsonify(youtube_titles).get_data(as_text=True)
        # --- UPDATE: Render playlist_player.html ---
        return render_template('playlist_player.html',
                               video_ids_json=video_ids_json,
                               track_names_json=track_names_json,
                               youtube_titles_json=youtube_titles_json,
                               playlist_title=playlist_title) # Pass playlist title
        # --- End Update ---

    except spotipy.SpotifyException as e:
         print(f"Spotify API error playing playlist {playlist_id}: {e}")
         if e.http_status in [401, 403]: return redirect(url_for('logout'))
         # --- UPDATE: Render playlist_player.html with error ---
         return render_template('playlist_player.html', video_ids_json='[]', track_names_json='[]', playlist_title=playlist_title, error=f"Spotify error: {e.msg}")
    except Exception as e:
        print(f"Unexpected error playing playlist {playlist_id}: {e}")
        import traceback; traceback.print_exc()
        # --- UPDATE: Render playlist_player.html with error ---
        return render_template('playlist_player.html', video_ids_json='[]', track_names_json='[]', playlist_title=playlist_title, error="Unexpected server error.")


# --- Error Handlers & Run ---
@app.errorhandler(404)
def page_not_found(e):
    print(f"404 Error: {request.url}")
    return "Page not found.", 404 # Return simple text

@app.errorhandler(500)
def internal_server_error(e):
    print(f"Server Error: {e}")
    import traceback; traceback.print_exc()
    error_message = f"Internal server error: {e}" if app.debug else "Internal server error."
    return error_message, 500

if __name__ == '__main__':
    # (Startup checks remain the same)
    if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET: print("🚨 CRITICAL ERROR: Spotify client ID or secret missing."); exit(1)
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "YOUR_API_KEY_HERE": print("🚨 CRITICAL ERROR: YouTube API key missing."); exit(1)
    templates_dir = 'templates'
    if not os.path.exists(templates_dir):
         try: os.makedirs(templates_dir); print(f"Created '{templates_dir}' directory.")
         except OSError as e: print(f"🚨 ERROR: Could not create templates directory '{templates_dir}'. {e}"); exit(1)
    # Check for essential templates
    # --- UPDATE: Check for mood_player.html, playlist_player.html, browse.html ---
    for tpl in ['index.html', 'select.html', 'mood_player.html', 'playlist_player.html', 'browse.html']:
        if not os.path.exists(os.path.join(templates_dir, tpl)): print(f"🚨 WARNING: Template '{tpl}' not found.")
    # --- End Update ---
    if not os.path.exists(EXTERNAL_CSV_PATH): print(f"🚨 CRITICAL ERROR: CSV file '{EXTERNAL_CSV_PATH}' not found."); exit(1)
    else: print(f"Found standardized CSV file at '{EXTERNAL_CSV_PATH}'.")

    print("\nStarting Flask app...")
    app.run(debug=True, port=8888, host='127.0.0.1')

