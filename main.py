from flask import Flask, send_file, request, after_this_request
from flask_limiter.util import get_remote_address
import os
from datetime import datetime, timedelta
import json
import pyttsx3
from flask_cors import CORS
import shutil
import threading
import time

app = Flask(__name__)
CORS(app)

request_counts = {}

def update_voice_count():
    try:
        with open("database.json", 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        data = {}

    count = data.get('total_voices_generated', 0)
    count += 1

    data['total_voices_generated'] = count

    with open("database.json", 'w') as file:
        json.dump(data, file)

def check_rate_limit(ip_address):
    now = datetime.now()
    last_access_time, count = request_counts.get(ip_address, (None, 0))

    if last_access_time is None or now - last_access_time > timedelta(hours=1):
        request_counts[ip_address] = (now, 1)
        return True
    elif count < 100:
        request_counts[ip_address] = (last_access_time, count + 1)
        return True
    else:
        return False
    
def save_text_to_speech(text, gender='female'):
    engine = pyttsx3.init()

    voices = engine.getProperty('voices')
    if gender == 'male':
        engine.setProperty('voice', voices[0].id)
    else:
        engine.setProperty('voice', voices[1].id)

    output_folder = 'temp_downloads'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    date_time_string = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f'{output_folder}/tts_output_{date_time_string}.mp3'

    engine.save_to_file(text, file_name)
    engine.runAndWait()

    update_voice_count()

    return file_name

# Frontend Files #
@app.route('/favicon.ico')
def faviconico():
    return send_file(os.path.join('public', 'favicon.ico'))

@app.route('/')
def index():
    return send_file(os.path.join('public', 'index.html'))
    
@app.route('/api/tts', methods=['POST'])
def text_to_speech_endpoint():
    ip_address = get_remote_address()

    if check_rate_limit(ip_address):
        text = request.form.get('text', '')
        gender = request.form.get('gender', 'female')
        file_path = save_text_to_speech(text, gender)
        return send_file(file_path, as_attachment=True, download_name=os.path.basename(file_path))
    else:
        return "Rate limit exceeded. You can make a maximum of 100 requests per hour.", 429

def delete_file_after_delay(file_path, delay_seconds=5):
    def delete_file():
        try:
            time.sleep(delay_seconds)
            os.remove(file_path)
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")

    threading.Thread(target=delete_file).start()

@app.route('/api/tts/download')
def download_voice():
    voice_folder = 'temp_downloads'
    latest_file = max([os.path.join(voice_folder, f) for f in os.listdir(voice_folder)], key=os.path.getctime, default=None)

    if latest_file:
        temp_download_folder = 'temp_downloads'
        os.makedirs(temp_download_folder, exist_ok=True)

        temp_file_path = os.path.join(temp_download_folder, os.path.basename(latest_file))

        shutil.move(latest_file, temp_file_path)

        @after_this_request
        def delete_file(response):
            delete_file_after_delay(temp_file_path)
            return response

        return send_file(temp_file_path, as_attachment=True, download_name=os.path.basename(temp_file_path))
    else:
        return "No voice file available for download", 404

@app.route('/api/tts/preview')
def preview_voice():
    voice_folder = 'temp_downloads'
    latest_file = max([os.path.join(voice_folder, f) for f in os.listdir(voice_folder)], key=os.path.getctime, default=None)

    if latest_file:
        return send_file(latest_file, mimetype="audio/mp3")
    else:
        return "No voice file available for preview", 404

if __name__ == '__main__':
    app.run()