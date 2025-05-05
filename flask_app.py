# /home/your-username/mysite/flask_app.py (di PythonAnywhere)

from flask import Flask, request, jsonify

app = Flask(__name__)

latest_image_url = None

@app.route('/update_image', methods=['POST'])
def update_image():
    global latest_image_url
    if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json(); new_url = data.get('image_url')
    if new_url is None: return jsonify({"error": "Missing 'image_url'"}), 400
    if not isinstance(new_url, str) and new_url is not None : return jsonify({"error": "'image_url' must be a string or null"}), 400 # Izinkan null
    latest_image_url = new_url
    print(f"Received URL: {latest_image_url}")
    return jsonify({"message": "URL updated"}), 200

@app.route('/get_latest_image_url', methods=['GET'])
def get_latest_image():
    return jsonify({"latest_image_url": latest_image_url}), 200

@app.route('/')
def home():
    return "Flask API for Image URL is running!"
