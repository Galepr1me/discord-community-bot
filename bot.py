import discord
from discord.ext import commands
import sqlite3
import random
import asyncio
import json
import os
from datetime import datetime, timedelta
from flask import Flask
import threading

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Database setup
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # XP and levels table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1, 
                  last_message TIMESTAMP, total_messages INTEGER DEFAULT 0)''')
    
    # Bot configuration table
    c.execute('''CREATE TABLE IF NOT EXISTS config
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Game data table
    c.execute('''CREATE TABLE IF NOT EXISTS game_data
                 (user_id INTEGER PRIMARY KEY, health INTEGER DEFAULT 100, 
                  gold INTEGER DEFAULT 0, inventory TEXT DEFAULT '{}', 
                  location TEXT DEFAULT 'town', level INTEGER DEFAULT 1)''')
    
    # Default configuration
    default_config = {
        'xp_per_message': '15',
        'xp_cooldown': '60',
        'level_multiplier': '100',
        'xp_channel': 'None',
        'game_enabled': 'True',
        'welcome_message': 'Welcome to the server, {user}!',
        'level_up_message': 'Congratulations {user}! You reached level {level}!'
    }
    
    for key, value in default_config.items():
        c.execute('INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)', (key, value))
    
    conn.commit()
    conn.close()

# Utility functions
def get_config(key):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT value FROM config WHERE key = ?', (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def set_config(key, value):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if not result:
        c.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        result = (user_id, 0, 1, None, 0)
    conn.close()
    return result

def update_user_xp(user_id, xp_gain):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    user_data = get_user_data(user_id)
    current_xp = user_data[1]
    current_level = user_data[2]
    total_messages = user_data[4]
    
    new_xp = current_xp + xp_gain
    level_multiplier = int(get_config('level_multiplier'))
    new_level = int(new_xp // level_multiplier) + 1
    
    now_str = datetime.now().isoformat()
    c.execute('''UPDATE users SET xp = ?, level = ?, last_message = ?, total_messages = ?
                 WHERE user_id = ?''', 
              (new_xp, new_level, now_str, total_messages + 1, user_id))
    conn.commit()
    conn.close()
    
    return new_level > current_level, new_level

# XP System
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Check XP cooldown
    user_data = get_user_data(message.author.id)
    last_message = user_data[3]
    cooldown = int(get_config('xp_cooldown'))
    
    if last_message:
        try:
            last_time = datetime.fromisoformat(last_message)
            if datetime.now() - last_time < timedelta(seconds=cooldown):
                await bot.process_commands(message)
                return
        except (ValueError, TypeError):
            # Handle old datetime format or invalid data
            pass
    
    # Award XP
    xp_gain = int(get_config('xp_per_message'))
    level_up, new_level = update_user_xp(message.author.id, xp_gain)
    
    if level_up:
        level_up_msg = get_config('level_up_message')
        formatted_msg = level_up_msg.format(user=message.author.mention, level=new_level)
        
        xp_channel = get_config('xp_channel')
        if xp_channel != 'None':
            channel = bot.get_channel(int(xp_channel))
            if channel:
                await channel.send(formatted_msg)
        else:
            await message.channel.send(formatted_msg)
    
    await bot.process_commands(message)

# Admin Configuration Commands
@bot.command(name='config')
@commands.has_permissions(administrator=True)
async def config_command(ctx, action=None, key=None, *, value=None):
    """Configure bot settings. Usage: !config [set/get/list] [key] [value]"""
    
    if action == 'list':
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('SELECT key, value FROM config')
        configs = c.fetchall()
        conn.close()
        
        embed = discord.Embed(title="Bot Configuration", color=0x00ff00)
        for key, val in configs:
            embed.add_field(name=key, value=val, inline=False)
        await ctx.send(embed=embed)
        
    elif action == 'get' and key:
        value = get_config(key)
        await ctx.send(f"**{key}**: {value}")
        
    elif action == 'set' and key and value:
        set_config(key, value)
        await ctx.send(f"✅ Set **{key}** to: {value}")
        
    else:
        await ctx.send("Usage: `!config [set/get/list] [key] [value]`")

# XP and Level Commands
@bot.command(name='level')
async def level_command(ctx, user: discord.Member = None):
    """Check your level or another user's level"""
    target = user or ctx.author
    user_data = get_user_data(target.id)
    
    embed = discord.Embed(title=f"{target.display_name}'s Level", color=0x3498db)
    embed.add_field(name="Level", value=user_data[2], inline=True)
    embed.add_field(name="XP", value=user_data[1], inline=True)
    embed.add_field(name="Messages", value=user_data[4], inline=True)
    
    level_multiplier = int(get_config('level_multiplier'))
    next_level_xp = user_data[2] * level_multiplier
    progress = user_data[1] - ((user_data[2] - 1) * level_multiplier)
    
    embed.add_field(name="Progress to Next Level", 
                   value=f"{progress}/{level_multiplier}", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='leaderboard')
async def leaderboard_command(ctx, limit: int = 10):
    """Show the XP leaderboard"""
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT user_id, xp, level FROM users ORDER BY xp DESC LIMIT ?', (limit,))
    top_users = c.fetchall()
    conn.close()
    
    embed = discord.Embed(title="🏆 XP Leaderboard", color=0xffd700)
    
    for i, (user_id, xp, level) in enumerate(top_users, 1):
        user = bot.get_user(user_id)
        name = user.display_name if user else f"User {user_id}"
        embed.add_field(name=f"{i}. {name}", 
                       value=f"Level {level} | {xp} XP", inline=False)
    
    await ctx.send(embed=embed)

# ASCII Adventure Game
class Game:
    def __init__(self):
        self.locations = {
            'town': {
                'description': '🏘️ You are in a peaceful town square.',
                'actions': ['explore', 'shop', 'rest'],
                'connections': ['forest', 'cave']
            },
            'forest': {
                'description': '🌲 You are in a dark forest. Strange noises echo around you.',
                'actions': ['hunt', 'gather', 'explore'],
                'connections': ['town', 'cave'],
                'monsters': ['Goblin', 'Wolf']
            },
            'cave': {
                'description': '🕳️ You enter a mysterious cave. Treasures might be hidden here.',
                'actions': ['mine', 'explore', 'dig'],
                'connections': ['town', 'forest'],
                'monsters': ['Bat', 'Spider', 'Orc']
            }
        }
        
        self.items = {
            'Health Potion': {'price': 20, 'effect': 'heal'},
            'Sword': {'price': 100, 'effect': 'weapon'},
            'Shield': {'price': 80, 'effect': 'defense'},
            'Magic Scroll': {'price': 150, 'effect': 'magic'}
        }

    def get_game_data(self, user_id):
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('SELECT * FROM game_data WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        if not result:
            c.execute('INSERT INTO game_data (user_id) VALUES (?)', (user_id,))
            conn.commit()
            result = (user_id, 100, 0, '{}', 'town', 1)
        conn.close()
        return result

    def update_game_data(self, user_id, health, gold, inventory, location, level):
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('''UPDATE game_data SET health = ?, gold = ?, inventory = ?, 
                     location = ?, level = ? WHERE user_id = ?''',
                  (health, gold, inventory, location, level, user_id))
        conn.commit()
        conn.close()

game = Game()

@bot.command(name='adventure')
async def adventure_command(ctx):
    """Start or continue your adventure!"""
    if get_config('game_enabled') != 'True':
        await ctx.send("The adventure game is currently disabled.")
        return
        
    user_data = game.get_game_data(ctx.author.id)
    location = user_data[4]
    health = user_data[1]
    gold = user_data[2]
    
    loc_info = game.locations[location]
    
    embed = discord.Embed(title="🎮 Adventure Game", color=0x9b59b6)
    embed.add_field(name="Location", value=loc_info['description'], inline=False)
    embed.add_field(name="Health", value=f"❤️ {health}/100", inline=True)
    embed.add_field(name="Gold", value=f"💰 {gold}", inline=True)
    embed.add_field(name="Available Actions", 
                   value=", ".join(loc_info['actions']), inline=False)
    
    if 'connections' in loc_info:
        embed.add_field(name="Travel to", 
                       value=", ".join(loc_info['connections']), inline=False)
    
    embed.set_footer(text="Use !action <action_name> to perform actions")
    
    await ctx.send(embed=embed)

@bot.command(name='action')
async def action_command(ctx, *, action):
    """Perform an action in the adventure game"""
    if get_config('game_enabled') != 'True':
        return
        
    user_data = game.get_game_data(ctx.author.id)
    user_id, health, gold, inventory_str, location, level = user_data
    inventory = json.loads(inventory_str)
    
    loc_info = game.locations[location]
    
    # Handle movement
    if action in game.locations:
        if action in loc_info.get('connections', []):
            game.update_game_data(user_id, health, gold, inventory_str, action, level)
            await ctx.send(f"🚶 You travel to the {action}.")
            await adventure_command(ctx)
            return
        else:
            await ctx.send("❌ You can't travel there from your current location.")
            return
    
    # Handle actions
    if action not in loc_info['actions']:
        await ctx.send(f"❌ You can't {action} here. Available actions: {', '.join(loc_info['actions'])}")
        return
    
    result = ""
    
    if action == 'explore':
        outcomes = [
            "🔍 You found a hidden treasure! +50 gold",
            "🕷️ You encountered a spider but escaped! -10 health",
            "💎 You discovered a valuable gem! +30 gold",
            "🍄 You found some berries and feel refreshed! +20 health",
            "❌ You found nothing interesting."
        ]
        outcome = random.choice(outcomes)
        result = outcome
        
        if "50 gold" in outcome:
            gold += 50
        elif "30 gold" in outcome:
            gold += 30
        elif "10 health" in outcome:
            health = max(0, health - 10)
        elif "20 health" in outcome:
            health = min(100, health + 20)
    
    elif action == 'hunt' and location == 'forest':
        if random.random() < 0.6:  # 60% success rate
            monster = random.choice(loc_info['monsters'])
            gold_reward = random.randint(20, 50)
            health_loss = random.randint(5, 15)
            gold += gold_reward
            health = max(0, health - health_loss)
            result = f"⚔️ You defeated a {monster}! +{gold_reward} gold, -{health_loss} health"
        else:
            result = "🏃 You couldn't find any monsters to hunt."
    
    elif action == 'shop' and location == 'town':
        shop_embed = discord.Embed(title="🏪 Town Shop", color=0xe74c3c)
        for item, info in game.items.items():
            shop_embed.add_field(name=item, value=f"💰 {info['price']} gold", inline=True)
        shop_embed.set_footer(text="Use !buy <item_name> to purchase")
        await ctx.send(embed=shop_embed)
        return
    
    elif action == 'rest' and location == 'town':
        health = 100
        result = "😴 You rest at the inn and restore full health!"
    
    elif action == 'mine' and location == 'cave':
        gold_found = random.randint(10, 40)
        gold += gold_found
        result = f"⛏️ You mined some precious ore! +{gold_found} gold"
    
    else:
        result = f"🤷 You {action} but nothing happens."
    
    # Update game data
    game.update_game_data(user_id, health, gold, json.dumps(inventory), location, level)
    
    embed = discord.Embed(title="Action Result", description=result, color=0x2ecc71)
    embed.add_field(name="Health", value=f"❤️ {health}/100", inline=True)
    embed.add_field(name="Gold", value=f"💰 {gold}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='buy')
async def buy_command(ctx, *, item_name):
    """Buy an item from the shop"""
    user_data = game.get_game_data(ctx.author.id)
    user_id, health, gold, inventory_str, location, level = user_data
    
    if location != 'town':
        await ctx.send("❌ You can only shop in town!")
        return
    
    if item_name not in game.items:
        await ctx.send(f"❌ Item '{item_name}' not found in shop.")
        return
    
    item = game.items[item_name]
    if gold < item['price']:
        await ctx.send(f"❌ You need {item['price']} gold but only have {gold}.")
        return
    
    inventory = json.loads(inventory_str)
    inventory[item_name] = inventory.get(item_name, 0) + 1
    gold -= item['price']
    
    game.update_game_data(user_id, health, gold, json.dumps(inventory), location, level)
    
    await ctx.send(f"✅ You bought {item_name} for {item['price']} gold!")

@bot.command(name='inventory')
async def inventory_command(ctx):
    """Check your inventory"""
    user_data = game.get_game_data(ctx.author.id)
    inventory_str = user_data[3]
    inventory = json.loads(inventory_str)
    
    if not inventory:
        await ctx.send("🎒 Your inventory is empty.")
        return
    
    embed = discord.Embed(title="🎒 Your Inventory", color=0x95a5a6)
    for item, count in inventory.items():
        embed.add_field(name=item, value=f"x{count}", inline=True)
    
    await ctx.send(embed=embed)

# Bot events
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    init_db()

@bot.event
async def on_member_join(member):
    welcome_msg = get_config('welcome_message')
    if welcome_msg and welcome_msg != 'None':
        formatted_msg = welcome_msg.format(user=member.mention)
        # Try to send to system channel, otherwise first text channel
        channel = member.guild.system_channel
        if not channel:
            channel = next((ch for ch in member.guild.text_channels if ch.permissions_for(member.guild.me).send_messages), None)
        if channel:
            await channel.send(formatted_msg)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found. Use `!help` to see available commands.")
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")

# Help command
@bot.command(name='help_custom')
async def help_custom(ctx):
    """Show all available commands"""
    embed = discord.Embed(title="🤖 Bot Commands", color=0x3498db)
    
    embed.add_field(name="📊 XP System", 
                   value="`!level` - Check your level\n`!leaderboard` - View top users", 
                   inline=False)
    
    embed.add_field(name="🎮 Adventure Game", 
                   value="`!adventure` - Start/continue adventure\n`!action <action>` - Perform action\n`!inventory` - Check inventory\n`!buy <item>` - Buy from shop", 
                   inline=False)
    
    embed.add_field(name="⚙️ Admin Commands", 
                   value="`!config list` - View all settings\n`!config set <key> <value>` - Change setting\n`!config get <key>` - Get setting value", 
                   inline=False)
    
    embed.add_field(name="📋 Configurable Settings", 
                   value="• `xp_per_message` - XP gained per message\n• `xp_cooldown` - Cooldown between XP gains (seconds)\n• `level_multiplier` - XP needed per level\n• `game_enabled` - Enable/disable adventure game\n• `welcome_message` - Message for new members\n• `level_up_message` - Level up notification", 
                   inline=False)
    
    await ctx.send(embed=embed)

# Flask web server to keep Render happy
app = Flask(__name__)

@app.route('/')
def home():
    return "Discord Bot is running! 🤖"

@app.route('/health')
def health():
    return {"status": "healthy", "bot": "online"}

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("Please set the DISCORD_TOKEN environment variable")
    else:
        # Start Flask server in a separate thread
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        
        print("Flask server started")
        print("Starting Discord bot...")
        
        try:
            bot.run(token)
        except Exception as e:
            print(f"Bot error: {e}")
            # Keep Flask running even if bot fails
            flask_thread.join()
