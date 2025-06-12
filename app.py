import discord
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = ""  # Replace with your actual bot token

intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

DB_FILE = "points.db"

conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

# Create tables
c.execute('''
CREATE TABLE IF NOT EXISTS user_points (
    user_id INTEGER PRIMARY KEY,
    points INTEGER NOT NULL DEFAULT 0
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS flags (
    flag TEXT PRIMARY KEY,
    points INTEGER NOT NULL,
    challenge_name TEXT NOT NULL
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS correct_submissions (
    user_id INTEGER,
    flag TEXT,
    timestamp TEXT,
    PRIMARY KEY (user_id, flag)
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS incorrect_submissions (
    user_id INTEGER,
    flag TEXT,
    timestamp TEXT,
    reason TEXT,
    PRIMARY KEY (user_id, flag)
)
''')

conn.commit()

# Seed flags with challenge names and points
def seed_flags():
    flags = [
        ("sillyCTF{bot}", 10, "Bot Challenge"),
        ("sillyCTF{advanced}", 25, "Advanced Challenge"),
        ("sillyCTF{secret}", 50, "Secret Challenge")
    ]
    for flag, pts, name in flags:
        try:
            c.execute("INSERT INTO flags (flag, points, challenge_name) VALUES (?, ?, ?)", (flag, pts, name))
        except sqlite3.IntegrityError:
            pass  # Already exists
    conn.commit()

seed_flags()

def get_points(user_id: int) -> int:
    c.execute('SELECT points FROM user_points WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    return row[0] if row else 0

def add_points(user_id: int, points: int):
    current = get_points(user_id)
    if current == 0:
        c.execute('INSERT INTO user_points(user_id, points) VALUES (?, ?)', (user_id, points))
    else:
        c.execute('UPDATE user_points SET points = points + ? WHERE user_id = ?', (points, user_id))
    conn.commit()

def check_flag(flag: str):
    c.execute('SELECT points FROM flags WHERE flag = ?', (flag,))
    row = c.fetchone()
    return row[0] if row else None

def has_already_submitted(user_id: int, flag: str) -> bool:
    c.execute('SELECT 1 FROM correct_submissions WHERE user_id = ? AND flag = ?', (user_id, flag))
    return c.fetchone() is not None

def record_correct_submission(user_id: int, flag: str):
    timestamp = datetime.now(ZoneInfo("America/New_York")).isoformat()
    c.execute(
        'INSERT INTO correct_submissions (user_id, flag, timestamp) VALUES (?, ?, ?)',
        (user_id, flag, timestamp)
    )
    conn.commit()

def record_incorrect_submission(user_id: int, flag: str, reason: str):
    timestamp = datetime.now(ZoneInfo("America/New_York")).isoformat()
    try:
        c.execute(
            'INSERT INTO incorrect_submissions (user_id, flag, timestamp, reason) VALUES (?, ?, ?, ?)',
            (user_id, flag, timestamp, reason)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Already recorded this incorrect submission before, ignore
        pass

class FlagSubmissionModal(discord.ui.Modal, title="Submit your flag"):
    flag_input = discord.ui.TextInput(label="Flag", placeholder="Enter your flag here")

    async def on_submit(self, interaction: discord.Interaction):
        user_flag = self.flag_input.value.strip()
        user_id = interaction.user.id

        points_for_flag = check_flag(user_flag)
        if points_for_flag is None:
            await interaction.response.send_message("❌ Incorrect flag, try again.", ephemeral=True)
            print(f"[FLAG] User {interaction.user} submitted incorrect flag: {user_flag}")
            record_incorrect_submission(user_id, user_flag, "wrong")
            return

        if has_already_submitted(user_id, user_flag):
            await interaction.response.send_message("⚠️ You have already submitted this flag.", ephemeral=True)
            print(f"[FLAG] User {interaction.user} re-submitted flag: {user_flag}")
            record_incorrect_submission(user_id, user_flag, "already_submitted")
            return

        record_correct_submission(user_id, user_flag)
        add_points(user_id, points_for_flag)
        new_points = get_points(user_id)

        await interaction.response.send_message(f"✅ Flag is correct! You earned {points_for_flag} points.\nTotal points: {new_points}", ephemeral=True)
        print(f"[FLAG] User {interaction.user} submitted flag: {user_flag} — Total: {new_points}")

class ConspiracyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        # Add leaderboard link button
        self.add_item(discord.ui.Button(
            label="Leaderboard",
            style=discord.ButtonStyle.link,
            url="https://leaderboard.maguireyounes.com/"
        ))

    @discord.ui.button(label="Submit Flag", style=discord.ButtonStyle.primary)
    async def submit_flag(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = FlagSubmissionModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Check Points", style=discord.ButtonStyle.secondary)
    async def check_points(self, interaction: discord.Interaction, button: discord.ui.Button):
        points = get_points(interaction.user.id)
        await interaction.response.send_message(f"🧮 You currently have {points} points.", ephemeral=True)

    @discord.ui.button(label="Challenge Status", style=discord.ButtonStyle.success)
    async def challenge_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        c.execute('SELECT challenge_name, flag, points FROM flags')
        challenges = c.fetchall()

        # Get all user's solved flags for quick lookup
        c.execute('SELECT flag FROM correct_submissions WHERE user_id = ?', (user_id,))
        solved_flags = {row[0] for row in c.fetchall()}

        lines = []
        header = f"{'Challenge':<20} | {'Status':<12} | {'Points':<6}"
        separator = "-" * len(header)
        lines.append(header)
        lines.append(separator)

        for name, flag, pts in challenges:
            status = "✅ Solved" if flag in solved_flags else "❌ Not Solved"
            lines.append(f"{name:<20} | {status:<12} | {pts:<6}")

        message = "```\n" + "\n".join(lines) + "\n```"
        await interaction.response.send_message(message, ephemeral=True)

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        print(f"[DM from {message.author}]: {message.content}")
        view = ConspiracyView()
        await message.channel.send(
            content="👋 Welcome to **THE CONSPIRACY**.\nUse the buttons below to submit flags, check your points, or see challenge status.",
            view=view
        )

client.run(TOKEN)
