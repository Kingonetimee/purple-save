import os
import re
import uuid
import time
import yt_dlp

from flask import Flask, render_template, request, send_from_directory

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# =========================
# RATE LIMITER
# =========================

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

# =========================
# AUTO DELETE OLD FILES
# =========================

FILE_LIFETIME = 60 * 30  # 30 minutes


def cleanup_old_files():
    now = time.time()

    for filename in os.listdir(DOWNLOAD_FOLDER):
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)

        if os.path.isfile(file_path):
            file_age = now - os.path.getmtime(file_path)

            if file_age > FILE_LIFETIME:
                try:
                    os.remove(file_path)
                    print(f"Deleted old file: {filename}")
                except Exception as e:
                    print(e)


# =========================
# EXTRACT URL FROM TEXT
# =========================

def extract_url(text):
    if not text:
        return None

    url_pattern = r"(https?://[^\s]+)"
    match = re.search(url_pattern, text)

    if match:
        return match.group(0)

    return None


# =========================
# PLATFORM CHECK
# =========================

def is_supported_url(url):
    supported_domains = [
        "tiktok.com",
        "vm.tiktok.com",
        "vt.tiktok.com",
        "instagram.com",
        "youtube.com",
        "youtu.be",
        "facebook.com",
        "fb.watch",
        "twitter.com",
        "x.com"
    ]

    return any(domain in url.lower() for domain in supported_domains)


def is_youtube_url(url):
    url = url.lower()

    return (
        "youtube.com" in url
        or "youtu.be" in url
    )


# =========================
# MAIN ROUTE
# =========================

@app.route("/", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def index():
    cleanup_old_files()

    download_file = None
    error = None
    video_info = None

    if request.method == "POST":
        video_text = request.form.get("video_url")
        permission = request.form.get("permission")

        video_url = extract_url(video_text)

        if not video_url:
            error = "Please paste a valid video link."

        elif permission != "yes":
            error = "You must confirm ownership or permission."

        elif "/photo/" in video_url.lower():
            error = "Photo/slideshow posts are not supported yet. Please paste a video link."

        elif not is_supported_url(video_url):
            error = "Only TikTok, Instagram, YouTube, Facebook, and Twitter/X links are supported."

        else:
            file_id = str(uuid.uuid4())

            output_template = os.path.join(
                DOWNLOAD_FOLDER,
                f"{file_id}.%(ext)s"
            )

            try:
                # =========================
                # GENERAL OPTIONS
                # =========================

                ydl_options = {
                    "outtmpl": output_template,
                    "quiet": True,
                    "noplaylist": True,
                    "merge_output_format": "mp4",
                    "max_filesize": 100 * 1024 * 1024,

                    "http_headers": {
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        )
                    },
                }

                # =========================
                # YOUTUBE-SPECIFIC OPTIONS
                # =========================

                if is_youtube_url(video_url):
                    ydl_options.update({
                        "format": "best[ext=mp4]/best",

                        "extractor_args": {
                            "youtube": {
                                "player_client": ["android"]
                            }
                        },
                    })

                else:
                    ydl_options.update({
                        "format": "best[ext=mp4]/best"
                    })

                # =========================
                # DOWNLOAD VIDEO
                # =========================

                with yt_dlp.YoutubeDL(ydl_options) as ydl:
                    info = ydl.extract_info(
                        video_url,
                        download=True
                    )

                    video_info = {
                        "title": info.get("title", "Untitled video"),
                        "uploader": info.get("uploader", "Unknown creator"),
                        "thumbnail": info.get("thumbnail"),
                        "duration": info.get("duration"),
                    }

                # =========================
                # FIND DOWNLOADED FILE
                # =========================

                possible_files = [
                    file
                    for file in os.listdir(DOWNLOAD_FOLDER)
                    if file.startswith(file_id)
                ]

                if not possible_files:
                    error = "Download finished but file was not found."

                else:
                    downloaded_filename = possible_files[0]
                    download_file = downloaded_filename

            except Exception as e:
                print("YT-DLP ERROR:")
                print(type(e))
                print(e)

                error = (
                    "Video could not be downloaded. "
                    "It may be private, restricted, blocked, or unsupported."
                )

    return render_template(
        "index.html",
        download_file=download_file,
        error=error,
        video_info=video_info
    )


# =========================
# DOWNLOAD ROUTE
# =========================

@app.route("/download/<filename>")
def download(filename):
    return send_from_directory(
        DOWNLOAD_FOLDER,
        filename,
        as_attachment=True
    )


# =========================
# STATIC PAGES
# =========================

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


# =========================
# RUN APP
# =========================

if __name__ == "__main__":
    app.run(debug=True)