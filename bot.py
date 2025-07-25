import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import json
import os
from datetime import datetime, timedelta
from flask import Flask
import threading

# Bot setup - Remove default help command
intents = discord.Intents.default()
intents.message_content = True
# Note: members intent requires verification for bots in 100+ servers
# Our username caching system works without it
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Database setup
def get_db_connection():
    """Get database connection - PostgreSQL for cloud with DATABASE_URL, SQLite otherwise"""
    database_url = os.getenv('DATABASE_URL')
    
    if database_url and database_url.startswith('postgresql://'):
        # Use external PostgreSQL (Supabase, etc.)
        try:
            import psycopg2
            print(f"🗄️ Attempting to connect to PostgreSQL database...")
            
            # Add connection timeout and better error handling
            conn = psycopg2.connect(
                database_url,
                connect_timeout=10,
                sslmode='require'
            )
            print(f"✅ Successfully connected to PostgreSQL database")
            return conn
            
        except ImportError:
            print("❌ psycopg2 not installed. Install with: pip install psycopg2-binary")
            print("🔄 Falling back to SQLite...")
            db_path = get_db_path()
            print(f"🗄️ Using SQLite database at: {db_path}")
            return sqlite3.connect(db_path)
            
        except Exception as e:
            print(f"❌ PostgreSQL connection failed: {e}")
            print("🔄 Falling back to SQLite...")
            db_path = get_db_path()
            print(f"🗄️ Using SQLite database at: {db_path}")
            return sqlite3.connect(db_path)
    else:
        # Use SQLite for local development
        db_path = get_db_path()
        print(f"🗄️ Using SQLite database at: {db_path}")
        return sqlite3.connect(db_path)

def get_db_path():
    """Get the appropriate SQLite database path for the environment"""
    # Check if we're in a cloud environment
    if os.getenv('RENDER') or os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('PORT'):
        # Use /tmp for cloud hosting (ephemeral but works)
        return '/tmp/bot_data.db'
    else:
        # Use local file for development
        return 'bot_data.db'

def init_db():
    conn = get_db_connection()
    database_url = os.getenv('DATABASE_URL')
    is_postgres = database_url and database_url.startswith('postgresql://')
    c = conn.cursor()
    
    # XP and levels table with username cache
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1, 
                  last_message TIMESTAMP, total_messages INTEGER DEFAULT 0, 
                  username TEXT, display_name TEXT)''')
    
    # Bot configuration table
    c.execute('''CREATE TABLE IF NOT EXISTS config
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Game data table with proper schema migration
    c.execute('''CREATE TABLE IF NOT EXISTS game_data
                 (user_id INTEGER PRIMARY KEY, health INTEGER DEFAULT 100, 
                  gold INTEGER DEFAULT 0, inventory TEXT DEFAULT '{}', 
                  location TEXT DEFAULT 'town', level INTEGER DEFAULT 1,
                  adventure_xp INTEGER DEFAULT 0, monsters_defeated INTEGER DEFAULT 0,
                  last_daily_quest DATE, daily_quest_progress TEXT DEFAULT '{}')''')
    
    # Database version tracking for migrations
    c.execute('''CREATE TABLE IF NOT EXISTS db_version
                 (version INTEGER PRIMARY KEY)''')
    
    # Check current database version
    c.execute('SELECT version FROM db_version ORDER BY version DESC LIMIT 1')
    current_version = c.fetchone()
    current_version = current_version[0] if current_version else 0
    
    # Perform migrations if needed
    if current_version < 1:
        # Migration 1: Add new columns to game_data if they don't exist
        try:
            c.execute('ALTER TABLE game_data ADD COLUMN adventure_xp INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            c.execute('ALTER TABLE game_data ADD COLUMN monsters_defeated INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('ALTER TABLE game_data ADD COLUMN last_daily_quest DATE')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('ALTER TABLE game_data ADD COLUMN daily_quest_progress TEXT DEFAULT "{}"')
        except sqlite3.OperationalError:
            pass
        
        c.execute('INSERT OR REPLACE INTO db_version (version) VALUES (1)')
        print("✅ Database migrated to version 1")
    
    if current_version < 2:
        # Migration 2: Add username cache columns
        try:
            c.execute('ALTER TABLE users ADD COLUMN username TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('ALTER TABLE users ADD COLUMN display_name TEXT')
        except sqlite3.OperationalError:
            pass
        
        c.execute('INSERT OR REPLACE INTO db_version (version) VALUES (2)')
        print("✅ Database migrated to version 2")
    
    # Default configuration
    default_config = {
        'xp_per_message': '15',
        'xp_cooldown': '60',
        'level_multiplier': '100',  # Base XP for first level up
        'level_scaling_factor': '1.2',  # How much harder each level gets (1.2 = 20% increase)
        'xp_channel': 'None',
        'game_enabled': 'True',
        'welcome_message': 'Welcome to the server, {user}!',
        'level_up_message': 'Congratulations {user}! You reached level {level}!',
        'rare_event_chance': '5',
        'legendary_event_chance': '1',
        'daily_quests_enabled': 'True',
        'adventure_leaderboard_enabled': 'True',
        'boss_encounter_chance': '3'
    }
    
    for key, value in default_config.items():
        c.execute('INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)', (key, value))
    
    conn.commit()
    conn.close()

# Utility functions
def get_config(key):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT value FROM config WHERE key = ?', (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def set_config(key, value):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if not result:
        c.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        result = (user_id, 0, 1, None, 0, None, None)  # Include new username columns
    conn.close()
    return result

def get_user_display_name(ctx, user_id):
    """Get user display name with multiple fallback methods"""
    # Method 1: Try to get server member (for current nickname)
    try:
        member = ctx.guild.get_member(user_id)
        if member:
            return member.display_name
    except:
        pass
    
    # Method 2: Try bot cache
    try:
        user = bot.get_user(user_id)
        if user:
            return user.display_name
    except:
        pass
    
    # Method 3: Get cached name from database
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT display_name, username FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        
        if result:
            cached_display_name, cached_username = result
            if cached_display_name:
                return cached_display_name
            elif cached_username:
                return cached_username
    except:
        pass
    
    # Method 4: Fallback to User ID
    return f"User {user_id}"

async def get_user_display_name_async(ctx, user_id):
    """Async version with API fetch capability"""
    # Try sync methods first
    name = get_user_display_name(ctx, user_id)
    if not name.startswith("User "):
        return name
    
    # Method 2: Try to fetch user from Discord API (async)
    try:
        user = await bot.fetch_user(user_id)
        if user:
            return user.display_name
    except:
        pass
    
    # Fallback to the sync result
    return name

def calculate_level_from_xp(total_xp):
    """Calculate level based on progressive XP requirements"""
    base_xp = int(get_config('level_multiplier'))  # Base XP for level 1->2
    scaling_factor = float(get_config('level_scaling_factor') or '1.2')
    level = 1
    xp_needed = 0
    
    while total_xp >= xp_needed:
        # Each level requires more XP: base_xp * level * scaling_factor^(level-1)
        level_xp_requirement = int(base_xp * level * (scaling_factor ** (level - 1)))
        xp_needed += level_xp_requirement
        
        if total_xp >= xp_needed:
            level += 1
        else:
            break
    
    return level

def calculate_xp_for_level(target_level):
    """Calculate total XP needed to reach a specific level"""
    if target_level <= 1:
        return 0
    
    base_xp = int(get_config('level_multiplier'))
    scaling_factor = float(get_config('level_scaling_factor') or '1.2')
    total_xp = 0
    
    for level in range(1, target_level):
        level_xp_requirement = int(base_xp * level * (scaling_factor ** (level - 1)))
        total_xp += level_xp_requirement
    
    return total_xp

def calculate_xp_for_next_level(current_level):
    """Calculate XP needed for the next level"""
    base_xp = int(get_config('level_multiplier'))
    scaling_factor = float(get_config('level_scaling_factor') or '1.2')
    return int(base_xp * current_level * (scaling_factor ** (current_level - 1)))

def update_user_xp(user_id, xp_gain, username=None, display_name=None):
    conn = get_db_connection()
    c = conn.cursor()
    
    user_data = get_user_data(user_id)
    current_xp = user_data[1]
    current_level = user_data[2]
    total_messages = user_data[4]
    
    new_xp = current_xp + xp_gain
    new_level = calculate_level_from_xp(new_xp)
    
    now_str = datetime.now().isoformat()
    
    # Update with username cache
    c.execute('''UPDATE users SET xp = ?, level = ?, last_message = ?, total_messages = ?, 
                 username = ?, display_name = ? WHERE user_id = ?''', 
              (new_xp, new_level, now_str, total_messages + 1, username, display_name, user_id))
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
    
    # Award XP and cache user info
    xp_gain = int(get_config('xp_per_message'))
    username = message.author.name
    display_name = message.author.display_name
    
    level_up, new_level = update_user_xp(message.author.id, xp_gain, username, display_name)
    
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
@bot.command(name='status')
@commands.has_permissions(administrator=True)
async def status_command(ctx):
    """Show bot and database status (Admin only)"""
    import psutil
    import platform
    from datetime import datetime
    
    # Get bot uptime
    uptime = datetime.now() - datetime.fromtimestamp(psutil.Process().create_time())
    
    # Test database connection
    database_url = os.getenv('DATABASE_URL')
    db_status = "❌ Unknown"
    db_type = "Unknown"
    db_details = "No connection info"
    
    try:
        conn = get_db_connection()
        
        if database_url and database_url.startswith('postgresql://'):
            # Test PostgreSQL connection
            try:
                import psycopg2
                test_conn = psycopg2.connect(
                    database_url,
                    connect_timeout=5,
                    sslmode='require'
                )
                test_conn.close()
                db_status = "✅ Connected"
                db_type = "PostgreSQL (Supabase)"
                # Extract host from URL for display
                host_start = database_url.find('@') + 1
                host_end = database_url.find(':', host_start)
                host = database_url[host_start:host_end] if host_end > host_start else "Unknown"
                db_details = f"Host: {host}\nSSL: Required"
            except Exception as e:
                db_status = f"❌ PostgreSQL Failed: {str(e)[:50]}..."
                db_type = "PostgreSQL (Failed - Using SQLite)"
                db_details = "Fallback to local SQLite"
        else:
            db_status = "✅ Connected"
            db_type = "SQLite (Local)"
            db_path = get_db_path()
            db_details = f"Path: {db_path}"
        
        # Test basic database operations
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM users')
        user_count = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM config')
        config_count = c.fetchone()[0]
        conn.close()
        
    except Exception as e:
        db_status = f"❌ Database Error: {str(e)[:50]}..."
        user_count = "Unknown"
        config_count = "Unknown"
    
    # Create status embed
    embed = discord.Embed(
        title="🤖 Bot Status Dashboard", 
        description="Complete system health check",
        color=0x00ff00 if "✅" in db_status else 0xff0000
    )
    
    # Bot Information
    bot_info = (
        f"🤖 **Bot User**: {bot.user.name}#{bot.user.discriminator}\n"
        f"🆔 **Bot ID**: {bot.user.id}\n"
        f"⏱️ **Uptime**: {str(uptime).split('.')[0]}\n"
        f"🌐 **Servers**: {len(bot.guilds)}\n"
        f"👥 **Cached Users**: {len(bot.users)}"
    )
    embed.add_field(name="📊 Bot Information", value=bot_info, inline=True)
    
    # Database Status
    db_info = (
        f"🗄️ **Type**: {db_type}\n"
        f"🔗 **Status**: {db_status}\n"
        f"📝 **Details**: {db_details}\n"
        f"👤 **Users**: {user_count}\n"
        f"⚙️ **Config Items**: {config_count}"
    )
    embed.add_field(name="🗄️ Database Status", value=db_info, inline=True)
    
    # System Information
    try:
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        system_info = (
            f"💻 **Platform**: {platform.system()} {platform.release()}\n"
            f"🧠 **CPU Usage**: {cpu_percent}%\n"
            f"💾 **Memory**: {memory.percent}% used\n"
            f"🐍 **Python**: {platform.python_version()}\n"
            f"📦 **Discord.py**: {discord.__version__}"
        )
    except:
        system_info = "❌ System info unavailable"
    
    embed.add_field(name="💻 System Information", value=system_info, inline=False)
    
    # Environment Variables Check
    env_status = []
    required_vars = ['DISCORD_TOKEN', 'DATABASE_URL']
    for var in required_vars:
        value = os.getenv(var)
        if var == 'DISCORD_TOKEN':
            status = "✅ Set" if value else "❌ Missing"
        elif var == 'DATABASE_URL':
            if value and value.startswith('postgresql://'):
                status = "✅ PostgreSQL URL"
            elif value:
                status = "⚠️ Invalid format"
            else:
                status = "❌ Not set (using SQLite)"
        env_status.append(f"**{var}**: {status}")
    
    embed.add_field(name="🔐 Environment Variables", value="\n".join(env_status), inline=False)
    
    # Add timestamp
    embed.timestamp = datetime.now()
    embed.set_footer(text="Status checked at")
    
    await ctx.send(embed=embed)

@bot.command(name='config')
@commands.has_permissions(administrator=True)
async def config_command(ctx, action=None, key=None, *, value=None):
    """Configure bot settings. Usage: !config [set/get/list] [key] [value]"""
    
    if action == 'list':
        conn = get_db_connection()
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
    
    current_level = user_data[2]
    current_xp = user_data[1]
    
    embed = discord.Embed(title=f"{target.display_name}'s Level", color=0x3498db)
    embed.add_field(name="Level", value=current_level, inline=True)
    embed.add_field(name="Total XP", value=f"{current_xp:,}", inline=True)
    embed.add_field(name="Messages", value=user_data[4], inline=True)
    
    # Calculate progress to next level
    current_level_xp = calculate_xp_for_level(current_level)
    next_level_xp = calculate_xp_for_level(current_level + 1)
    xp_needed_for_next = calculate_xp_for_next_level(current_level)
    progress = current_xp - current_level_xp
    
    embed.add_field(name="Progress to Next Level", 
                   value=f"{progress:,}/{xp_needed_for_next:,} XP", inline=False)
    
    # Add a progress bar
    progress_percentage = min(100, (progress / xp_needed_for_next) * 100)
    progress_bar = "█" * int(progress_percentage // 10) + "░" * (10 - int(progress_percentage // 10))
    embed.add_field(name="Progress Bar", 
                   value=f"`{progress_bar}` {progress_percentage:.1f}%", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='xp_table')
async def xp_table_command(ctx, max_level: int = 10):
    """Show XP requirements for different levels"""
    if max_level > 25:
        max_level = 25  # Prevent spam
    
    embed = discord.Embed(title="📊 XP Level Requirements", color=0x00ff00)
    
    table_text = "```\nLevel | XP for Level | Total XP\n"
    table_text += "------|-------------|----------\n"
    
    for level in range(1, max_level + 1):
        if level == 1:
            xp_for_level = 0
            total_xp = 0
        else:
            xp_for_level = calculate_xp_for_next_level(level - 1)
            total_xp = calculate_xp_for_level(level)
        
        table_text += f"{level:5} | {xp_for_level:11,} | {total_xp:9,}\n"
    
    table_text += "```"
    
    embed.description = table_text
    
    base_xp = int(get_config('level_multiplier'))
    scaling_factor = float(get_config('level_scaling_factor') or '1.2')
    
    embed.add_field(
        name="📈 Scaling Info", 
        value=f"Base XP: {base_xp}\nScaling Factor: {scaling_factor}x per level", 
        inline=True
    )
    
    embed.set_footer(text="Use !xp_table <number> to see more levels (max 25)")
    
    await ctx.send(embed=embed)

@bot.command(name='leaderboard')
@commands.cooldown(1, 30, commands.BucketType.guild)  # 1 use per 30 seconds per server
async def leaderboard_command(ctx, limit: int = 10):
    """Show the XP leaderboard"""
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT user_id, xp, level, username, display_name FROM users ORDER BY xp DESC LIMIT ?', (limit,))
    top_users = c.fetchall()
    conn.close()
    
    embed = discord.Embed(title="🏆 XP Leaderboard", color=0xffd700)
    
    if not top_users:
        embed.description = "No users found! Start chatting to gain XP!"
        await ctx.send(embed=embed)
        return
    
    leaderboard_text = ""
    for i, (user_id, xp, level, cached_username, cached_display_name) in enumerate(top_users, 1):
        # Try multiple methods to get user name
        name = None
        
        # Method 1: Try to get server member (for current nickname)
        try:
            member = ctx.guild.get_member(user_id)
            if member:
                name = member.display_name
        except:
            pass
        
        # Method 2: Try to fetch user from Discord API
        if not name:
            try:
                user = await bot.fetch_user(user_id)
                if user:
                    name = user.display_name
            except:
                pass
        
        # Method 3: Try bot cache
        if not name:
            try:
                user = bot.get_user(user_id)
                if user:
                    name = user.display_name
            except:
                pass
        
        # Method 4: Use cached display name from database
        if not name and cached_display_name:
            name = cached_display_name
        
        # Method 5: Use cached username from database
        if not name and cached_username:
            name = cached_username
        
        # Method 6: Fallback to User ID
        if not name:
            name = f"User {user_id}"
        
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
        leaderboard_text += f"{medal} **{name}**\n└ Level {level} • {xp:,} XP\n\n"
    
    embed.description = leaderboard_text
    embed.set_footer(text=f"Showing top {len(top_users)} users • Use !level to check your rank")
    
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
            'Health Potion': {'price': 20, 'effect': 'heal', 'value': 50},
            'Sword': {'price': 100, 'effect': 'weapon', 'value': 15},
            'Shield': {'price': 80, 'effect': 'defense', 'value': 10},
            'Magic Scroll': {'price': 150, 'effect': 'magic', 'value': 25}
        }
        
        self.bosses = {
            'forest': {'name': 'Giant Wolf Alpha', 'health': 80, 'gold': 200, 'xp': 100},
            'cave': {'name': 'Ancient Dragon', 'health': 120, 'gold': 500, 'xp': 200}
        }
        
        self.daily_quests = [
            {'name': 'Monster Hunter', 'description': 'Defeat 5 monsters', 'target': 5, 'reward': 100, 'type': 'monsters'},
            {'name': 'Explorer', 'description': 'Explore 10 times', 'target': 10, 'reward': 75, 'type': 'explore'},
            {'name': 'Miner', 'description': 'Mine 15 times', 'target': 15, 'reward': 80, 'type': 'mine'},
            {'name': 'Gold Collector', 'description': 'Collect 300 gold', 'target': 300, 'reward': 50, 'type': 'gold'}
        ]

    def get_game_data(self, user_id):
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('SELECT * FROM game_data WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        if not result:
            c.execute('INSERT INTO game_data (user_id) VALUES (?)', (user_id,))
            conn.commit()
            today = datetime.now().date().isoformat()
            result = (user_id, 100, 0, '{}', 'town', 1, 0, 0, today, '{}')
        conn.close()
        return result

    def update_game_data(self, user_id, health, gold, inventory, location, level, adventure_xp=None, monsters_defeated=None, daily_quest_progress=None):
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        
        if adventure_xp is not None and monsters_defeated is not None and daily_quest_progress is not None:
            c.execute('''UPDATE game_data SET health = ?, gold = ?, inventory = ?, 
                         location = ?, level = ?, adventure_xp = ?, monsters_defeated = ?, daily_quest_progress = ?
                         WHERE user_id = ?''',
                      (health, gold, inventory, location, level, adventure_xp, monsters_defeated, daily_quest_progress, user_id))
        else:
            c.execute('''UPDATE game_data SET health = ?, gold = ?, inventory = ?, 
                         location = ?, level = ? WHERE user_id = ?''',
                      (health, gold, inventory, location, level, user_id))
        conn.commit()
        conn.close()

    def get_daily_quest(self, user_id):
        import hashlib
        today = datetime.now().date().isoformat()
        # Generate consistent daily quest based on user ID and date
        seed = hashlib.md5(f"{user_id}{today}".encode()).hexdigest()
        random.seed(int(seed[:8], 16))
        quest = random.choice(self.daily_quests)
        random.seed()  # Reset random seed
        return quest

    def update_quest_progress(self, user_id, quest_type, amount=1):
        user_data = self.get_game_data(user_id)
        today = datetime.now().date().isoformat()
        last_quest_date = user_data[8] if len(user_data) > 8 else today
        progress_str = user_data[9] if len(user_data) > 9 else '{}'
        
        # Reset progress if new day
        if last_quest_date != today:
            progress = {}
        else:
            try:
                progress = json.loads(progress_str)
            except:
                progress = {}
        
        # Update progress
        progress[quest_type] = progress.get(quest_type, 0) + amount
        
        # Update database
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('UPDATE game_data SET last_daily_quest = ?, daily_quest_progress = ? WHERE user_id = ?',
                  (today, json.dumps(progress), user_id))
        conn.commit()
        conn.close()
        
        return progress

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
    adventure_level = user_data[5] if len(user_data) > 5 else 1
    adventure_xp = user_data[6] if len(user_data) > 6 else 0
    
    loc_info = game.locations[location]
    
    embed = discord.Embed(title="🎮 Adventure Game", color=0x9b59b6)
    embed.add_field(name="Location", value=loc_info['description'], inline=False)
    embed.add_field(name="Health", value=f"❤️ {health}/100", inline=True)
    embed.add_field(name="Gold", value=f"💰 {gold}", inline=True)
    embed.add_field(name="Adventure Level", value=f"⭐ {adventure_level} ({adventure_xp} XP)", inline=True)
    embed.add_field(name="Available Actions", 
                   value=", ".join(loc_info['actions']), inline=False)
    
    if 'connections' in loc_info:
        embed.add_field(name="Travel to", 
                       value=", ".join(loc_info['connections']), inline=False)
    
    # Show daily quest if enabled
    if get_config('daily_quests_enabled') == 'True':
        daily_quest = game.get_daily_quest(ctx.author.id)
        progress_data = game.update_quest_progress(ctx.author.id, 'check', 0)  # Just check, don't increment
        quest_progress = progress_data.get(daily_quest['type'], 0)
        
        quest_status = f"**Daily Quest**: {daily_quest['name']}\n"
        quest_status += f"{daily_quest['description']} ({quest_progress}/{daily_quest['target']})\n"
        quest_status += f"Reward: {daily_quest['reward']} gold 💰"
        
        embed.add_field(name="📋 Today's Quest", value=quest_status, inline=False)
    
    embed.set_footer(text="Use !action <action_name> to perform actions • !use <item> to use items")
    
    await ctx.send(embed=embed)

@bot.command(name='action')
@commands.cooldown(1, 3, commands.BucketType.user)  # 1 use per 3 seconds per user
async def action_command(ctx, *, action):
    """Perform an action in the adventure game"""
    if get_config('game_enabled') != 'True':
        return
        
    user_data = game.get_game_data(ctx.author.id)
    user_id = user_data[0]
    health = user_data[1]
    gold = user_data[2]
    inventory_str = user_data[3]
    location = user_data[4]
    adventure_level = user_data[5] if len(user_data) > 5 else 1
    adventure_xp = user_data[6] if len(user_data) > 6 else 0
    monsters_defeated = user_data[7] if len(user_data) > 7 else 0
    daily_progress_str = user_data[9] if len(user_data) > 9 else '{}'
    
    inventory = json.loads(inventory_str)
    loc_info = game.locations[location]
    
    # Handle movement
    if action in game.locations:
        if action in loc_info.get('connections', []):
            game.update_game_data(user_id, health, gold, inventory_str, action, adventure_level, adventure_xp, monsters_defeated, daily_progress_str)
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
    xp_gained = 10  # Base XP for any action
    quest_updates = {}
    
    # Check for rare events first
    rare_chance = int(get_config('rare_event_chance'))
    legendary_chance = int(get_config('legendary_event_chance'))
    boss_chance = int(get_config('boss_encounter_chance'))
    
    random_roll = random.randint(1, 100)
    
    # Legendary Event (1% default)
    if random_roll <= legendary_chance:
        legendary_rewards = [
            ("🌟 You discovered an ANCIENT TREASURE CHEST! Legendary find!", 800, 50, 200),
            ("👑 You found the Crown of Kings! A truly legendary artifact!", 1000, 0, 300),
            ("🗡️ You uncovered Excalibur! The legendary sword grants you power!", 500, 100, 250)
        ]
        event_text, gold_reward, health_reward, xp_reward = random.choice(legendary_rewards)
        gold += gold_reward
        health = min(100, health + health_reward)
        xp_gained = xp_reward
        result = event_text
        quest_updates['gold'] = gold_reward
        
    # Boss Encounter (3% default)
    elif random_roll <= boss_chance + legendary_chance and location in game.bosses:
        boss = game.bosses[location]
        # Boss fight calculation
        player_power = adventure_level * 10 + inventory.get('Sword', 0) * 15 + inventory.get('Shield', 0) * 5
        success_chance = min(90, max(20, player_power - boss['health'] + 50))
        
        if random.randint(1, 100) <= success_chance:
            gold += boss['gold']
            adventure_xp += boss['xp']
            monsters_defeated += 1
            result = f"⚔️ BOSS BATTLE! You defeated the {boss['name']}! +{boss['gold']} gold, +{boss['xp']} adventure XP!"
            quest_updates['monsters'] = 1
            quest_updates['gold'] = boss['gold']
        else:
            health_loss = random.randint(30, 50)
            health = max(1, health - health_loss)
            result = f"💀 BOSS BATTLE! The {boss['name']} overpowered you! -{health_loss} health. Train more and try again!"
    
    # Rare Event (5% default)
    elif random_roll <= rare_chance + boss_chance + legendary_chance:
        rare_events = [
            ("💎 You found a rare gemstone! Sparkling treasure!", random.randint(150, 300), 0, 50),
            ("🧙‍♂️ A mysterious wizard grants you a boon!", random.randint(100, 200), random.randint(20, 40), 75),
            ("📜 You discovered an ancient map to hidden treasure!", random.randint(200, 400), 0, 60),
            ("🍀 A lucky clover boosts your fortune!", random.randint(175, 350), random.randint(15, 30), 80)
        ]
        event_text, gold_reward, health_reward, xp_reward = random.choice(rare_events)
        gold += gold_reward
        health = min(100, health + health_reward)
        xp_gained = xp_reward
        result = f"✨ RARE EVENT! {event_text}"
        quest_updates['gold'] = gold_reward
    
    # Normal actions
    else:
        if action == 'explore':
            quest_updates['explore'] = 1
            outcomes = [
                ("🔍 You found a hidden treasure! +50 gold", 50, 0),
                ("🕷️ You encountered a spider but escaped! -10 health", 0, -10),
                ("💎 You discovered a valuable gem! +30 gold", 30, 0),
                ("🍄 You found some berries and feel refreshed! +20 health", 0, 20),
                ("❌ You found nothing interesting.", 0, 0),
                ("🗝️ You found an old key! +25 gold", 25, 0)
            ]
            outcome_text, gold_change, health_change = random.choice(outcomes)
            result = outcome_text
            gold += gold_change
            health = max(0, min(100, health + health_change))
            if gold_change > 0:
                quest_updates['gold'] = gold_change
        
        elif action == 'hunt' and location == 'forest':
            quest_updates['explore'] = 1
            if random.random() < 0.7:  # 70% success rate
                monster = random.choice(loc_info['monsters'])
                gold_reward = random.randint(25, 60)
                health_loss = random.randint(5, 20)
                
                # Apply weapon bonus
                weapon_bonus = inventory.get('Sword', 0) * 10
                shield_defense = inventory.get('Shield', 0) * 5
                gold_reward += weapon_bonus
                health_loss = max(1, health_loss - shield_defense)
                
                gold += gold_reward
                health = max(0, health - health_loss)
                monsters_defeated += 1
                adventure_xp += 25
                result = f"⚔️ You defeated a {monster}! +{gold_reward} gold, -{health_loss} health, +25 adventure XP"
                quest_updates['monsters'] = 1
                quest_updates['gold'] = gold_reward
            else:
                result = "🏃 You couldn't find any monsters to hunt."
        
        elif action == 'shop' and location == 'town':
            shop_embed = discord.Embed(title="🏪 Town Shop", color=0xe74c3c)
            for item, info in game.items.items():
                effect_desc = f"({info['effect'].title()}: +{info['value']})" if 'value' in info else ""
                shop_embed.add_field(name=item, value=f"💰 {info['price']} gold {effect_desc}", inline=True)
            shop_embed.set_footer(text="Use !buy <item_name> to purchase")
            await ctx.send(embed=shop_embed)
            return
        
        elif action == 'rest' and location == 'town':
            health = 100
            result = "😴 You rest at the inn and restore full health!"
        
        elif action == 'mine' and location == 'cave':
            quest_updates['mine'] = 1
            quest_updates['explore'] = 1
            gold_found = random.randint(15, 50)
            gold += gold_found
            adventure_xp += 15
            result = f"⛏️ You mined some precious ore! +{gold_found} gold, +15 adventure XP"
            quest_updates['gold'] = gold_found
        
        else:
            result = f"🤷 You {action} but nothing notable happens."
    
    # Level up adventure character
    adventure_xp += xp_gained
    new_adventure_level = (adventure_xp // 200) + 1  # 200 XP per adventure level
    if new_adventure_level > adventure_level:
        result += f"\n🎉 Adventure Level Up! You are now level {new_adventure_level}!"
        adventure_level = new_adventure_level
    
    # Update quest progress
    if get_config('daily_quests_enabled') == 'True':
        for quest_type, amount in quest_updates.items():
            game.update_quest_progress(user_id, quest_type, amount)
    
    # Update game data
    game.update_game_data(user_id, health, gold, json.dumps(inventory), location, adventure_level, adventure_xp, monsters_defeated, daily_progress_str)
    
    embed = discord.Embed(title="Action Result", description=result, color=0x2ecc71)
    embed.add_field(name="Health", value=f"❤️ {health}/100", inline=True)
    embed.add_field(name="Gold", value=f"💰 {gold}", inline=True)
    embed.add_field(name="Adventure Level", value=f"⭐ {adventure_level}", inline=True)
    
    await ctx.send(embed=embed)

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
        item_info = game.items.get(item, {})
        effect_text = ""
        if 'effect' in item_info and 'value' in item_info:
            effect_text = f" ({item_info['effect'].title()}: +{item_info['value']})"
        embed.add_field(name=item, value=f"x{count}{effect_text}", inline=True)
    
    embed.set_footer(text="Use !use <item> to use consumable items")
    await ctx.send(embed=embed)

@bot.command(name='buy')
async def buy_command(ctx, *, item_name):
    """Buy an item from the shop"""
    user_data = game.get_game_data(ctx.author.id)
    user_id = user_data[0]
    health = user_data[1]
    gold = user_data[2]
    inventory_str = user_data[3]
    location = user_data[4]
    adventure_level = user_data[5] if len(user_data) > 5 else 1
    adventure_xp = user_data[6] if len(user_data) > 6 else 0
    monsters_defeated = user_data[7] if len(user_data) > 7 else 0
    daily_progress_str = user_data[9] if len(user_data) > 9 else '{}'
    
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
    
    game.update_game_data(user_id, health, gold, json.dumps(inventory), location, adventure_level, adventure_xp, monsters_defeated, daily_progress_str)
    
    await ctx.send(f"✅ You bought {item_name} for {item['price']} gold!")

@bot.command(name='use')
async def use_item_command(ctx, *, item_name):
    """Use an item from your inventory"""
    user_data = game.get_game_data(ctx.author.id)
    user_id = user_data[0]
    health = user_data[1]
    gold = user_data[2]
    inventory_str = user_data[3]
    location = user_data[4]
    adventure_level = user_data[5] if len(user_data) > 5 else 1
    adventure_xp = user_data[6] if len(user_data) > 6 else 0
    monsters_defeated = user_data[7] if len(user_data) > 7 else 0
    daily_progress_str = user_data[9] if len(user_data) > 9 else '{}'
    
    inventory = json.loads(inventory_str)
    
    if item_name not in inventory or inventory[item_name] <= 0:
        await ctx.send(f"❌ You don't have any {item_name} in your inventory.")
        return
    
    if item_name not in game.items:
        await ctx.send(f"❌ {item_name} cannot be used.")
        return
    
    item = game.items[item_name]
    result = ""
    
    if item['effect'] == 'heal':
        old_health = health
        health = min(100, health + item['value'])
        healed = health - old_health
        result = f"💚 You used {item_name} and restored {healed} health!"
        
    elif item['effect'] == 'magic':
        # Magic scroll gives temporary XP boost
        adventure_xp += item['value']
        result = f"✨ You used {item_name} and gained {item['value']} adventure XP!"
        
    else:
        await ctx.send(f"❌ {item_name} is passive equipment and doesn't need to be used manually.")
        return
    
    # Remove item from inventory
    inventory[item_name] -= 1
    if inventory[item_name] <= 0:
        del inventory[item_name]
    
    # Update game data
    game.update_game_data(user_id, health, gold, json.dumps(inventory), location, adventure_level, adventure_xp, monsters_defeated, daily_progress_str)
    
    embed = discord.Embed(title="Item Used", description=result, color=0x00ff00)
    embed.add_field(name="Health", value=f"❤️ {health}/100", inline=True)
    embed.add_field(name="Adventure XP", value=f"⭐ {adventure_xp}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='adventure_leaderboard')
async def adventure_leaderboard_command(ctx, category='gold'):
    """Show adventure leaderboards - categories: gold, level, monsters"""
    if get_config('adventure_leaderboard_enabled') != 'True':
        await ctx.send("Adventure leaderboards are currently disabled.")
        return
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    if category == 'gold':
        c.execute('SELECT user_id, gold FROM game_data WHERE gold > 0 ORDER BY gold DESC LIMIT 10')
        title = "💰 Adventure Gold Leaderboard"
        icon = "💰"
    elif category == 'level':
        c.execute('SELECT user_id, level, adventure_xp FROM game_data WHERE adventure_xp > 0 ORDER BY level DESC, adventure_xp DESC LIMIT 10')
        title = "⭐ Adventure Level Leaderboard" 
        icon = "⭐"
    elif category == 'monsters':
        c.execute('SELECT user_id, monsters_defeated FROM game_data WHERE monsters_defeated > 0 ORDER BY monsters_defeated DESC LIMIT 10')
        title = "⚔️ Monster Hunter Leaderboard"
        icon = "⚔️"
    else:
        await ctx.send("❌ Invalid category. Use: `gold`, `level`, or `monsters`")
        return
    
    results = c.fetchall()
    conn.close()
    
    embed = discord.Embed(title=title, color=0xffd700)
    
    if not results:
        embed.description = "No adventure data yet! Start playing with `!adventure`"
        await ctx.send(embed=embed)
        return
    
    leaderboard_text = ""
    for i, result in enumerate(results, 1):
        user_id = result[0]
        
        # Use the helper function to get display name
        name = await get_user_display_name_async(ctx, user_id)
        
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
        
        if category == 'gold':
            value = f"{result[1]:,} gold"
        elif category == 'level':
            value = f"Level {result[1]} ({result[2]:,} XP)"
        else:  # monsters
            value = f"{result[1]:,} monsters defeated"
        
        leaderboard_text += f"{medal} **{name}**\n└ {icon} {value}\n\n"
    
    embed.description = leaderboard_text
    embed.set_footer(text="Use !adventure_leaderboard <gold/level/monsters> for different rankings")
    
    await ctx.send(embed=embed)

@bot.command(name='daily_quest')
async def daily_quest_command(ctx):
    """Check your daily quest progress"""
    if get_config('daily_quests_enabled') != 'True':
        await ctx.send("Daily quests are currently disabled.")
        return
    
    user_data = game.get_game_data(ctx.author.id)
    daily_quest = game.get_daily_quest(ctx.author.id)
    progress_data = game.update_quest_progress(ctx.author.id, 'check', 0)  # Just check
    
    quest_progress = progress_data.get(daily_quest['type'], 0)
    completed = quest_progress >= daily_quest['target']
    
    embed = discord.Embed(
        title="📋 Daily Quest", 
        color=0x00ff00 if completed else 0x3498db
    )
    
    embed.add_field(name="Quest", value=daily_quest['name'], inline=True)
    embed.add_field(name="Description", value=daily_quest['description'], inline=True)
    embed.add_field(name="Reward", value=f"{daily_quest['reward']} gold", inline=True)
    
    status = "✅ COMPLETED!" if completed else f"{quest_progress}/{daily_quest['target']}"
    embed.add_field(name="Progress", value=status, inline=False)
    
    if completed:
        embed.add_field(name="💰 Claim Reward", value="Use `!claim_quest` to get your reward!", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='claim_quest')
async def claim_quest_command(ctx):
    """Claim your completed daily quest reward"""
    if get_config('daily_quests_enabled') != 'True':
        await ctx.send("Daily quests are currently disabled.")
        return
    
    user_data = game.get_game_data(ctx.author.id)
    daily_quest = game.get_daily_quest(ctx.author.id)
    progress_data = game.update_quest_progress(ctx.author.id, 'check', 0)
    
    quest_progress = progress_data.get(daily_quest['type'], 0)
    
    if quest_progress < daily_quest['target']:
        await ctx.send(f"❌ Quest not completed yet! Progress: {quest_progress}/{daily_quest['target']}")
        return
    
    # Check if already claimed today
    claimed_key = f"claimed_{daily_quest['type']}"
    if progress_data.get(claimed_key, False):
        await ctx.send("❌ You already claimed today's quest reward!")
        return
    
    # Award the reward
    user_id = user_data[0]
    health = user_data[1]
    gold = user_data[2] + daily_quest['reward']
    inventory_str = user_data[3]
    location = user_data[4]
    adventure_level = user_data[5] if len(user_data) > 5 else 1
    adventure_xp = user_data[6] if len(user_data) > 6 else 0
    monsters_defeated = user_data[7] if len(user_data) > 7 else 0
    
    # Mark as claimed
    progress_data[claimed_key] = True
    game.update_quest_progress(ctx.author.id, claimed_key, 0)  # Update the claimed status
    
    game.update_game_data(user_id, health, gold, inventory_str, location, adventure_level, adventure_xp, monsters_defeated, json.dumps(progress_data))
    
    embed = discord.Embed(title="🎉 Quest Completed!", color=0x00ff00)
    embed.add_field(name="Quest", value=daily_quest['name'], inline=True)
    embed.add_field(name="Reward Claimed", value=f"💰 {daily_quest['reward']} gold", inline=True)
    embed.add_field(name="New Gold Total", value=f"💰 {gold}", inline=True)
    
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
        embed = discord.Embed(
            title="❌ Permission Error", 
            description="You don't have permission to use this command.",
            color=0xff0000
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏱️ Cooldown Active", 
            description=f"Command is on cooldown. Try again in **{error.retry_after:.1f}** seconds.",
            color=0xffa500
        )
        await ctx.send(embed=embed, delete_after=5)  # Auto-delete after 5 seconds
    elif isinstance(error, commands.CommandNotFound):
        # Don't respond to unknown commands to avoid spam
        return
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="❓ Invalid Input", 
            description="Invalid command usage. Use `!help_custom` for command help.",
            color=0xffa500
        )
        await ctx.send(embed=embed)
    else:
        # Log unexpected errors but don't show full error to users
        print(f"Unexpected error in {ctx.command}: {error}")
        embed = discord.Embed(
            title="⚠️ Something went wrong", 
            description="An unexpected error occurred. Please try again.",
            color=0xff0000
        )
        await ctx.send(embed=embed)

@bot.command(name='stats')
@commands.cooldown(1, 60, commands.BucketType.guild)
async def stats_command(ctx):
    """Show server bot statistics"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get XP stats
    c.execute('SELECT COUNT(*), SUM(total_messages), MAX(level), SUM(xp) FROM users WHERE total_messages > 0')
    xp_stats = c.fetchone()
    total_users, total_messages, max_level, total_xp = xp_stats
    
    # Get adventure stats
    c.execute('SELECT COUNT(*), SUM(gold), MAX(level), SUM(monsters_defeated) FROM game_data WHERE gold > 0 OR monsters_defeated > 0')
    adventure_stats = c.fetchone()
    adventure_users, total_gold, max_adventure_level, total_monsters = adventure_stats
    
    # Get daily quest completion rate
    today = datetime.now().date().isoformat()
    c.execute('SELECT COUNT(*) FROM game_data WHERE last_daily_quest = ? AND daily_quest_progress LIKE "%claimed_%"', (today,))
    daily_completions = c.fetchone()[0]
    
    conn.close()
    
    embed = discord.Embed(title="📊 Server Bot Statistics", color=0x7289da)
    
    # XP Statistics
    xp_text = (
        f"👥 Active Users: **{total_users or 0:,}**\n"
        f"💬 Messages Sent: **{total_messages or 0:,}**\n"
        f"⭐ Highest Level: **{max_level or 0}**\n"
        f"🎯 Total XP Earned: **{total_xp or 0:,}**"
    )
    embed.add_field(name="📈 Chat Activity", value=xp_text, inline=True)
    
    # Adventure Statistics  
    adventure_text = (
        f"🎮 Adventurers: **{adventure_users or 0:,}**\n"
        f"💰 Gold Collected: **{total_gold or 0:,}**\n"
        f"⚔️ Monsters Defeated: **{total_monsters or 0:,}**\n"
        f"🌟 Max Adventure Level: **{max_adventure_level or 0}**"
    )
    embed.add_field(name="🏔️ Adventure Progress", value=adventure_text, inline=True)
    
    # Today's Activity
    today_text = (
        f"📋 Daily Quests Completed: **{daily_completions or 0}**\n"
        f"🎲 Rare Events Today: *Happening live!*\n"
        f"👑 Current Top Player: *Check leaderboards!*\n"
        f"🤖 Bot Uptime: *24/7 Online*"
    )
    embed.add_field(name="📅 Today's Activity", value=today_text, inline=False)
    
    # Fun Facts
    if total_messages and total_users:
        avg_messages = total_messages // total_users
        fun_facts = (
            f"📝 Average messages per user: **{avg_messages}**\n"
            f"🎪 Most active feature: **{'Adventure Game' if adventure_users > total_users // 2 else 'XP System'}**\n"
            f"💎 Community engagement: **{'High' if total_users > 10 else 'Growing'}**"
        )
        embed.add_field(name="🎉 Fun Facts", value=fun_facts, inline=False)
    
    embed.set_footer(text="Statistics update in real-time • Use !leaderboard to see rankings")
    embed.timestamp = datetime.now()
    
    await ctx.send(embed=embed)

# Help command with rich embed design
@bot.command(name='help')
async def help_command(ctx):
    """Show all available commands"""
    await help_custom(ctx)

@bot.command(name='help_custom')
async def help_custom(ctx):
    """Show all available commands"""
    
    # Main help embed
    embed = discord.Embed(
        title="🤖 Community Bot Commands", 
        description="Your complete guide to XP systems and epic adventures!",
        color=0x00d4ff
    )
    
    # XP System Section
    embed.add_field(
        name="📊 Chat Activity", 
        value=(
            "🔹 `!level` - View your XP and level\n"
            "🔹 `!level @user` - Check someone else's level\n" 
            "🔹 `!leaderboard` - See top XP earners\n"
            "🔹 `!xp_table` - View XP requirements per level\n"
            "🔹 `!stats` - Server bot statistics\n"
            " *Gain XP automatically by chatting!*"
        ), 
        inline=True
    )
    
    # Adventure Game Section  
    embed.add_field(
        name="🎮 Adventure RPG", 
        value=(
            "🔹 `!adventure` - Start your journey\n"
            "🔹 `!action <explore/hunt/mine>` - Take actions\n"
            "🔹 `!inventory` - Check your items\n"
            "🔹 `!use <item>` - Use potions & scrolls\n"
            "🔹 `!buy <item>` - Shop in town\n"
            "⚡ *Rare events, boss battles & more!*"
        ), 
        inline=True
    )
    
    # Competition Section
    embed.add_field(
        name="🏆 Leaderboards & Rankings", 
        value=(
            "🔹 `!adventure_leaderboard gold` - Top collectors 💰\n"
            "🔹 `!adventure_leaderboard level` - Highest adventurers ⭐\n"
            "🔹 `!adventure_leaderboard monsters` - Monster hunters ⚔️\n"
            "🏆 *Compete for glory and bragging rights!*"
        ), 
        inline=True
    )
    
    # Daily Quests Section
    embed.add_field(
        name="📋 Daily Quest System", 
        value=(
            "🔹 `!daily_quest` - Check today's challenge\n"
            "🔹 `!claim_quest` - Collect your rewards\n"
            "📋 *New quest every day with bonus gold!*"
        ), 
        inline=True
    )
    
    # Quick Start Guide
    embed.add_field(
        name="🚀 Quick Start Guide", 
        value=(
            "1️⃣ Chat normally to gain XP\n"
            "2️⃣ Use `!adventure` to start the game\n"
            "3️⃣ Try `!action explore` for your first adventure\n"
            "4️⃣ Check `!daily_quest` for bonus objectives"
        ), 
        inline=True
    )
    
    # Game Locations
    embed.add_field(
        name="🗺️ Adventure Locations", 
        value=(
            "🏘️ **Town** - Shop, rest, safe exploration\n"
            "🌲 **Forest** - Hunt monsters, boss battles\n"
            "🕳️ **Cave** - Mine gold, dangerous creatures\n"
            "🎲 *Watch for rare events and legendary finds!*"
        ), 
        inline=True
    )
    
    # Footer with additional info
    embed.set_footer(
        text="💡 Tip: Start in Town, then explore Forest and Cave! • 🎲 5% chance for rare events!",
    )
    
    await ctx.send(embed=embed)
    
    # Send admin commands separately if user has permissions
    if ctx.author.guild_permissions.administrator:
        admin_embed = discord.Embed(
            title="⚙️ Admin Commands", 
            description="Configure your bot without touching code!",
            color=0xff6b35
        )
        
        admin_embed.add_field(
            name="🛠️ Configuration", 
            value=(
                "🔹 `!config list` - View all settings\n"
                "🔹 `!config get <key>` - Check specific setting\n"
                "🔹 `!config set <key> <value>` - Change setting\n"
            ), 
            inline=True
        )
        
        admin_embed.add_field(
            name="🔧 Key Settings", 
            value=(
                "🔹 `xp_per_message` - XP per message\n"
                "🔹 `level_multiplier` - Base XP for leveling\n"
                "🔹 `level_scaling_factor` - Level difficulty scaling\n"
                "🔹 `rare_event_chance` - Rare discovery rate (%)\n"
                "🔹 `boss_encounter_chance` - Boss battle rate (%)\n"
                "🔹 `daily_quests_enabled` - Enable daily quests\n"
                "🔹 `game_enabled` - Enable/disable adventure"
            ), 
            inline=True
        )
        
        admin_embed.set_footer(text="🔐 Admin-only commands • Use !config list to see all options")
        
        await ctx.send(embed=admin_embed)

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
