"""
Export Instagram cookies from your Edge browser to ig_cookies.txt (Netscape format).

This file is mounted into Docker so yt-dlp can use authenticated Instagram access.
Run this ONE TIME (or whenever cookies expire / you re-login on Edge):

    python export_ig_cookies.py

Prerequisites:
  - You must be logged into Instagram on Microsoft Edge
  - Close Edge completely before running (or it may fail to read the cookie DB)
  - pip install yt-dlp  (already in your venv)
"""
import subprocess
import sys
import os

COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ig_cookies.txt")
BROWSER = os.getenv("INSTAGRAM_COOKIE_BROWSER", "edge")


def main():
    print(f"Exporting Instagram cookies from {BROWSER.upper()} browser...")
    print(f"Target file: {COOKIE_FILE}")
    print()
    print("NOTE: If Edge is open, close it first (or cookies may fail to read).")
    print()

    # Use yt-dlp to export cookies from the browser
    # --cookies-from-browser reads the browser's cookie store
    # --cookies writes them to a Netscape-format file
    # We use a dummy URL just to trigger the cookie export
    result = subprocess.run(
        [
            sys.executable, "-m", "yt_dlp",
            "--cookies-from-browser", BROWSER,
            "--cookies", COOKIE_FILE,
            "--dump-json",
            "--no-download",
            "--quiet",
            "https://www.instagram.com/reel/CxLiDqpuVcR/",  # any public reel
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if not os.path.exists(COOKIE_FILE) or os.path.getsize(COOKIE_FILE) < 100:
        print(f"\nERROR: Cookie export failed!")
        print(f"stderr: {result.stderr.strip()}")
        print()
        print("Troubleshooting:")
        print(f"  1. Make sure you're logged into Instagram on {BROWSER.upper()}")
        print(f"  2. Close {BROWSER.upper()} completely and try again")
        print(f"  3. Try: python -m yt_dlp --cookies-from-browser {BROWSER} --cookies ig_cookies.txt https://www.instagram.com/")
        sys.exit(1)

    size = os.path.getsize(COOKIE_FILE)
    
    # Count instagram cookies
    ig_count = 0
    with open(COOKIE_FILE, "r") as f:
        for line in f:
            if ".instagram.com" in line:
                ig_count += 1

    print(f"\nCookies exported successfully!")
    print(f"  File: {COOKIE_FILE}")
    print(f"  Size: {size:,} bytes")
    print(f"  Instagram cookies: {ig_count}")
    print()

    if ig_count == 0:
        print("WARNING: No Instagram cookies found!")
        print(f"Make sure you're logged into Instagram on {BROWSER.upper()}.")
        sys.exit(1)

    print("Next steps:")
    print("  1. Rebuild Docker:  docker-compose up -d --build backend")
    print("  2. The backend will now use authenticated Instagram access")
    print("  3. You'll get: real view counts, follower counts, and reliable audio")
    print()
    print("Re-run this script whenever your Instagram session expires (~90 days).")


if __name__ == "__main__":
    main()
