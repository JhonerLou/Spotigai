# test_spotify.py
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

print("--- Starting Spotify Connection Test ---")

# Load the credentials from your .env file
load_dotenv()
client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")

if not client_id or not client_secret:
    print("❌ ERROR: Could not load credentials from .env file.")
    print("Please check that the file exists and the variable names are correct.")
else:
    print("✅ Credentials loaded from .env file.")
    print(f"   Client ID: {client_id[:4]}...{client_id[-4:]}") # Print partial ID for verification

    try:
        # Attempt to authenticate
        auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        sp = spotipy.Spotify(auth_manager=auth_manager)

        # Make a simple, public API call to test the token
        track = sp.track('3n3Ppam7vgaVa1iaRUc9Lp') # Mr. Brightside

        print("\n🚀 SUCCESS! Connection to Spotify is working.")
        print(f"   Successfully fetched track: {track['name']}")

    except Exception as e:
        print(f"\n❌ FAILED: The connection was blocked.")
        print(f"   Error details: {e}")

print("\n--- Test Complete ---")