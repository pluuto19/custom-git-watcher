import datetime
import os
import threading
import time
import traceback
import requests

from flask import Flask, request, jsonify
from aw_client import ActivityWatchClient
from aw_core import Event

app = Flask(__name__)
aw_client = ActivityWatchClient("custom-git-watcher")
bucket_id = "git-commits-bucket"
aw_client.create_bucket(bucket_id, event_type="git-commit")

bucket_lock = threading.Lock()

def save_err_log(message, line_number):
    print("called")
    if not os.path.exists("~/.custom-watcher-error-logs"):
        os.mkdir("~/.custom-watcher-error-logs")

    with open(os.path.join("~/.custom-watcher-error-logs", "custom-watcher-logs.txt"), mode="a") as f:
        f.write(f"{message}[custom-git-watcher.py | {line_number}]\n")

@app.route('/git-commit', methods=['POST'])
def receive_git_commit():
    try:
        data = request.json
        commit_hash = data['commit_hash']
        commit_message = data['commit_message']
        author = data['author']
        timestamp = data['timestamp']

        default_data = query_default_watchers()

        commit_data = {
            "git_commit": {
                "commit_hash": commit_hash,
                "commit_message": commit_message,
                "author": author,
                "timestamp": timestamp
            },
            "default_data": default_data
        }

        with bucket_lock:
            iso_timestamp = datetime.datetime.fromtimestamp(float(timestamp), tz=datetime.timezone.utc).isoformat()
            aw_client.insert_event(bucket_id, Event(timestamp=iso_timestamp, duration=0, data=commit_data))

        return jsonify({"status": "success"}), 200

    except Exception as e:
        error_message = f"Error processing request: {str(e)}\n{traceback.format_exc()}"
        save_err_log(error_message, 55)
        return jsonify({"status": "error", "message": "Internal server error"}), 500

def query_default_watchers():
    buckets = aw_client.get_buckets()
    default_watcher_data = {}
    for b_id, bucket_info in buckets.items():
        if b_id != "git-commits-bucket":
            events = aw_client.get_events(b_id, limit=1)
            if events:
                default_watcher_data[b_id] = events[0].data
    return default_watcher_data

def sync_to_external_server():
    with bucket_lock:
        events = aw_client.get_events(bucket_id)
        if events:
            data_to_send = [event.to_json_dict() for event in events]
            event_ids = [event['id'] for event  in events]
            try:
                response = requests.post('http://localhost:10000/receive-git-data', json=data_to_send)
                if response.status_code == 200:
                    try:
                        for event_id in event_ids:
                            aw_client.delete_event(bucket_id, event_id)
                    except Exception as e:
                        save_err_log(str(e), 81)
                else:
                    save_err_log(f"Failed to send data to external server. Status code: {response.status_code}", 83)
            except requests.exceptions.RequestException as e:
                save_err_log(str(e), 85)

def run_sync():
    while True:
        time.sleep(1800)
        sync_to_external_server()

def run_flask():
    aw_client.connect()
    app.run(host='0.0.0.0', port=5000)
    aw_client.disconnect()

server_thread = threading.Thread(target=run_flask)
sync_thread = threading.Thread(target=run_sync)
server_thread.start()
sync_thread.start()

while True:
    time.sleep(3)