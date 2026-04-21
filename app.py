from flask import Flask, render_template, request, jsonify, session
import uuid
import requests
from urllib.parse import urlparse
import re

app = Flask(__name__)
app.secret_key = "change-this-to-a-secure-secret-key"

# In-memory store (replace with a DB like SQLite for persistence)
# Format: { session_id: [ {id, src, orientation, label, added_at}, ... ] }
boards = {}

DEFAULT_IMAGES = [
    {"id": "default-1", "src": "https://picsum.photos/seed/11/800/500", "orientation": "horizontal", "label": ""},
    {"id": "default-2", "src": "https://picsum.photos/seed/22/500/800", "orientation": "vertical",   "label": ""},
    {"id": "default-3", "src": "https://picsum.photos/seed/33/800/600", "orientation": "horizontal", "label": ""},
    {"id": "default-4", "src": "https://picsum.photos/seed/44/600/900", "orientation": "vertical",   "label": ""},
    {"id": "default-5", "src": "https://picsum.photos/seed/55/900/600", "orientation": "horizontal", "label": ""},
    {"id": "default-6", "src": "https://picsum.photos/seed/66/500/750", "orientation": "vertical",   "label": ""},
    {"id": "default-7", "src": "https://picsum.photos/seed/77/800/450", "orientation": "horizontal", "label": ""},
    {"id": "default-8", "src": "https://picsum.photos/seed/88/750/500", "orientation": "horizontal", "label": ""},
]


def get_board():
    sid = session.get("sid")
    if not sid or sid not in boards:
        sid = str(uuid.uuid4())
        session["sid"] = sid
        boards[sid] = list(DEFAULT_IMAGES)  # copy defaults
    return boards[sid]


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def detect_orientation_from_url(url: str) -> str:
    """
    Try to detect orientation by making a HEAD request and reading
    Content-Type. Falls back to a simple heuristic on the URL path.
    We keep it lightweight — no Pillow dependency required.
    """
    try:
        resp = requests.head(url, timeout=5, allow_redirects=True)
        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type:
            return None  # not an image
    except Exception:
        return None  # can't reach URL
    # Default to horizontal; the frontend JS will correct it after load
    return "horizontal"


@app.route("/")
def index():
    images = get_board()
    return render_template("index.html", images=images, count=len(images))


@app.route("/api/images", methods=["GET"])
def api_get_images():
    return jsonify(get_board())


@app.route("/api/images", methods=["POST"])
def api_add_image():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    orientation = data.get("orientation", "horizontal")
    label = (data.get("label") or "").strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400
    if not is_valid_url(url):
        return jsonify({"error": "Invalid URL"}), 400
    if orientation not in ("horizontal", "vertical"):
        orientation = "horizontal"

    # Verify it's actually a reachable image
    result = detect_orientation_from_url(url)
    if result is None:
        return jsonify({"error": "Could not verify image URL. Make sure it points to a valid image."}), 400

    board = get_board()
    new_image = {
        "id": str(uuid.uuid4()),
        "src": url,
        "orientation": orientation,
        "label": label,
    }
    board.insert(0, new_image)
    return jsonify(new_image), 201


@app.route("/api/images/<image_id>", methods=["DELETE"])
def api_delete_image(image_id):
    board = get_board()
    original_len = len(board)
    boards[session["sid"]] = [img for img in board if img["id"] != image_id]
    if len(boards[session["sid"]]) == original_len:
        return jsonify({"error": "Image not found"}), 404
    return jsonify({"deleted": image_id}), 200


@app.route("/api/images/<image_id>", methods=["PATCH"])
def api_update_image(image_id):
    data = request.get_json(force=True)
    board = get_board()
    for img in board:
        if img["id"] == image_id:
            if "label" in data:
                img["label"] = str(data["label"]).strip()
            if "orientation" in data and data["orientation"] in ("horizontal", "vertical"):
                img["orientation"] = data["orientation"]
            return jsonify(img), 200
    return jsonify({"error": "Image not found"}), 404


@app.route("/api/board/clear", methods=["POST"])
def api_clear_board():
    sid = session.get("sid")
    if sid and sid in boards:
        boards[sid] = []
    return jsonify({"cleared": True}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)
