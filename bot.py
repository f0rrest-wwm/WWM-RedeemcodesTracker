import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import checks
import sqlite3
from dotenv import load_dotenv
import os
from datetime import datetime

# =========================
# LOAD TOKEN
# =========================

load_dotenv()
TOKEN = os.getenv("TOKEN")

# =========================
# DATABASE
# =========================

conn = sqlite3.connect("tracker.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS codes (
    code TEXT PRIMARY KEY,
    added_by TEXT,
    added_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS redeemed (
    code TEXT,
    user_id TEXT,
    username TEXT,
    redeemed_at TEXT,
    UNIQUE(code, user_id)
)
""")

conn.commit()

# =========================
# BOT SETUP
# =========================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# BUTTON UI
# =========================

class CodeView(discord.ui.View):
    def __init__(self, code):
        super().__init__(timeout=None)
        self.code = code

    @discord.ui.button(label="Redeem", style=discord.ButtonStyle.green)
    async def redeem(self, interaction: discord.Interaction, button: discord.ui.Button):

        try:
            cursor.execute(
                "INSERT INTO redeemed VALUES (?, ?, ?, ?)",
                (
                    self.code,
                    str(interaction.user.id),
                    interaction.user.name,
                    datetime.now().isoformat()
                )
            )
            conn.commit()

            await interaction.response.send_message(
                f"✅ You redeemed `{self.code}`",
                ephemeral=True
            )

        except sqlite3.IntegrityError:
            await interaction.response.send_message(
                "⚠️ You already redeemed this code.",
                ephemeral=True
            )

    @discord.ui.button(label="Status", style=discord.ButtonStyle.blurple)
    async def status(self, interaction: discord.Interaction, button: discord.ui.Button):

        cursor.execute(
            "SELECT username FROM redeemed WHERE code=?",
            (self.code,)
        )

        users = [row[0] for row in cursor.fetchall()]

        if not users:
            text = "Nobody redeemed this yet."
        else:
            text = "\n".join(users)

        await interaction.response.send_message(
            f"**{self.code}**\n```\n{text}\n```",
            ephemeral=True
        )

# =========================
# READY
# =========================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

# =========================
# ADD CODE
# =========================

@bot.tree.command(name="addcode", description="Add one or more codes")
async def addcode(interaction: discord.Interaction, codes: str):

    split_codes = [
        c.strip().upper()
        for c in codes.replace(",", "\n").split("\n")
        if c.strip()
    ]

    added = []
    duplicates = []

    for code in split_codes:

        cursor.execute("SELECT code FROM codes WHERE code=?", (code,))
        if cursor.fetchone():
            duplicates.append(code)
            continue

        cursor.execute(
            "INSERT INTO codes VALUES (?, ?, ?)",
            (code, interaction.user.name, datetime.now().isoformat())
        )

        added.append(code)

        # POST PUBLIC MESSAGE WITH BUTTONS
        await interaction.channel.send(
            f"## ✅ New Redeem Code\n`{code}`",
            view=CodeView(code)
        )

    conn.commit()

    await interaction.response.send_message(
        f"Added {len(added)} code(s).",
        ephemeral=True
    )

# =========================
# ALL CODES
# =========================

@bot.tree.command(name="allcodes", description="Show all codes")
async def allcodes(interaction: discord.Interaction):

    cursor.execute("SELECT code FROM codes ORDER BY added_at DESC")
    rows = cursor.fetchall()

    if not rows:
        await interaction.response.send_message("No codes found.", ephemeral=True)
        return

    text = "\n".join(row[0] for row in rows)

    await interaction.response.send_message(f"```\n{text}\n```", ephemeral=True)

# =========================
# DELETE ONE CODE
# =========================

@bot.tree.command(name="deletecode", description="Delete a code")
@checks.has_permissions(administrator=True)
async def deletecode(interaction: discord.Interaction, code: str):

    code = code.upper()

    cursor.execute("DELETE FROM codes WHERE code=?", (code,))
    cursor.execute("DELETE FROM redeemed WHERE code=?", (code,))
    conn.commit()

    await interaction.response.send_message(f"Deleted {code}", ephemeral=True)

# =========================
# DELETE ALL
# =========================

@bot.tree.command(name="deleteallcodes", description="Delete all codes")
@checks.has_permissions(administrator=True)
async def deleteallcodes(interaction: discord.Interaction):

    cursor.execute("DELETE FROM codes")
    cursor.execute("DELETE FROM redeemed")
    conn.commit()

    await interaction.response.send_message("All codes deleted.", ephemeral=True)

# =========================
# STATUS OF A CODE
# =========================

@bot.tree.command(name="redeemstatus", description="Check redeemed users for a code")
async def redeemstatus(interaction: discord.Interaction, code: str):

    code = code.upper()

    cursor.execute("SELECT username FROM redeemed WHERE code=?", (code,))
    users = [r[0] for r in cursor.fetchall()]

    cursor.execute("SELECT code FROM codes WHERE code=?", (code,))
    exists = cursor.fetchone()

    if not exists:
        await interaction.response.send_message("Code not found.", ephemeral=True)
        return

    if not users:
        await interaction.response.send_message(f"{code} has no redeemers yet.", ephemeral=True)
        return

    await interaction.response.send_message(
        f"**{code} redeemed by:**\n```\n" + "\n".join(users) + "\n```",
        ephemeral=True
    )

# =========================
# MY MISSING CODES
# =========================

@bot.tree.command(name="mymissing", description="Codes you haven't redeemed")
async def mymissing(interaction: discord.Interaction):

    cursor.execute("SELECT code FROM codes")
    all_codes = {r[0] for r in cursor.fetchall()}

    cursor.execute("SELECT code FROM redeemed WHERE user_id=?", (str(interaction.user.id),))
    redeemed = {r[0] for r in cursor.fetchall()}

    missing = sorted(all_codes - redeemed)

    if not missing:
        await interaction.response.send_message("🎉 You redeemed everything!", ephemeral=True)
        return

    await interaction.response.send_message(
        "Missing codes:\n```\n" + "\n".join(missing) + "\n```",
        ephemeral=True
    )

# =========================
# RUN BOT
# =========================

bot.run(TOKEN)