from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication


@app.route("/")
def home():
    return jsonify(
        {"message": "Welcome to HealthHackathon 2025 API", "status": "running"}
    )


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "backend"})


@app.route("/api/example", methods=["POST"])
def example_post():
    data = request.get_json()
    return jsonify({"message": "Data received", "received": data})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
