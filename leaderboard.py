from flask import Flask, render_template
import sqlite3

app = Flask(__name__)
DB_FILE = "points.db"

def get_leaderboard():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT user_id, points FROM user_points ORDER BY points DESC LIMIT 20')
    results = c.fetchall()
    conn.close()
    return results

@app.route("/")
def leaderboard():
    data = get_leaderboard()
    leaderboard_data = [{"user_id": str(row[0]), "points": row[1]} for row in data]
    return render_template("leaderboard.html", leaderboard=leaderboard_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
