import threading
import time
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
        aw_client.insert_event(bucket_id, Event(timestamp=f"{time.time()}", duration=0, data=commit_data))

    return jsonify({"status": "success"}), 200

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
    print("Syncing to external server...")
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
        else:
            print("No data to sync")

def run_sync():
    while True:
        time.sleep(5)
        sync_to_external_server()

server_thread = threading.Thread(target=app.run, args=(5000,))
sync_thread = threading.Thread(target=run_sync)
server_thread.start()
sync_thread.start()

while True:
    print("watcher running...")
    # aw_client.heartbeat(bucket_id, Event(timestamp= f"{time.time()}", data={"status":"alive"}), pulsetime=5)
    time.sleep(3)