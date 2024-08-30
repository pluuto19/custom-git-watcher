import threading
import time

from flask import Flask, request, jsonify
from aw_client import ActivityWatchClient
from aw_core import Event

app = Flask(__name__)
aw_client = ActivityWatchClient("custom-git-watcher")
bucket_id = "git-commits-bucket"
aw_client.create_bucket(bucket_id, event_type="git-commit")

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

server_thread = threading.Thread(target=app.run(port=5000))
server_thread.start()
while True:
    print("server running...")
    time.sleep(3)