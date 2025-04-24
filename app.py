from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp, time, sqlite3, os

app = Flask(__name__)
CORS(app)

DB_PATH = "audio_cache.db"

def init_db():
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audio_cache (
            video_id TEXT PRIMARY KEY,
            audio_url TEXT NOT NULL
        )
        """)
        conn.commit()
        conn.close()

def get_cached_url(video_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT audio_url FROM audio_cache WHERE video_id = ?", (video_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def set_cached_url(video_id, audio_url):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO audio_cache (video_id, audio_url) VALUES (?, ?)",
                   (video_id, audio_url))
    conn.commit()
    conn.close()

@app.route("/get-audio-url", methods=["POST"])
def get_audio_url():
    data = request.get_json()
    video_id = data.get("videoId")

    if not video_id:
        return jsonify({"error": "Missing videoId"}), 400

    audio_url = get_cached_url(video_id)
    if audio_url:
        return jsonify({"audioUrl": audio_url})

    try:
        with yt_dlp.YoutubeDL({
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extractor_args": {
                "youtube": ["skip=dash,player_response"]
            }
        }) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            audio_url = info.get("url")
            if not audio_url:
                return jsonify({"error": "No audio URL found"}), 500
            set_cached_url(video_id, audio_url)
            return jsonify({"audioUrl": audio_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    init_db()
    app.run(debug=False, threaded=True, port=5000)
