// --- Configuration ---
// Note: server1.py is assumed to be on 5001 for Speech-to-Sign
const API_URL = 'http://localhost:5001'; 
// Note: server.py is on 5002 for Sign-to-Text
const INFERENCE_API_URL = 'http://localhost:5002';

// --- Speech to Sign Converter Logic (Port 5001) ---

const speechRecognitionStatus = document.getElementById('speechRecognitionStatus');
const signDisplayArea = document.getElementById('signDisplayArea');
const recognizedTextOutput = document.getElementById('recognizedTextOutput');
const speechToSignBtn = document.getElementById('startSpeechToSignBtn');

function updateStatus(message, isError = false) {
    if (speechRecognitionStatus) {
        speechRecognitionStatus.textContent = message;
        speechRecognitionStatus.style.color = isError ? 'red' : '#2563eb';
    }
}

async function startSpeechToSign() {
    if (!speechToSignBtn) return;
    
    updateStatus('Connecting to Speech Server...');
    speechToSignBtn.disabled = true;

    try {
        const response = await fetch(API_URL + '/start_recognition', { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
            updateStatus('Listening... Please speak now.');
            // Start polling for recognized text and signs
            pollSpeechRecognition();
        } else {
            updateStatus('Error starting recognition: ' + data.error, true);
            speechToSignBtn.disabled = false;
        }
    } catch (error) {
        updateStatus('Server error. Ensure server1.py (Port 5001) is running.', true);
        console.error('Fetch error:', error);
        speechToSignBtn.disabled = false;
    }
}

function stopSpeechToSign() {
    // This function only stops the polling loop, 
    // the server is designed to stop recognition after a period of silence.
    // We just reset the UI.
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
    if (speechToSignBtn) speechToSignBtn.disabled = false;
    updateStatus('Recognition Stopped.');
}


let pollInterval = null;

function pollSpeechRecognition() {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(API_URL + '/status');
            const data = await response.json();

            if (data.is_recognizing) {
                updateStatus('Listening... Speak now.');
                recognizedTextOutput.textContent = data.recognized_text || '...';
                
                if (data.sign_image_url) {
                    signDisplayArea.innerHTML = `<img src="${API_URL}/${data.sign_image_url}" alt="${data.current_word}" class="w-full h-auto max-w-sm rounded-lg shadow-xl mx-auto" onerror="this.onerror=null; this.src='https://placehold.co/400x300/e0e0e0/555555?text=Image+Not+Found'">`;
                } else if (data.recognized_text) {
                     // If no sign is found for the word, clear the image
                    signDisplayArea.innerHTML = `<p class="text-gray-500 mt-4">Word: "${data.current_word}" - No sign found yet.</p>`;
                }
            
            } else {
                // If recognition is finished
                updateStatus('Recognition Complete. Press Start to go again.');
                recognizedTextOutput.textContent = data.recognized_text || '...';
                clearInterval(pollInterval);
                if (speechToSignBtn) speechToSignBtn.disabled = false;

                // Final sign should be displayed
                if (data.sign_image_url) {
                    signDisplayArea.innerHTML = `<img src="${API_URL}/${data.sign_image_url}" alt="${data.current_word}" class="w-full h-auto max-w-sm rounded-lg shadow-xl mx-auto" onerror="this.onerror=null; this.src='https://placehold.co/400x300/e0e0e0/555555?text=Image+Not+Found'">`;
                }
            }

        } catch (e) {
            updateStatus('Connection lost. Server error.', true);
            console.error('Polling error:', e);
            clearInterval(pollInterval);
            if (speechToSignBtn) speechToSignBtn.disabled = false;
        }
    }, 500); // Poll every 500ms
}


// --- Sign to Text Converter Logic (Port 5002) ---

let socket = null;
let recognitionLoop = null;

function connectSocket() {
    // Only run this if we are on the sign_to_text page
    if (!document.getElementById('startInferenceBtn')) return;
    
    // Check if socket is already connected or connecting
    if (socket && (socket.connected || socket.connecting)) return;

    // We use a standard HTTP polling mechanism now as defined in the instructions, 
    // so the SocketIO connection might be vestigial but keep the function structure.
    console.log('Sign-to-Text logic ready.');
}

// Function to initialize webcam and start polling for recognized string
async function startInference() {
    const startBtn = document.getElementById('startInferenceBtn');
    const stopBtn = document.getElementById('stopInferenceBtn');

    if (!startBtn || !stopBtn) return;

    // 1. Send HTTP request to Flask server to start capture/inference thread (OpenCV window pops up)
    try {
        const response = await fetch(INFERENCE_API_URL + '/start_inference', { method: 'POST' });
        if (!response.ok) {
            const errorData = await response.json();
             throw new Error(errorData.message || "Failed to start inference.");
        }
        console.log('Inference thread requested on server.');
    } catch (error) {
        console.error('Failed to start inference on server:', error);
        alert('Could not connect to Sign Server (Port 5002) or inference is already running.');
        return;
    }

    // 2. Start Polling for Recognized String
    stopBtn.disabled = false;
    startBtn.disabled = true;

    // Start polling for recognized string every 500ms
    recognitionLoop = setInterval(fetchRecognizedString, 50);
}

async function fetchRecognizedString() {
    try {
        const response = await fetch(INFERENCE_API_URL + '/recognized_string');
        const data = await response.json();
        
        const recognizedStringDisplay = document.getElementById('recognizedStringDisplay');
        if (recognizedStringDisplay) {
             // Use the recognized_string for real-time output
             recognizedStringDisplay.textContent = data.recognized_string;
             
             // Check if a final confirmation string is ready (e.g., after an 'OK' gesture)
             if (data.confirmation_string && data.confirmation_string !== "") {
                 // You could add logic here to display the confirmed string differently
                 // For now, we just ensure it's still using the latest recognized_string
             }
        }

        //const frameWindow = document.getElementById('OpenCVFrame');
        const frameElement = document.getElementById('OpenCVFrame');
        if (frameElement && data.opencv_frame) {
            frameElement.src = `data:image/jpeg;base64,${data.opencv_frame}`;
        }
        
    } catch (e) {
        console.error('Error fetching recognized string. Server may have stopped:', e);
        clearInterval(recognitionLoop); // Stop polling on error
        document.getElementById('startInferenceBtn').disabled = false;
        document.getElementById('stopInferenceBtn').disabled = true;
    }
}


async function stopInference() {
    const startBtn = document.getElementById('startInferenceBtn');
    const stopBtn = document.getElementById('stopInferenceBtn');
    
    // Stop the local polling loop
    if (recognitionLoop) {
        clearInterval(recognitionLoop);
    }
    
    // Send HTTP request to Flask server to stop inference thread
    try {
        await fetch(INFERENCE_API_URL + '/stop_inference', { method: 'POST' });
        console.log('Inference thread stop requested on server.');
    } catch (error) {
        console.error('Failed to communicate stop to server:', error);
    }
    
    if (stopBtn) stopBtn.disabled = true;
    if (startBtn) startBtn.disabled = false;
}

// Global setup run on page load
document.addEventListener('DOMContentLoaded', connectSocket);
