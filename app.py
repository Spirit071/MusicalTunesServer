from flask import Flask, request, jsonify
from flask_cors import CORS
import os, psycopg2, threading
import yt_dlp

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode='verify-full',
        sslrootcert='/etc/ssl/certs/ca-certificates.crt'  # <--- Use system certs
    )

def init_db():
    conn = get_db_connection()
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT audio_url FROM audio_cache WHERE video_id = %s", (video_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def set_cached_url(video_id, audio_url):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audio_cache (video_id, audio_url)
        VALUES (%s, %s)
        ON CONFLICT (video_id) DO UPDATE
        SET audio_url = EXCLUDED.audio_url
    """, (video_id, audio_url))
    conn.commit()
    conn.close()

def fetch_and_cache(video_id, result_container):
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
            if audio_url:
                set_cached_url(video_id, audio_url)
                result_container['audio_url'] = audio_url
            else:
                result_container['error'] = "No audio URL found"
    except Exception as e:
        result_container['error'] = str(e)

@app.route('/', methods=["GET"])
def home():
    return "Hello!"

@app.route("/get-audio-url", methods=["POST"])
def get_audio_url():
    data = request.get_json()
    video_id = data.get("videoId")

    if not video_id:
        return jsonify({"error": "Missing videoId"}), 400

    audio_url = get_cached_url(video_id)
    if audio_url:
        return jsonify({"audioUrl": audio_url})

    result_container = {}

    thread = threading.Thread(target=fetch_and_cache, args=(video_id, result_container))
    thread.start()
    thread.join()

    if 'audio_url' in result_container:
        return jsonify({"audioUrl": result_container['audio_url']})
    else:
        return jsonify({"error": result_container.get('error', 'Unknown error')}), 500

if __name__ == "__main__":
    init_db()
    app.run(debug=False, threaded=True, host='0.0.0.0', port=5000)
