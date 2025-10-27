import spotipy
from spotipy.oauth2 import SpotifyOAuth
from flask import Flask, request, redirect
import os
# Initialize Flask app
app = Flask(__name__)

# Spotify app credentials (replace with your actual credentials)
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = "os.getenv('SPOTIFY_CLIENT_SECRET')"
REDIRECT_URI = "http://localhost:8888/callback"  # For local testing
SCOPE = "user-library-read user-top-read playlist-modify-public playlist-modify-private"

# Set up Spotify OAuth
sp_oauth = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE)

@app.route('/')
def home():
    return "Welcome to the Spotify Dashboard!"

# Redirect user to Spotify login page
@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

# Callback route that Spotify redirects to after login
@app.route('/callback')
def callback():
    token_info = sp_oauth.get_access_token(request.args['code'])
    sp = spotipy.Spotify(auth=token_info['access_token'])

    # Save the access token for future requests (you can save it in session or database)
    return "Logged in successfully!"

if __name__ == '__main__':
    app.run(port=8888)


