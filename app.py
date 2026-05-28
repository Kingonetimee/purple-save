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

    url_pattern = r"(https?://[^\s]+)"

    match = re.search(url_pattern, text)

    if match:
        return match.group(0)

    return None


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

        # Extract actual URL
        video_url = extract_url(video_text)

        if not video_url:
            error = "Please paste a valid TikTok or Instagram link."

        elif permission != "yes":
            error = "You must confirm ownership or permission."

        elif "/photo/" in video_url:
            error = "TikTok photo/slideshow posts are not supported yet. Please paste a video link."    

        elif "tiktok.com" not in video_url and "instagram.com" not in video_url:
            error = "Only TikTok and Instagram links are supported."

        else:

            file_id = str(uuid.uuid4())

            output_path = os.path.join(
                DOWNLOAD_FOLDER,
                f"{file_id}.mp4"
            )

            try:

                ydl_options = {
                    "format": "best",
                    "outtmpl": output_path,
                    "quiet": True,
                    "noplaylist": True,

                    # Max file size
                    "max_filesize": 100 * 1024 * 1024,
                }

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

                download_file = f"{file_id}.mp4"

            except Exception as e:

                print("YT-DLP ERROR:")
                print(e)

                error = "Video could not be downloaded."

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