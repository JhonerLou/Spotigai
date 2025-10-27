import os
import time
import pandas as pd # Import pandas
from flask import Flask, redirect, request, session, render_template, url_for, jsonify
# --- FIX: Ensure spotipy is explicitly imported for exception handling ---
import spotipy
# --- End FIX ---
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

# Scopes needed for Spotify OAuth (Required for login flow)
SCOPE = "playlist-read-private user-library-read"

# Available Moods
AVAILABLE_MOODS = ["Happy", "Sad", "Calm", "Energetic"]

# --- CSV Dataset Path ---
EXTERNAL_CSV_PATH = 'standardized_song_list.csv' # Use the standardized CSV


# --- HELPER FUNCTIONS ---
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
                 # If no refresh token, clear session and force re-login
                 session.pop('token_info', None); session.pop('uuid', None)
                 print("No refresh token found. User needs to re-authenticate.")
                 return None
        except Exception as e:
            # If refresh fails, clear session and force re-login
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
        # Re-raise HttpError to be caught specifically in the main loop
        print(f"DEBUG: YouTube API HttpError: Status {e.resp.status}, Reason: {e.reason}")
        raise e
    except Exception as e:
        print(f"❌ Unexpected YouTube search error: {e}")
        return None

# --- FIX: Re-add get_playlist_tracks function ---
def get_playlist_tracks(sp, playlist_id):
    """Fetches all tracks from a Spotify playlist, handling pagination."""
    tracks_data = []
    offset = 0
    limit = 50 # Max limit per request
    total_tracks = None # Store total number later

    print(f"Fetching tracks for Spotify playlist ID: {playlist_id}")
    while True:
        try:
            # Request specific fields to minimize data transfer
            fields = 'items(track(id,name,artists(name),album(release_date,release_date_precision))),next,offset,total'
            results = sp.playlist_items(playlist_id, fields=fields, limit=limit, offset=offset)

            if total_tracks is None: # Get total on first request
                total_tracks = results.get('total', 0)

            items = results.get('items', [])
            if not items:
                print("No more items found in playlist.")
                break # Exit loop if no items are returned

            tracks_data.extend(items)
            print(f"Fetched {len(tracks_data)}/{total_tracks if total_tracks is not None else '?'} tracks...")

            if results.get('next'):
                offset += limit # Prepare for the next batch
            else:
                print("Reached end of playlist.")
                break # Exit loop if there's no next page

        except spotipy.SpotifyException as e:
            print(f"Spotify API error fetching playlist items (offset {offset}): {e}")
            # Depending on the error (e.g., rate limit), you might want to wait and retry
            break # Stop fetching for this playlist on error
        except Exception as e:
            print(f"Unexpected error fetching playlist items: {e}")
            break # Stop fetching on unexpected errors

    print(f"Finished fetching. Total items received: {len(tracks_data)}")

    # Process the received track data
    processed_tracks = []
    processed_ids = set() # To avoid duplicates within the playlist itself
    for item in tracks_data:
        track = item.get('track')
        # Basic validation for track data
        if not track or not isinstance(track, dict) or not track.get('id'):
            print("Skipping invalid track item:", item)
            continue

        track_id = track['id']
        # Skip if already processed (duplicate in playlist)
        if track_id in processed_ids:
            continue
        processed_ids.add(track_id)

        # Extract year safely
        album_info = track.get('album', {})
        release_date = album_info.get('release_date', '')
        release_precision = album_info.get('release_date_precision', '')
        year = None
        if release_date:
            try:
                if release_precision == 'year' and len(release_date) == 4:
                    year = int(release_date)
                elif release_precision in ['month', 'day'] and len(release_date) >= 4:
                    year = int(release_date.split('-')[0])
                # Add handling for potentially malformed dates if necessary
            except (ValueError, IndexError, TypeError):
                print(f"Warning: Could not parse year from release_date '{release_date}' with precision '{release_precision}' for track {track_id}")
                year = None # Ensure year is None if parsing fails

        # Extract artist name safely
        artist_name = 'Unknown Artist'
        if track.get('artists') and isinstance(track['artists'], list) and len(track['artists']) > 0:
            artist_name = track['artists'][0].get('name', 'Unknown Artist')

        processed_tracks.append({
            'id': track_id,
            'name': track.get('name', 'Unknown Track'),
            'artist': artist_name,
            'year': year,
            'source': 'spotify_playlist', # Identify the source
            'mood': None # Mood is not available directly from playlist items
        })
    print(f"Processed {len(processed_tracks)} valid, unique tracks from Spotify playlist.")
    return processed_tracks
# --- End FIX ---


def load_csv_tracks(csv_path):
    """Loads tracks from the standardized CSV file."""
    if not os.path.exists(csv_path):
        print(f"❌ ERROR: Standardized CSV file not found at '{csv_path}'.")
        return None
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        print(f"Loaded {len(df)} tracks from standardized CSV '{csv_path}'.")

        # Define the expected standard columns
        expected_cols = ['track_id', 'track_name', 'artist_name', 'Mood', 'year']

        # Verify required columns exist
        if not all(col in df.columns for col in expected_cols):
             missing = [col for col in expected_cols if col not in df.columns]
             print(f"❌ ERROR: Standardized CSV missing expected columns: {', '.join(missing)}")
             print(f"   Available columns: {', '.join(df.columns)}")
             return None # Return None if essential columns are missing

        # --- Data Type Conversion and Cleaning ---
        # Ensure year is numeric (allow NA) - convert to float first
        df['year'] = pd.to_numeric(df['year'], errors='coerce')
        # Ensure mood is string and stripped
        df['Mood'] = df['Mood'].astype(str).str.strip()
        # Replace empty strings/common NA representations in Mood with proper NA
        df['Mood'] = df['Mood'].replace(['nan', 'NaN','None', ''], pd.NA, regex=False)
        # Clean other essential columns just in case
        df['track_id'] = df['track_id'].astype(str).str.strip().replace(['nan', 'NaN', 'None', ''], pd.NA, regex=False)
        df['track_name'] = df['track_name'].astype(str).str.strip().replace(['nan', 'NaN', 'None', ''], pd.NA, regex=False)
        df['artist_name'] = df['artist_name'].astype(str).str.strip().replace(['nan', 'NaN','None', ''], pd.NA, regex=False)

        # Drop rows where mood or other critical identifiers are NA *after* cleaning
        initial_rows = len(df)
        df.dropna(subset=['Mood', 'track_id', 'track_name', 'artist_name'], inplace=True)
        print(f"Dropped {initial_rows - len(df)} rows due to missing critical data.")
        print(f"DataFrame shape after cleaning and dropping NA: {df.shape}")


        if df.empty:
            print("❌ Warning: DataFrame empty after cleaning.")
            return df # Return empty df

        print(f"Found unique mood labels in standardized CSV: {list(df['Mood'].unique())}")
        return df # Return DataFrame

    except Exception as e:
        print(f"❌ ERROR: Failed to load or process standardized CSV file '{csv_path}'. {e}")
        import traceback; traceback.print_exc()
        return None


# --- FLASK ROUTES ---
@app.route('/')
def index():
    token_info = get_token()
    if not token_info:
         if 'uuid' not in session: session['uuid'] = os.urandom(16).hex()
         # Render index.html which should contain the login button
         return render_template('index.html')
    else:
        # If already logged in, redirect to the selection page
        return redirect(url_for('select_options'))

@app.route('/login')
def login():
    if 'uuid' not in session: session['uuid'] = os.urandom(16).hex()
    # Clear previous token info before starting auth flow
    session.pop('token_info', None)
    sp_oauth = get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    print(f"Redirecting to Spotify auth URL: {auth_url}")
    return redirect(auth_url)

@app.route('/logout')
def logout():
    uuid = session.get('uuid', None)
    cache_file = f".spotify_cache-{uuid}" if uuid else None
    session.clear() # Clear Flask session
    # Attempt to remove the specific Spotipy cache file
    if cache_file and os.path.exists(cache_file):
        try:
            os.remove(cache_file)
            print(f"Removed Spotipy cache file: {cache_file}")
        except OSError as e:
            print(f"Warning: Could not remove cache file {cache_file}. Error: {e}")
    print("User logged out.")
    return redirect(url_for('index')) # Redirect to home page after logout

@app.route('/callback')
def callback():
    sp_oauth = get_spotify_oauth()
    code = request.args.get('code')
    error = request.args.get('error')

    # Handle potential errors from Spotify in the callback
    if error:
        print(f"Error received from Spotify callback: {error}")
        return f"Authentication failed: {error}. Please try logging in again.", 400
    if not code:
        print("No authorization code received in callback.")
        return "Authentication failed: No code received. Please try logging in again.", 400

    try:
        # Exchange the code for an access token
        token_info = sp_oauth.get_access_token(code, check_cache=False)
        session['token_info'] = token_info # Store token info in session
        print("Successfully obtained and stored Spotify token.")
        # Redirect to the main selection page after successful login
        return redirect(url_for('select_options'))
    except Exception as e:
        print(f"Error getting access token from Spotify: {e}")
        return "Failed to get access token. Please try logging in again.", 500

@app.route('/select')
def select_options():
    token_info = get_token()
    if not token_info:
        print("No valid token found in session, redirecting to login.")
        return redirect(url_for('login')) # Redirect to login if token is invalid/missing

    username = "User" # Default username
    user_playlists = [] # Default empty list
    try:
        sp = Spotify(auth=token_info['access_token'])
        user_profile = sp.current_user()
        username = user_profile.get('display_name', 'User')

        # Fetch user's playlists
        user_playlists_data = sp.current_user_playlists(limit=50) # Fetch up to 50 playlists
        user_playlists = user_playlists_data.get('items', [])
        print(f"Fetched {len(user_playlists)} playlists for user {username}.")

    except spotipy.SpotifyException as e: # Use imported spotipy here
        # Handle Spotify specific errors like invalid token
        print(f"Spotify API error fetching user data: {e}")
        if e.http_status in [401, 403]:
            print("Spotify token invalid or expired. Redirecting to logout.")
            return redirect(url_for('logout')) # Force re-login if token fails
        # For other Spotify errors, maybe show an error page or message
        return "Error communicating with Spotify. Please try again later.", 500
    except Exception as e:
        # Handle other potential errors (network issues, etc.)
        print(f"Warning: Could not fetch Spotify user data. Error: {e}")
        # Allow rendering the page but maybe without username/playlists
        username = "User" # Fallback
        user_playlists = [] # Ensure it's an empty list

    # Render the selection page, passing the fetched playlists
    return render_template('select.html',
                           moods=AVAILABLE_MOODS,
                           username=username,
                           playlists=user_playlists) # Pass playlists to the template


@app.route('/generate', methods=['POST'])
def generate_playlist():
    token_info = get_token()
    if not token_info:
        print("Generate request failed: User not authenticated.")
        return render_template('player.html', video_ids_json='[]', track_names_json='[]', error="Your session has expired. Please log in again."), 401


    # --- Get User Selections ---
    selected_playlist_id = request.form.get('playlist_id') # Get playlist ID
    selected_mood_label = request.form.get('mood')
    try:
        num_songs_str = request.form.get('num_songs', '20')
        num_songs = min(max(1, int(num_songs_str)), 50) # Target total
    except (TypeError, ValueError):
         print(f"Invalid form input (num_songs).")
         return "Invalid number of songs provided.", 400

    if not selected_mood_label or not selected_playlist_id:
        print(f"Missing Mood or Playlist selection.")
        return "Missing Mood or Playlist selection.", 400


    print(f"Generating playlist for Mood: {selected_mood_label}, Target Songs: {num_songs}, From Playlist: {selected_playlist_id}")

    try:
        # --- Load CSV Tracks ---
        print("Loading standardized CSV tracks...")
        csv_df = load_csv_tracks(EXTERNAL_CSV_PATH)
        if csv_df is None or csv_df.empty:
             print("CSV DataFrame is empty or failed to load after cleaning.")
             return render_template('player.html', video_ids_json='[]', track_names_json='[]', error=f"Could not load valid track data.")

        # --- Filter CSV DataFrame by mood ---
        mood_filter = csv_df['Mood'].str.lower() == selected_mood_label.strip().lower()
        filtered_csv_df = csv_df.loc[mood_filter].copy()
        print(f"Found {len(filtered_csv_df)} tracks in CSV matching mood criteria.")

        # --- Fetch User Playlist Tracks ---
        sp = Spotify(auth=token_info['access_token']) # Need Spotify client here
        print(f"Fetching tracks from selected Spotify playlist ID: {selected_playlist_id}...")
        playlist_tracks_list = get_playlist_tracks(sp, selected_playlist_id) # Call the reinstated helper function
        print(f"Found {len(playlist_tracks_list)} total tracks in the selected Spotify playlist.")

        # --- Combine Tracks with Ratio ---
        # Convert filtered DataFrame rows to list of dicts for consistency
        filtered_csv_tracks_list = []
        for _, row in filtered_csv_df.iterrows():
            filtered_csv_tracks_list.append({
                'id': row['track_id'],
                'name': row['track_name'],
                'artist': row['artist_name'],
                'mood': row['Mood'], # Keep mood info
                'source': 'csv_dataset'
                # Add year if needed for display later
                # 'year': row['year'] if 'year' in row and pd.notna(row['year']) else None
            })

        # Define targets
        num_csv_target = math.ceil(num_songs * 0.8)
        num_playlist_target = num_songs - num_csv_target

        print(f"Targeting {num_csv_target} from CSV, {num_playlist_target} from Spotify Playlist.")

        # Select random tracks from CSV list
        selected_csv = random.sample(filtered_csv_tracks_list, min(len(filtered_csv_tracks_list), num_csv_target))
        print(f"Selected {len(selected_csv)} tracks from CSV.")

        # Select random tracks from the fetched playlist list
        # Ensure playlist_tracks_list is actually a list before sampling
        if not isinstance(playlist_tracks_list, list):
            print("Warning: playlist_tracks_list is not a list. Setting selected_playlist to empty.")
            selected_playlist = []
        else:
            selected_playlist = random.sample(playlist_tracks_list, min(len(playlist_tracks_list), num_playlist_target))
        print(f"Selected {len(selected_playlist)} tracks from Spotify Playlist.")


        # Combine the selections
        combined_selection = selected_csv + selected_playlist
        print(f"Initial combined count: {len(combined_selection)} tracks.")


        # --- Deduplicate ---
        final_selection_dict = {}
        for track in combined_selection:
            track_id = track.get('id')
            if track_id:
                # Prioritize keeping the CSV version if both exist (as it has mood info)
                if track_id not in final_selection_dict or track.get('source') == 'csv_dataset':
                    final_selection_dict[track_id] = track
        selected_tracks = list(final_selection_dict.values())
        print(f"Deduplicated count: {len(selected_tracks)} tracks.")


        # --- Shuffle Final List ---
        random.shuffle(selected_tracks)
        print(f"Final selected count after shuffle: {len(selected_tracks)}")


        if not selected_tracks:
             return render_template('player.html', video_ids_json='[]', track_names_json='[]', error=f"No tracks found matching criteria for mood: {selected_mood_label}.")


        # --- Iterative YouTube Search ---
        print(f"\nSearching YouTube iteratively to find up to {len(selected_tracks)} videos...") # Search for all selected
        youtube_video_ids = []
        final_track_names = []
        youtube_titles = []
        processed_track_ids_yt = set() # Use a different set for YT search tracking
        search_candidates = selected_tracks[:] # Use the final shuffled list

        youtube_search_attempts = 0
        max_youtube_attempts = len(selected_tracks) + 10 # Allow extra attempts
        quota_exceeded = False
        target_yt_videos = len(selected_tracks) # Try to find video for every selected track

        while len(youtube_video_ids) < target_yt_videos and search_candidates and youtube_search_attempts < max_youtube_attempts:
            youtube_search_attempts += 1
            current_track = search_candidates.pop(0)
            track_id = current_track.get('id')

            # Use .get with fallbacks for safety
            artist = current_track.get('artist', 'Unknown Artist')
            name = current_track.get('name', 'Unknown Track')

            # Skip if essential info missing or already processed
            if not track_id or not name or not artist or track_id in processed_track_ids_yt:
                continue

            processed_track_ids_yt.add(track_id)

            query = f"{artist} - {name} official audio video lyrics"

            print(f"  Attempt {youtube_search_attempts}: Searching for '{query}' (Track ID: {track_id})")
            video_info = None
            try:
                video_info = search_youtube(query)
                if video_info:
                    youtube_video_ids.append(video_info['id'])
                    final_track_names.append(f"{artist} - {name}") # Keep track names aligned with found videos
                    youtube_titles.append(video_info['title'])
                    print(f"    -> SUCCESS: Found YT: {video_info['title']} (ID: {video_info['id']}) [{len(youtube_video_ids)} found]")
                else:
                    print(f"    -> FAILED: Video not found for '{query}'.")

            except HttpError as e:
                 if e.resp.status == 403:
                     print("🛑 YouTube Quota likely exceeded. Stopping search.")
                     quota_exceeded = True; break
                 else: print(f"  - YouTube API HTTP Error during search for '{query}': {e}")
            except Exception as e: print(f"  - Unexpected YouTube search error for '{query}': {e}")

            time.sleep(0.1) # Small delay

        # --- End Iterative Search ---

        found_videos_count = len(youtube_video_ids)
        print(f"\nFinished YouTube search phase.")
        print(f"Successfully found {found_videos_count} videos out of {len(selected_tracks)} selected tracks.")
        if quota_exceeded: print("Warning: YouTube search stopped early due to likely quota limits.")
        if not search_candidates and len(youtube_video_ids) < len(selected_tracks): print("Warning: Ran out of unique songs to search or some searches failed.")

        if not youtube_video_ids:
             return render_template('player.html', video_ids_json='[]', track_names_json='[]', error="Could not find any playable YouTube videos for the selected mood.")

        # --- Render Player ---
        video_ids_json = jsonify(youtube_video_ids).get_data(as_text=True)
        track_names_json = jsonify(final_track_names).get_data(as_text=True) # Use names corresponding to found videos
        youtube_titles_json = jsonify(youtube_titles).get_data(as_text=True)
        return render_template('player.html', video_ids_json=video_ids_json, track_names_json=track_names_json, youtube_titles_json=youtube_titles_json)

    # --- FIX: Ensure spotipy is defined for exception handling ---
    except spotipy.SpotifyException as e:
    # --- End FIX ---
         # Handle Spotify errors during playlist fetch
         print(f"Spotify API error during playlist generation: {e}")
         if e.http_status in [401, 403]: print("Spotify token invalid. Logging out."); return redirect(url_for('logout'))
         return render_template('player.html', video_ids_json='[]', track_names_json='[]', error=f"Spotify error: {e.msg}")
    except Exception as e:
        print(f"Unexpected error in /generate: {e}")
        import traceback; traceback.print_exc()
        return render_template('player.html', video_ids_json='[]', track_names_json='[]', error="Unexpected server error during playlist generation.")

# --- Error Handlers & Run ---
@app.errorhandler(404)
def page_not_found(e):
    print(f"404 Error: {request.url}")
    # You should create a templates/404.html file
    # For now, return a simple message
    return "Page not found.", 404
    # return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    print(f"Server Error: {e}")
    import traceback; traceback.print_exc()
    # You should create a templates/500.html file
    # For now, return a simple message
    return "Internal server error.", 500
    # return render_template('500.html'), 500

if __name__ == '__main__':
    if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET:
        print("🚨 CRITICAL ERROR: Spotify client ID or secret missing in environment variables.")
        exit(1)
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "YOUR_API_KEY_HERE":
        print("🚨 CRITICAL ERROR: YouTube API key missing or placeholder used in environment variables.")
        exit(1)

    templates_dir = 'templates'
    if not os.path.exists(templates_dir):
         try: os.makedirs(templates_dir); print(f"Created '{templates_dir}' directory.")
         except OSError as e: print(f"🚨 ERROR: Could not create templates directory '{templates_dir}'. {e}"); exit(1)

    # Ensure templates/index.html exists for the root route
    if not os.path.exists(os.path.join(templates_dir, 'index.html')):
        print(f"🚨 WARNING: templates/index.html not found. Login page might fail.")
        # Optionally create a basic index.html here if needed

    # Ensure templates/select.html exists
    if not os.path.exists(os.path.join(templates_dir, 'select.html')):
         print(f"🚨 WARNING: templates/select.html not found. Selection page might fail.")

     # Ensure templates/player.html exists
    if not os.path.exists(os.path.join(templates_dir, 'player.html')):
        print(f"🚨 WARNING: templates/player.html not found. Player page might fail.")

    # Check for standardized CSV file
    if not os.path.exists(EXTERNAL_CSV_PATH):
         print(f"🚨 CRITICAL ERROR: Standardized CSV file '{EXTERNAL_CSV_PATH}' not found.")
         print("   Please run the standardize_data.py script first.")
         exit(1)
    else:
         print(f"Found standardized CSV file at '{EXTERNAL_CSV_PATH}'.")

    print("\nStarting Flask app...")
    app.run(debug=True, port=8888, host='127.0.0.1')

