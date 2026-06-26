
# Full updated bot.py with channel setup
import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import checks
import sqlite3
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()
TOKEN=os.getenv("TOKEN")

conn=sqlite3.connect("tracker.db")
cursor=conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS codes(code TEXT PRIMARY KEY,added_by TEXT,added_at TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS redeemed(code TEXT,user_id TEXT,username TEXT,redeemed_at TEXT,UNIQUE(code,user_id))")
cursor.execute("CREATE TABLE IF NOT EXISTS guild_settings(guild_id TEXT PRIMARY KEY,channel_id TEXT)")
conn.commit()

intents=discord.Intents.default()
bot=commands.Bot(command_prefix="!",intents=intents)

class CodeView(discord.ui.View):
    def __init__(self,code):
        super().__init__(timeout=None); self.code=code
    @discord.ui.button(label="Redeem",style=discord.ButtonStyle.green)
    async def redeem(self,i,b):
        try:
            cursor.execute("INSERT INTO redeemed VALUES(?,?,?,?)",(self.code,str(i.user.id),i.user.name,datetime.now().isoformat())); conn.commit()
            await i.response.send_message(f"✅ You redeemed `{self.code}`",ephemeral=True)
        except sqlite3.IntegrityError:
            await i.response.send_message("⚠️ You already redeemed this code.",ephemeral=True)
    @discord.ui.button(label="Status",style=discord.ButtonStyle.blurple)
    async def status(self,i,b):
        cursor.execute("SELECT username FROM redeemed WHERE code=?",(self.code,))
        users=[r[0] for r in cursor.fetchall()]
        txt="Nobody redeemed this yet." if not users else "\n".join(users)
        await i.response.send_message(f"**{self.code}**\n```\n{txt}\n```",ephemeral=True)

class SetupView(discord.ui.View):
    @discord.ui.select(cls=discord.ui.ChannelSelect,channel_types=[discord.ChannelType.text],placeholder="Select code channel")
    async def pick(self,i,s):
        ch=s.values[0]
        cursor.execute("INSERT OR REPLACE INTO guild_settings VALUES(?,?)",(str(i.guild.id),str(ch.id))); conn.commit()
        await i.response.edit_message(content=f"✅ Bot channel set to {ch.mention}",view=None)

@bot.event
async def on_ready():
    bot.add_view(CodeView("persistent"))
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

@bot.tree.command(
    name="setchannel",
    description="Choose the channel for redeem codes"
)
@checks.has_permissions(administrator=True)
async def setchannel(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Choose the channel for redeem codes:",
        view=SetupView(),
        ephemeral=True
    )

def get_channel(guild):
    cursor.execute("SELECT channel_id FROM guild_settings WHERE guild_id=?",(str(guild.id),))
    r=cursor.fetchone()
    return guild.get_channel(int(r[0])) if r else None

@bot.tree.command(description="Add one or more codes")
async def addcode(interaction:discord.Interaction,codes:str):
    channel=get_channel(interaction.guild)
    if not channel:
        return await interaction.response.send_message(
    "⚠️ Please run **/setchannel** first to choose where redeem codes should be posted.",
    ephemeral=True
)
    added=[]
    for code in [c.strip().upper() for c in codes.replace(",","\n").split("\n") if c.strip()]:
        cursor.execute("SELECT code FROM codes WHERE code=?",(code,))
        if cursor.fetchone(): continue
        cursor.execute("INSERT INTO codes VALUES(?,?,?)",(code,interaction.user.name,datetime.now().isoformat())); conn.commit()
        await channel.send(f"## ✅ New Redeem Code\n`{code}`",view=CodeView(code))
        added.append(code)
    await interaction.response.send_message(f"Added {len(added)} code(s).",ephemeral=True)

@bot.tree.command()
async def allcodes(interaction):
    cursor.execute("SELECT code FROM codes ORDER BY added_at DESC")
    rows=cursor.fetchall()
    if not rows: return await interaction.response.send_message("No codes found.",ephemeral=True)
    await interaction.response.send_message("```\n"+"\n".join(r[0] for r in rows)+"\n```",ephemeral=True)

@bot.tree.command()
@checks.has_permissions(administrator=True)
async def deletecode(interaction,code:str):
    code=code.upper(); cursor.execute("DELETE FROM codes WHERE code=?",(code,)); cursor.execute("DELETE FROM redeemed WHERE code=?",(code,)); conn.commit()
    await interaction.response.send_message(f"Deleted {code}",ephemeral=True)

@bot.tree.command()
@checks.has_permissions(administrator=True)
async def deleteallcodes(interaction):
    cursor.execute("DELETE FROM codes"); cursor.execute("DELETE FROM redeemed"); conn.commit()
    await interaction.response.send_message("All codes deleted.",ephemeral=True)

@bot.tree.command()
async def redeemstatus(interaction,code:str):
    code=code.upper(); cursor.execute("SELECT code FROM codes WHERE code=?",(code,))
    if not cursor.fetchone(): return await interaction.response.send_message("Code not found.",ephemeral=True)
    cursor.execute("SELECT username FROM redeemed WHERE code=?",(code,))
    u=[x[0] for x in cursor.fetchall()]
    await interaction.response.send_message(f"{code} has no redeemers yet." if not u else f"**{code} redeemed by:**\n```\n"+"\n".join(u)+"\n```",ephemeral=True)

@bot.tree.command()
async def mymissing(interaction):
    cursor.execute("SELECT code FROM codes"); allc={r[0] for r in cursor.fetchall()}
    cursor.execute("SELECT code FROM redeemed WHERE user_id=?",(str(interaction.user.id),)); red={r[0] for r in cursor.fetchall()}
    miss=sorted(allc-red)
    await interaction.response.send_message("🎉 You redeemed everything!" if not miss else "Missing codes:\n```\n"+"\n".join(miss)+"\n```",ephemeral=True)

bot.run(TOKEN)
