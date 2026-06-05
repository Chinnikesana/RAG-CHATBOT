"""
One-time helper: log into Instagram interactively and save the session.

Run this LOCALLY (not in Docker) so you can approve any challenge
Instagram throws (SMS code, email code, "Was this you?" etc.).

Usage:
    python generate_ig_session.py

Once it prints "Session saved!", the ig_session.json file will be
mounted into Docker automatically on the next restart.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from this directory
load_dotenv(Path(__file__).parent / ".env")

from instagrapi import Client

USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")
SESSION_FILE = Path(__file__).parent / "ig_session.json"


def challenge_code_handler(username, choice):
    """
    Called by instagrapi when Instagram sends a verification code.
    'choice' is 1 for SMS, 0 for email.
    """
    method = "SMS" if choice == 1 else "EMAIL"
    print(f"\n{'='*50}")
    print(f"Instagram sent a {method} verification code to your account.")
    print(f"{'='*50}")
    code = input(f"Enter the {method} code: ").strip()
    return code


def change_password_handler(username):
    """Called if Instagram forces a password change."""
    print("\nInstagram is requesting a password change.")
    new_pass = input("Enter a new password (or press Enter to skip): ").strip()
    if new_pass:
        return new_pass
    print("Skipped password change — login may fail.")
    return None


def main():
    if not USERNAME or not PASSWORD:
        print("ERROR: INSTAGRAM_USERNAME or INSTAGRAM_PASSWORD not set in .env")
        sys.exit(1)

    print(f"Logging into Instagram as: {USERNAME}")
    print("(If Instagram sends a verification code, you'll be prompted here)\n")

    cl = Client()
    cl.delay_range = [1, 3]
    cl.challenge_code_handler = challenge_code_handler
    cl.change_password_handler = change_password_handler

    try:
        cl.login(USERNAME, PASSWORD)
    except Exception as e:
        print(f"\nLogin failed: {e}")
        print("\nTROUBLESHOOTING:")
        print("1. Open Instagram on your phone/browser")
        print("2. Check for a 'Suspicious login attempt' notification and tap 'This Was Me'")
        print("3. Go to Settings > Security > Login Activity and approve recent logins")
        print("4. Then run this script again immediately")
        sys.exit(1)

    # Verify the session works
    try:
        info = cl.account_info()
        print(f"\nLogged in successfully as: {info.username}")
        print(f"Followers: {info.follower_count}")
    except Exception as e:
        print(f"\nLogin seemed to work but session verification failed: {e}")
        sys.exit(1)

    # Save the session
    cl.dump_settings(str(SESSION_FILE))
    print(f"\nSession saved to: {SESSION_FILE}")
    print(f"File size: {SESSION_FILE.stat().st_size} bytes")
    print("\nNow restart your backend:")
    print("  docker-compose up -d --build backend")
    print("\nThe backend will reuse this authenticated session — no more challenges!")


if __name__ == "__main__":
    main()
