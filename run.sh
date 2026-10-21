#!/bin/bash

run_ivrserver() {
    echo "Starting IVR Server"
    python ./ivr_tts/tts_voice_message.py
}

run_webserver() {
    echo "Starting Web Server"
    uvicorn --app-dir=ivr_tts --host=0.0.0.0 --port=8000 app:app
}

run_dialer() {
    echo "Starting Dialer"
    python ./ivr_tts/dialer.py
}

run_ivrserver &
run_dialer &
run_webserver 