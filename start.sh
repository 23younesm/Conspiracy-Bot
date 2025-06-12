#!/bin/bash

# Start Discord bot in background
python app.py &

# Start Flask leaderboard web app (adjust host/port if needed)
python leaderboard.py &

# Start DB webview
python3 -m sqlite_web points.db --host 0.0.0.0