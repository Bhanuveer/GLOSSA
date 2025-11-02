import warnings
import pickle
import cv2
import mediapipe as mp
import numpy as np
from collections import deque
import threading
from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import base64

# Suppress noisy warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=RuntimeWarning)

# -----------------------------
# MODEL LOADING
# -----------------------------
try:
    with open('model1.p', 'rb') as file:
        model_dict = pickle.load(file)
    model = model_dict['model']
    label_mapping = model_dict['label_mapping']
    reverse_label_mapping = {v: k for k, v in label_mapping.items()}
    print("✅ Sign recognition model loaded successfully.")
except FileNotFoundError:
    print("❌ Error: model1.p not found. Place it in the backend directory.")
    model = None
    label_mapping, reverse_label_mapping = {}, {}

# -----------------------------
# INITIALIZATIONS
# -----------------------------
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=True, min_detection_confidence=0.3)
mp_drawing = mp.solutions.drawing_utils

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

lock = threading.Lock()
cap = None
server_running = False

# Recognition-related variables
recognized_string = ""
display_string = ""
opencv_frame = None
prediction_buffer = deque(maxlen=10)
previous_character = None
gesture_interval = 0.7
prediction_smoothing_threshold = 0.7
space_timeout = 1.0
letter_timeout = 2.0
no_hand_timeout = 1.0
debounce_timeout = 0.5

# -----------------------------
# THREAD FUNCTION
# -----------------------------
def run_inference():
    global server_running, recognized_string, display_string, previous_character, opencv_frame

    if model is None:
        print("❌ Model not loaded — cannot start inference.")
        with lock:
            server_running = False
        return

    print("🎥 Attempting to open webcam...")

    # Try multiple camera indices
    for index in [0, 1, 2, 3]:
        temp_cap = cv2.VideoCapture(index)
        if temp_cap.isOpened():
            cap = temp_cap
            print(f"✅ Camera opened at index {index}")
            break
        temp_cap.release()
    else:
        print("❌ No camera found. Check device permissions.")
        with lock:
            server_running = False
        return

    #cv2.namedWindow("Sign Recognition", cv2.WINDOW_NORMAL)
    #cv2.resizeWindow("Sign Recognition", 640, 480)

    try:
        while True:
            with lock:
                if not server_running:
                    print("🛑 Server stopped.")
                    break

            ret, frame = cap.read()
            if not ret:
                print("⚠️ Camera frame not received.")
                break

            H, W, _ = frame.shape
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(frame_rgb)

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    x_ = [lm.x for lm in hand_landmarks.landmark]
                    y_ = [lm.y for lm in hand_landmarks.landmark]
                    data_aux = [(x - min(x_)) for x in x_] + [(y - min(y_)) for y in y_]

                    if len(data_aux) == 42:
                        prediction = model.predict([np.asarray(data_aux)])
                        predicted_index = prediction[0]
                        predicted_character = str(predicted_index)
                        prediction_buffer.append(predicted_character)

                        most_common_prediction = max(set(prediction_buffer), key=prediction_buffer.count)
                        prediction_confidence = prediction_buffer.count(most_common_prediction) / len(prediction_buffer)

                        if prediction_confidence > prediction_smoothing_threshold:
                            if most_common_prediction == 'OK':
                                display_string = recognized_string
                                recognized_string = ""
                            elif most_common_prediction == 'SPACE':
                                recognized_string += " "
                            elif most_common_prediction == 'BACKSPACE':
                                recognized_string = recognized_string[:-1]
                            else:
                                if previous_character != most_common_prediction:
                                    recognized_string += most_common_prediction
                                    previous_character = most_common_prediction

                        cv2.putText(frame, most_common_prediction, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
                    else:
                        print(f"⚠️ Skipping frame with {len(data_aux)} landmarks.")

            # Show recognized text
            cv2.putText(frame, recognized_string, (30, H - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 0), 3)
            #cv2.imshow("Sign Recognition", frame)
            _, buffer = cv2.imencode('.jpg', frame)
            opencv_frame = base64.b64encode(buffer).decode('utf-8')


            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("👋 'q' pressed — stopping inference.")
                break

    except Exception as e:
        print(f"💥 Error during inference: {str(e)}")

    finally:
        if cap:
            cap.release()
        cv2.destroyAllWindows()
        with lock:
            server_running = False
        print("✅ Clean exit from inference thread.")

# -----------------------------
# FLASK ROUTES
# -----------------------------
@app.route("/start_inference", methods=["POST"])
def start_inference():
    global server_running
    with lock:
        if not server_running:
            server_running = True
            t = threading.Thread(target=run_inference, daemon=True)
            t.start()
            return jsonify({"message": "Inference started."}), 200
        else:
            return jsonify({"message": "Inference already running."}), 400

@app.route("/stop_inference", methods=["POST"])
def stop_inference():
    global server_running
    with lock:
        server_running = False
    return jsonify({"message": "Inference stopped."}), 200

@app.route("/recognized_string", methods=["GET"])
def get_recognized_string():
    return jsonify({
        "recognized_string": recognized_string,
        "confirmation_string": display_string,
        "opencv_frame": opencv_frame
    })

@app.route("/")
def home():
    return "<h3>🧠 Sign Recognition Server (Port 5002) is Running!</h3>"

# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5002, allow_unsafe_werkzeug=True)
