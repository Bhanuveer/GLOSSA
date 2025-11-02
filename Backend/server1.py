# --- REVISED server1.py ---

from flask import Flask, jsonify, send_from_directory
import speech_recognition as sr
import threading
import os
import pathlib 

app = Flask(__name__)

# Global Variables
listening = False
recognized_text = ""
recognized_letters = []
lock = threading.Lock()

# --- CRITICAL ADJUSTMENT: Path Fix START ---

# Get the directory where server1.py is located
BASE_DIR = pathlib.Path(__file__).parent 

# Set the folder path to the 'signs' folder, which should be in the same directory
SIGN_IMAGE_FOLDER = BASE_DIR / "signs" 

# Convert the path object to a string for old Python functions (e.g., os.listdir)
SIGN_IMAGE_FOLDER_STR = str(SIGN_IMAGE_FOLDER)

# Check if folder exists
if not os.path.exists(SIGN_IMAGE_FOLDER_STR):
    print(f"Error: Sign image folder not found at {SIGN_IMAGE_FOLDER_STR}")
    print("Please ensure the folder is named 'signs' and is in the same directory as server1.py.")
else:
    print(f"Sign image folder found: {SIGN_IMAGE_FOLDER_STR}")

# Print available sign images (first few for verification)
try:
    print("Available sign images:", os.listdir(SIGN_IMAGE_FOLDER_STR)[:5], "...")
except FileNotFoundError:
    pass 

# --- CRITICAL ADJUSTMENT: Path Fix END ---


def process_speech():
    """Runs speech recognition continuously until stopped."""
    global listening, recognized_text, recognized_letters
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("Listening for speech...")
        recognizer.adjust_for_ambient_noise(source)

        while listening:
            try:
                audio = recognizer.listen(source, timeout=3, phrase_time_limit=10) 
                text = recognizer.recognize_google(audio)
                with lock:
                    recognized_text += " " + text
                    # The conversion to letters handles spaces, punctuation, and capitalizes
                    recognized_letters.extend(list(text.replace(" ", "").upper()))
                print(f"Recognized Speech: {text}")
            except sr.UnknownValueError:
                print("Could not understand audio")
            except sr.WaitTimeoutError:
                 print("No speech detected.")
            except sr.RequestError:
                print("Speech recognition service unavailable")
            except Exception as e:
                print(f"Unexpected Error: {e}")


@app.route('/start', methods=['POST'])
def start_listening():
    """Starts speech recognition in a separate thread."""
    global listening
    if not listening:
        listening = True
        threading.Thread(target=process_speech, daemon=True).start()
        return jsonify({"status": "Listening started"}), 200
    return jsonify({"status": "Already listening"}), 200


@app.route('/stop', methods=['POST'])
def stop_listening():
    """Stops speech recognition but keeps recognized text and letters."""
    global listening
    listening = False
    return jsonify({"status": "Listening stopped"}), 200


@app.route('/clear_signs', methods=['POST'])
def clear_signs():
    """Clears the recognized letters and text."""
    global recognized_text, recognized_letters
    with lock:
        recognized_text = ""
        recognized_letters = []
    return jsonify({"status": "Signs and speech cleared"}), 200


@app.route('/recognized_text', methods=['GET'])
def get_recognized_text():
    """Returns the recognized speech text."""
    with lock:
        return jsonify({"recognized_text": recognized_text}), 200


@app.route('/recognized_letters', methods=['GET'])
def get_recognized_letters():
    """Returns the recognized letters for sign display."""
    with lock:
        return jsonify({"recognized_letters": recognized_letters}), 200


@app.route('/sign/<letter>', methods=['GET'])
def get_sign_image(letter):
    """Serves the sign image for a given letter."""
    letter = letter.upper()
    available_files = os.listdir(SIGN_IMAGE_FOLDER_STR) 

    # Check for multiple possible extensions
    possible_extensions = ['.png', '.PNG', '.jpg', '.JPG', '.jpeg', '.JPEG']

    for ext in possible_extensions:
        filename = f"{letter}{ext}"
        if filename in available_files:
            # Use the string version of the folder path for send_from_directory
            return send_from_directory(SIGN_IMAGE_FOLDER_STR, filename) 

    print(f"Error: Image not found for '{letter}'. Available files: {available_files[:5]}...")
    return jsonify({"error": f"Image not found for letter {letter}"}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)