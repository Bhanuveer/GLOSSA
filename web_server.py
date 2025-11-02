from flask import Flask, send_from_directory
from flask_cors import CORS, cross_origin # Import Flask-CORS

# Initialize Flask app
app = Flask(__name__, static_folder='frontend_static', static_url_path='')

# Apply CORS to the entire app
# This is crucial for allowing the frontend (Port 8000) to communicate with 
# the backend APIs (Ports 5001 and 5002) without the browser blocking it.
CORS(app) 

# Route to serve the main index.html file
@app.route('/')
def serve_index():
    """Serves the main entry page."""
    return send_from_directory(app.static_folder, 'index.html')

# General route to serve all other static files (like sign_to_text.html, app.js, style.css)
@app.route('/<path:filename>')
def serve_static(filename):
    """Serves all static files from the frontend_static folder."""
    return send_from_directory(app.static_folder, filename)

if __name__ == '__main__':
    # We only run the web server on port 8000
    # Note: We do NOT need to run this inside the virtual environment if 'flask_cors'
    # is installed globally, but it is best practice to run it inside the venv
    # to guarantee all dependencies are met.
    app.run(host='0.0.0.0', port=8000, debug=True)
