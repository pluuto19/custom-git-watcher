import json
import os.path
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

@app.route('/git-commit', methods=['POST'])
def receive_git_commit():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No JSON data received"}), 400

        required_fields = ['commit_hash', 'commit_message', 'author', 'timestamp']
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"Missing required field: {field}"}), 400

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

        # with open("C:\\Users\\Asher Siddique\\Desktop\\opt.txt", mode="a") as f:
        #     f.write(f"Received commit: {commit_data}\n")

        with bucket_lock:
            aw_client.insert_event(bucket_id, Event(timestamp=f"{time.time()}", duration=0, data=commit_data))

        return jsonify({"status": "success"}), 200

    except Exception as e:
        error_message = f"Error processing request: {str(e)}\n{traceback.format_exc()}"
        print(error_message)
        os.mkdir(os.path.expanduser("~/.custom-watcher-error-logs"))
        with open(os.path.expanduser("~/.custom-watcher-error-logs"), mode="a") as f:
            f.write(f"Error: {error_message}\n")
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
            response = requests.post('', json=data_to_send)
            if response.status_code == 200:
                print("Data successfully sent to external server")
                aw_client.delete_bucket(bucket_id)
                aw_client.create_bucket(bucket_id, event_type="git-commit")
            else:
                print(f"Failed to send data to external server. Status code: {response.status_code}")

def run_sync():
    while True:
        time.sleep(5)
        sync_to_external_server()

def run_flask():
    app.run(host='0.0.0.0', port=5000)

server_thread = threading.Thread(target=run_flask)
sync_thread = threading.Thread(target=run_sync)
server_thread.start()
sync_thread.start()

while True:
    # aw_client.heartbeat(bucket_id, Event(timestamp= f"{time.time()}", data={"status":"alive"}), pulsetime=5)
    time.sleep(3)