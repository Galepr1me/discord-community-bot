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
# Global variable to track database type
_current_db_type = 'sqlite'

def get_db_connection():
    """Get database connection - PostgreSQL for cloud with DATABASE_URL, SQLite otherwise"""
    global _current_db_type
    database_url = os.getenv('DATABASE_URL')
    
    if database_url and database_url.startswith('postgresql://'):
        # Use external PostgreSQL (Neon, Supabase, etc.)
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
            _current_db_type = 'postgresql'
            return conn
            
        except ImportError:
            print("❌ psycopg2 not installed. Install with: pip install psycopg2-binary")
            print("🔄 Falling back to SQLite...")
            db_path = get_db_path()
            print(f"🗄️ Using SQLite database at: {db_path}")
            _current_db_type = 'sqlite'
            return sqlite3.connect(db_path)
            
        except Exception as e:
            print(f"❌ PostgreSQL connection failed: {e}")
            print("🔄 Falling back to SQLite...")
            db_path = get_db_path()
            print(f"🗄️ Using SQLite database at: {db_path}")
            _current_db_type = 'sqlite'
            return sqlite3.connect(db_path)
    else:
        # Use SQLite for local development
        db_path = get_db_path()
        print(f"🗄️ Using SQLite database at: {db_path}")
        _current_db_type = 'sqlite'
        return sqlite3.connect(db_path)

def execute_query_with_conversion(query, params=None):
    """Execute a database query with automatic parameter conversion"""
    global _current_db_type
    conn = get_db_connection()
    
    try:
        # Convert SQLite placeholders (?) to PostgreSQL placeholders (%s) if needed
        if _current_db_type == 'postgresql':
            converted_query = query.replace('?', '%s')
        else:
            converted_query = query
        
        c = conn.cursor()
        
        if params:
            c.execute(converted_query, params)
        else:
            c.execute(converted_query)
        
        result = c.fetchone()
        conn.commit()
        conn.close()
        
        return result
        
    except Exception as e:
        print(f"Database error: {e}")
        conn.close()
        raise

def get_db_path():
    """Get the appropriate SQLite database path for the environment"""
    # Check if we're in a cloud environment
    if os.getenv('RENDER') or os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('PORT'):
        # Use /tmp for cloud hosting (ephemeral but works)
        return '/tmp/bot_data.db'
    else:
        # Use local file for development
        return 'bot_data.db'

def populate_card_library_postgresql(cursor):
    """Populate the cards table with the initial card library for PostgreSQL"""
    for card in card_game.card_library:
        cursor.execute('''INSERT INTO cards (name, element, rarity, attack, health, cost, ability, ascii_art) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                      (card['name'], card['element'], card['rarity'], card['attack'], 
                       card['health'], card['cost'], card['ability'], card['ascii']))

def populate_card_library_sqlite(cursor):
    """Populate the cards table with the initial card library for SQLite"""
    for card in card_game.card_library:
        cursor.execute('''INSERT INTO cards (name, element, rarity, attack, health, cost, ability, ascii_art) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                      (card['name'], card['element'], card['rarity'], card['attack'], 
                       card['health'], card['cost'], card['ability'], card['ascii']))

def init_db():
    global _current_db_type
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Handle PostgreSQL vs SQLite differences
        if _current_db_type == 'postgresql':
            # PostgreSQL syntax
            c.execute('''CREATE TABLE IF NOT EXISTS users
                         (user_id BIGINT PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1, 
                          last_message TIMESTAMP, total_messages INTEGER DEFAULT 0, 
                          username TEXT, display_name TEXT)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS config
                         (key TEXT PRIMARY KEY, value TEXT)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS game_data
                         (user_id BIGINT PRIMARY KEY, health INTEGER DEFAULT 100, 
                          gold INTEGER DEFAULT 0, inventory TEXT DEFAULT '{}', 
                          location TEXT DEFAULT 'town', level INTEGER DEFAULT 1,
                          adventure_xp INTEGER DEFAULT 0, monsters_defeated INTEGER DEFAULT 0,
                          last_daily_quest DATE, daily_quest_progress TEXT DEFAULT '{}')''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS db_version
                         (version INTEGER PRIMARY KEY)''')
            
            # Card Game Tables for PostgreSQL
            c.execute('''CREATE TABLE IF NOT EXISTS cards
                         (card_id SERIAL PRIMARY KEY, name TEXT NOT NULL, element TEXT NOT NULL,
                          rarity TEXT NOT NULL, attack INTEGER NOT NULL, health INTEGER NOT NULL,
                          cost INTEGER NOT NULL, ability TEXT, ascii_art TEXT NOT NULL)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS user_cards
                         (user_id BIGINT NOT NULL, card_id INTEGER NOT NULL, quantity INTEGER DEFAULT 1,
                          obtained_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                          PRIMARY KEY (user_id, card_id),
                          FOREIGN KEY (card_id) REFERENCES cards(card_id))''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS user_decks
                         (deck_id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL, deck_name TEXT DEFAULT 'Main Deck',
                          card_ids JSON NOT NULL, is_active BOOLEAN DEFAULT FALSE,
                          created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            
            # PostgreSQL migrations
            c.execute('SELECT version FROM db_version ORDER BY version DESC LIMIT 1')
            current_version = c.fetchone()
            current_version = current_version[0] if current_version else 0
            
            if current_version < 2:
                # For PostgreSQL, we'll just ensure all columns exist
                try:
                    c.execute('ALTER TABLE game_data ADD COLUMN IF NOT EXISTS adventure_xp INTEGER DEFAULT 0')
                    c.execute('ALTER TABLE game_data ADD COLUMN IF NOT EXISTS monsters_defeated INTEGER DEFAULT 0')
                    c.execute('ALTER TABLE game_data ADD COLUMN IF NOT EXISTS last_daily_quest DATE')
                    c.execute('ALTER TABLE game_data ADD COLUMN IF NOT EXISTS daily_quest_progress TEXT DEFAULT \'{}\'')
                    c.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT')
                    c.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT')
                except Exception as e:
                    print(f"Migration note: {e}")
                
                c.execute('INSERT INTO db_version (version) VALUES (%s) ON CONFLICT (version) DO NOTHING', (2,))
            
            if current_version < 3:
                # Card system migration - populate cards table
                try:
                    c.execute('SELECT COUNT(*) FROM cards')
                    card_count = c.fetchone()[0]
                    if card_count == 0:
                        print("🃏 Populating card library...")
                        populate_card_library_postgresql(c)
                except Exception as e:
                    print(f"Card migration note: {e}")
                
                c.execute('INSERT INTO db_version (version) VALUES (%s) ON CONFLICT (version) DO NOTHING', (3,))
                print("✅ PostgreSQL database with card system initialized")
        
        else:
            # SQLite syntax
            c.execute('''CREATE TABLE IF NOT EXISTS users
                         (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1, 
                          last_message TIMESTAMP, total_messages INTEGER DEFAULT 0, 
                          username TEXT, display_name TEXT)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS config
                         (key TEXT PRIMARY KEY, value TEXT)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS game_data
                         (user_id INTEGER PRIMARY KEY, health INTEGER DEFAULT 100, 
                          gold INTEGER DEFAULT 0, inventory TEXT DEFAULT '{}', 
                          location TEXT DEFAULT 'town', level INTEGER DEFAULT 1,
                          adventure_xp INTEGER DEFAULT 0, monsters_defeated INTEGER DEFAULT 0,
                          last_daily_quest DATE, daily_quest_progress TEXT DEFAULT '{}')''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS db_version
                         (version INTEGER PRIMARY KEY)''')
            
            # Card Game Tables for SQLite
            c.execute('''CREATE TABLE IF NOT EXISTS cards
                         (card_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, element TEXT NOT NULL,
                          rarity TEXT NOT NULL, attack INTEGER NOT NULL, health INTEGER NOT NULL,
                          cost INTEGER NOT NULL, ability TEXT, ascii_art TEXT NOT NULL)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS user_cards
                         (user_id INTEGER NOT NULL, card_id INTEGER NOT NULL, quantity INTEGER DEFAULT 1,
                          obtained_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                          PRIMARY KEY (user_id, card_id),
                          FOREIGN KEY (card_id) REFERENCES cards(card_id))''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS user_decks
                         (deck_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, deck_name TEXT DEFAULT 'Main Deck',
                          card_ids TEXT NOT NULL, is_active INTEGER DEFAULT 0,
                          created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            
            # SQLite migrations
            c.execute('SELECT version FROM db_version ORDER BY version DESC LIMIT 1')
            current_version = c.fetchone()
            current_version = current_version[0] if current_version else 0
            
            if current_version < 1:
                try:
                    c.execute('ALTER TABLE game_data ADD COLUMN adventure_xp INTEGER DEFAULT 0')
                except sqlite3.OperationalError:
                    pass
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
            
            if current_version < 3:
                # Card system migration - populate cards table
                try:
                    c.execute('SELECT COUNT(*) FROM cards')
                    card_count = c.fetchone()[0]
                    if card_count == 0:
                        print("🃏 Populating card library...")
                        populate_card_library_sqlite(c)
                except Exception as e:
                    print(f"Card migration note: {e}")
                
                c.execute('INSERT OR REPLACE INTO db_version (version) VALUES (3)')
                print("✅ SQLite database with card system initialized")
        
        # Default configuration (works for both databases)
        default_config = {
            'xp_per_message': '15',
            'xp_cooldown': '60',
            'level_multiplier': '100',
            'level_scaling_factor': '1.2',
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
            if _current_db_type == 'postgresql':
                c.execute('INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING', (key, value))
            else:
                c.execute('INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)', (key, value))
        
        conn.commit()
        print(f"✅ Database initialization complete ({_current_db_type})")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        raise
    finally:
        conn.close()

# Utility functions
def get_config(key):
    global _current_db_type
    conn = get_db_connection()
    c = conn.cursor()
    
    if _current_db_type == 'postgresql':
        c.execute('SELECT value FROM config WHERE key = %s', (key,))
    else:
        c.execute('SELECT value FROM config WHERE key = ?', (key,))
    
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def set_config(key, value):
    global _current_db_type
    conn = get_db_connection()
    c = conn.cursor()
    
    if _current_db_type == 'postgresql':
        c.execute('INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value', (key, value))
    else:
        c.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', (key, value))
    
    conn.commit()
    conn.close()

def get_user_data(user_id):
    global _current_db_type
    conn = get_db_connection()
    c = conn.cursor()
    
    if _current_db_type == 'postgresql':
        c.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        result = c.fetchone()
        if not result:
            c.execute('INSERT INTO users (user_id) VALUES (%s)', (user_id,))
            conn.commit()
            result = (user_id, 0, 1, None, 0, None, None)
    else:
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        if not result:
            c.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
            conn.commit()
            result = (user_id, 0, 1, None, 0, None, None)
    
    conn.close()
    return result

def get_user_display_name(ctx, user_id):
    """Get user display name with multiple fallback methods"""
    global _current_db_type
    
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
        
        if _current_db_type == 'postgresql':
            c.execute('SELECT display_name, username FROM users WHERE user_id = %s', (user_id,))
        else:
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
    global _current_db_type
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
    if _current_db_type == 'postgresql':
        c.execute('''UPDATE users SET xp = %s, level = %s, last_message = %s, total_messages = %s, 
                     username = %s, display_name = %s WHERE user_id = %s''', 
                  (new_xp, new_level, now_str, total_messages + 1, username, display_name, user_id))
    else:
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
    global _current_db_type
    conn = get_db_connection()
    c = conn.cursor()
    
    if _current_db_type == 'postgresql':
        c.execute('SELECT user_id, xp, level, username, display_name FROM users ORDER BY xp DESC LIMIT %s', (limit,))
    else:
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

# Trading Card Game System
class CardGame:
    def __init__(self):
        # Card elements and their advantages
        self.elements = {
            'fire': {'beats': 'earth', 'color': 0xff4500, 'emoji': '🔥'},
            'water': {'beats': 'fire', 'color': 0x1e90ff, 'emoji': '💧'},
            'earth': {'beats': 'air', 'color': 0x8b4513, 'emoji': '🌍'},
            'air': {'beats': 'water', 'color': 0x87ceeb, 'emoji': '💨'},
            'light': {'beats': 'dark', 'color': 0xffd700, 'emoji': '✨'},
            'dark': {'beats': 'light', 'color': 0x4b0082, 'emoji': '🌑'}
        }
        
        # Rarity system
        self.rarities = {
            'common': {'color': 0x808080, 'drop_rate': 60, 'border': '─'},
            'rare': {'color': 0x0080ff, 'drop_rate': 25, 'border': '═'},
            'epic': {'color': 0x8000ff, 'drop_rate': 10, 'border': '━'},
            'legendary': {'color': 0xff8000, 'drop_rate': 4, 'border': '█'},
            'mythic': {'color': 0xff0080, 'drop_rate': 1, 'border': '▓'}
        }
        
        # Initial card library
        self.card_library = self._create_initial_cards()
    
    def _create_initial_cards(self):
        """Create the initial set of 20 cards"""
        cards = []
        
        # Common Cards (8 total - 2 per basic element)
        common_cards = [
            # Fire Commons
            {'name': 'Fire Sprite', 'element': 'fire', 'rarity': 'common', 'attack': 2, 'health': 1, 'cost': 1,
             'ascii': ' /^\\\n( o )\n \\v/', 'ability': 'None'},
            {'name': 'Flame Imp', 'element': 'fire', 'rarity': 'common', 'attack': 3, 'health': 2, 'cost': 2,
             'ascii': ' /^^^\\\n( >o< )\n  \\_/', 'ability': 'None'},
            
            # Water Commons  
            {'name': 'Water Drop', 'element': 'water', 'rarity': 'common', 'attack': 1, 'health': 3, 'cost': 1,
             'ascii': '  ~\n (~)\n  ~', 'ability': 'None'},
            {'name': 'Stream Fish', 'element': 'water', 'rarity': 'common', 'attack': 2, 'health': 2, 'cost': 2,
             'ascii': ' ><>\n~~~~\n ><>', 'ability': 'None'},
            
            # Earth Commons
            {'name': 'Rock Pebble', 'element': 'earth', 'rarity': 'common', 'attack': 1, 'health': 4, 'cost': 2,
             'ascii': ' ###\n#####\n ###', 'ability': 'None'},
            {'name': 'Mud Golem', 'element': 'earth', 'rarity': 'common', 'attack': 3, 'health': 3, 'cost': 3,
             'ascii': ' ###\n# O #\n ###', 'ability': 'None'},
            
            # Air Commons
            {'name': 'Wind Wisp', 'element': 'air', 'rarity': 'common', 'attack': 3, 'health': 1, 'cost': 1,
             'ascii': ' ~~~\n~ o ~\n ~~~', 'ability': 'None'},
            {'name': 'Cloud Sprite', 'element': 'air', 'rarity': 'common', 'attack': 2, 'health': 3, 'cost': 2,
             'ascii': ' ~~~~\n(  o )\n ~~~~', 'ability': 'None'},
        ]
        
        # Rare Cards (6 total)
        rare_cards = [
            {'name': 'Fire Wolf', 'element': 'fire', 'rarity': 'rare', 'attack': 4, 'health': 3, 'cost': 3,
             'ascii': '  /\\_/\\\n ( o.o )\n  > ^ <', 'ability': 'Burn: Deal 1 extra damage'},
            {'name': 'Ice Mage', 'element': 'water', 'rarity': 'rare', 'attack': 3, 'health': 4, 'cost': 4,
             'ascii': '   /|\\\n  /*|*\\\n ( o o )', 'ability': 'Freeze: Skip enemy turn'},
            {'name': 'Stone Giant', 'element': 'earth', 'rarity': 'rare', 'attack': 5, 'health': 5, 'cost': 5,
             'ascii': '  #####\n #  O  #\n #  _  #\n  #####', 'ability': 'Armor: Reduce damage by 1'},
            {'name': 'Storm Eagle', 'element': 'air', 'rarity': 'rare', 'attack': 4, 'health': 2, 'cost': 3,
             'ascii': '  \\   /\n   \\_/\n  (o o)\n   ^^^', 'ability': 'Swift: Attack first'},
            {'name': 'Light Fairy', 'element': 'light', 'rarity': 'rare', 'attack': 2, 'health': 3, 'cost': 3,
             'ascii': '   *\n  /|\\\n ( o )\n  /|\\', 'ability': 'Heal: Restore 2 health'},
            {'name': 'Shadow Cat', 'element': 'dark', 'rarity': 'rare', 'attack': 3, 'health': 2, 'cost': 2,
             'ascii': '  /\\_/\\\n ( -.o )\n  > ^ <', 'ability': 'Stealth: 50% dodge chance'},
        ]
        
        # Epic Cards (4 total)
        epic_cards = [
            {'name': 'Fire Dragon', 'element': 'fire', 'rarity': 'epic', 'attack': 6, 'health': 5, 'cost': 6,
             'ascii': '   /\\_/\\\n  /  o  \\\n |  ___  |\n  \\  ^  /\n   \\___/', 'ability': 'Inferno: Deal damage to all enemies'},
            {'name': 'Water Leviathan', 'element': 'water', 'rarity': 'epic', 'attack': 5, 'health': 7, 'cost': 7,
             'ascii': '  ~~~~~~~\n ~  o o  ~\n~   ___   ~\n ~  \\_/  ~\n  ~~~~~~~', 'ability': 'Tsunami: Heal all allies'},
            {'name': 'Earth Titan', 'element': 'earth', 'rarity': 'epic', 'attack': 7, 'health': 6, 'cost': 7,
             'ascii': '  #######\n # O   O #\n #   _   #\n #  \\_/  #\n  #######', 'ability': 'Earthquake: Stun all enemies'},
            {'name': 'Sky Lord', 'element': 'air', 'rarity': 'epic', 'attack': 6, 'health': 4, 'cost': 5,
             'ascii': '    /|\\\n   / | \\\n  |  *  |\n   \\ | /\n    \\|/', 'ability': 'Lightning: Deal 3 damage to any target'},
        ]
        
        # Legendary Cards (2 total)
        legendary_cards = [
            {'name': 'Phoenix God', 'element': 'light', 'rarity': 'legendary', 'attack': 8, 'health': 8, 'cost': 9,
             'ascii': '     /|\\\n    / | \\\n   |  *  |\n  /|\\ | /|\\\n / | \\|/ | \\\n|  |  *  |  |\n \\ |     | /\n  \\|_____|/', 'ability': 'Rebirth: Return to hand when destroyed'},
            {'name': 'Void Demon', 'element': 'dark', 'rarity': 'legendary', 'attack': 9, 'health': 6, 'cost': 8,
             'ascii': '   #######\n  # \\   / #\n #   \\_/   #\n#  (o) (o)  #\n #    ^    #\n  # \\_-_/ #\n   #######', 'ability': 'Devour: Destroy any card and gain its stats'},
        ]
        
        # Combine all cards
        cards.extend(common_cards)
        cards.extend(rare_cards) 
        cards.extend(epic_cards)
        cards.extend(legendary_cards)
        
        return cards

card_game = CardGame()

# Card Storage Functions
def add_card_to_collection(user_id, card_id, quantity=1):
    """Add a card to user's collection"""
    global _current_db_type
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        if _current_db_type == 'postgresql':
            # Try to insert new card, or update quantity if it exists
            c.execute('''INSERT INTO user_cards (user_id, card_id, quantity) 
                         VALUES (%s, %s, %s) 
                         ON CONFLICT (user_id, card_id) 
                         DO UPDATE SET quantity = user_cards.quantity + %s''',
                      (user_id, card_id, quantity, quantity))
        else:
            # SQLite approach - check if exists first
            c.execute('SELECT quantity FROM user_cards WHERE user_id = ? AND card_id = ?', (user_id, card_id))
            existing = c.fetchone()
            
            if existing:
                new_quantity = existing[0] + quantity
                c.execute('UPDATE user_cards SET quantity = ? WHERE user_id = ? AND card_id = ?',
                         (new_quantity, user_id, card_id))
            else:
                c.execute('INSERT INTO user_cards (user_id, card_id, quantity) VALUES (?, ?, ?)',
                         (user_id, card_id, quantity))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding card to collection: {e}")
        return False
    finally:
        conn.close()

def get_user_collection(user_id):
    """Get user's card collection with card details"""
    global _current_db_type
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        if _current_db_type == 'postgresql':
            c.execute('''SELECT c.card_id, c.name, c.element, c.rarity, c.attack, c.health, c.cost, c.ability, c.ascii_art, uc.quantity
                         FROM cards c 
                         JOIN user_cards uc ON c.card_id = uc.card_id 
                         WHERE uc.user_id = %s 
                         ORDER BY c.rarity DESC, c.name''', (user_id,))
        else:
            c.execute('''SELECT c.card_id, c.name, c.element, c.rarity, c.attack, c.health, c.cost, c.ability, c.ascii_art, uc.quantity
                         FROM cards c 
                         JOIN user_cards uc ON c.card_id = uc.card_id 
                         WHERE uc.user_id = ? 
                         ORDER BY c.rarity DESC, c.name''', (user_id,))
        
        results = c.fetchall()
        return results
    except Exception as e:
        print(f"Error getting user collection: {e}")
        return []
    finally:
        conn.close()

def get_card_by_name(card_name):
    """Get card details from database by name"""
    global _current_db_type
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        if _current_db_type == 'postgresql':
            c.execute('SELECT * FROM cards WHERE name = %s', (card_name,))
        else:
            c.execute('SELECT * FROM cards WHERE name = ?', (card_name,))
        
        result = c.fetchone()
        return result
    except Exception as e:
        print(f"Error getting card by name: {e}")
        return None
    finally:
        conn.close()

# Card Game Commands
def format_card_display(card):
    """Format a card for display with ASCII art and stats"""
    rarity = card['rarity']
    element = card['element']
    
    # Get colors and borders
    rarity_info = card_game.rarities[rarity]
    element_info = card_game.elements[element]
    
    border_char = rarity_info['border']
    color = rarity_info['color']
    
    # Create the card display
    card_lines = card['ascii'].split('\n')
    max_width = max(len(line) for line in card_lines) + 4
    
    # Top border
    display = f"╔{'═' * (max_width - 2)}╗\n"
    
    # Card name
    name_line = f"║ {card['name'].center(max_width - 4)} ║\n"
    display += name_line
    
    # Separator
    display += f"║{' ' * (max_width - 2)}║\n"
    
    # ASCII art
    for line in card_lines:
        padded_line = line.center(max_width - 4)
        display += f"║ {padded_line} ║\n"
    
    # Separator
    display += f"║{' ' * (max_width - 2)}║\n"
    
    # Stats
    stats_line = f"ATK: {card['attack']}  HP: {card['health']}"
    cost_element = f"COST: {card['cost']}  {element_info['emoji']}{element.upper()}"
    
    display += f"║ {stats_line.ljust(max_width - 4)} ║\n"
    display += f"║ {cost_element.ljust(max_width - 4)} ║\n"
    
    # Ability (if not None)
    if card['ability'] != 'None':
        ability_line = card['ability'][:max_width - 4]  # Truncate if too long
        display += f"║ {ability_line.ljust(max_width - 4)} ║\n"
    
    # Bottom border
    display += f"╚{'═' * (max_width - 2)}╝"
    
    return display, color

@bot.command(name='cards')
async def cards_command(ctx, page: int = 1):
    """View your card collection"""
    if get_config('game_enabled') != 'True':
        await ctx.send("The card game is currently disabled.")
        return
    
    # Get user's collection from database
    collection = get_user_collection(ctx.author.id)
    
    if not collection:
        embed = discord.Embed(
            title="🃏 Your Card Collection", 
            description="Your collection is empty! Use `!pack` to get your first cards.",
            color=0x95a5a6
        )
        embed.add_field(
            name="Getting Started", 
            value="🎁 Use `!pack` to open card packs\n🎴 Collect all 20 unique cards\n⚔️ Battles coming soon!",
            inline=False
        )
        await ctx.send(embed=embed)
        return
    
    # Calculate collection stats
    total_cards = sum(card[9] for card in collection)  # quantity is index 9
    unique_cards = len(collection)
    rare_cards = sum(1 for card in collection if card[3] in ['rare', 'epic', 'legendary', 'mythic'])
    
    # Pagination - 5 cards per page
    cards_per_page = 5
    total_pages = (len(collection) + cards_per_page - 1) // cards_per_page
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * cards_per_page
    end_idx = start_idx + cards_per_page
    page_cards = collection[start_idx:end_idx]
    
    embed = discord.Embed(
        title="🃏 Your Card Collection", 
        description=f"**Page {page}/{total_pages}** • Showing {len(page_cards)} cards",
        color=0x3498db
    )
    
    # Add collection stats
    embed.add_field(
        name="📊 Collection Stats", 
        value=f"📦 **{total_cards}** total cards\n🎴 **{unique_cards}**/20 unique cards\n💎 **{rare_cards}** rare+ cards", 
        inline=True
    )
    
    # Add rarity breakdown
    rarity_counts = {}
    for card in collection:
        rarity = card[3]  # rarity is index 3
        rarity_counts[rarity] = rarity_counts.get(rarity, 0) + card[9]  # quantity
    
    rarity_text = ""
    for rarity in ['common', 'rare', 'epic', 'legendary', 'mythic']:
        if rarity in rarity_counts:
            emoji = {'common': '⚪', 'rare': '🔵', 'epic': '🟣', 'legendary': '🟠', 'mythic': '🟡'}[rarity]
            rarity_text += f"{emoji} {rarity_counts[rarity]} {rarity.title()}\n"
    
    if rarity_text:
        embed.add_field(name="🌟 By Rarity", value=rarity_text, inline=True)
    
    # Add cards on this page
    for card_data in page_cards:
        card_id, name, element, rarity, attack, health, cost, ability, ascii_art, quantity = card_data
        
        element_info = card_game.elements[element]
        rarity_info = card_game.rarities[rarity]
        
        quantity_text = f" x{quantity}" if quantity > 1 else ""
        
        embed.add_field(
            name=f"{name}{quantity_text}", 
            value=f"{element_info['emoji']} {element.title()} • {rarity.title()}\n"
                  f"⚔️ {attack} ATK • ❤️ {health} HP • 💎 {cost} Cost\n"
                  f"🎯 {ability if ability != 'None' else 'No special ability'}",
            inline=False
        )
    
    # Add navigation footer
    footer_text = "Use !pack to get more cards"
    if total_pages > 1:
        footer_text += f" • Use !cards {page + 1} for next page" if page < total_pages else ""
        footer_text += f" • Use !cards {page - 1} for previous page" if page > 1 else ""
    
    embed.set_footer(text=footer_text)
    
    await ctx.send(embed=embed)

@bot.command(name='view')
async def view_card_command(ctx, *, card_name):
    """View a specific card in full ASCII art format"""
    if get_config('game_enabled') != 'True':
        await ctx.send("The card game is currently disabled.")
        return
    
    # Find the card in the library
    card = None
    for library_card in card_game.card_library:
        if library_card['name'].lower() == card_name.lower():
            card = library_card
            break
    
    if not card:
        # Show available cards
        available_cards = [c['name'] for c in card_game.card_library]
        embed = discord.Embed(
            title="❌ Card Not Found", 
            description=f"Could not find card: **{card_name}**",
            color=0xff0000
        )
        
        # Show some example cards
        examples = available_cards[:10]  # First 10 cards
        embed.add_field(
            name="Available Cards (examples)", 
            value="\n".join(f"• {name}" for name in examples),
            inline=False
        )
        
        embed.set_footer(text="Use exact card names • Case insensitive")
        await ctx.send(embed=embed)
        return
    
    # Display the card with full ASCII art
    card_display, color = format_card_display(card)
    
    embed = discord.Embed(
        title=f"🃏 {card['name']}", 
        description=f"```\n{card_display}\n```",
        color=color
    )
    
    # Add detailed stats
    element_info = card_game.elements[card['element']]
    rarity_info = card_game.rarities[card['rarity']]
    
    embed.add_field(
        name="📊 Card Details", 
        value=(
            f"{element_info['emoji']} **Element:** {card['element'].title()}\n"
            f"💎 **Rarity:** {card['rarity'].title()}\n"
            f"⚔️ **Attack:** {card['attack']}\n"
            f"❤️ **Health:** {card['health']}\n"
            f"💰 **Cost:** {card['cost']}\n"
            f"🎯 **Ability:** {card['ability']}"
        ),
        inline=True
    )
    
    # Add element advantage info
    beats_element = card_game.elements[card['element']]['beats']
    beats_info = card_game.elements[beats_element]
    
    embed.add_field(
        name="⚡ Element Advantage", 
        value=f"{element_info['emoji']} **{card['element'].title()}** beats {beats_info['emoji']} **{beats_element.title()}**",
        inline=True
    )
    
    embed.set_footer(text="Use !pack to collect cards • Use !cards to view your collection")
    
    await ctx.send(embed=embed)

@bot.command(name='pack')
async def pack_command(ctx):
    """Open a card pack"""
    if get_config('game_enabled') != 'True':
        await ctx.send("The card game is currently disabled.")
        return
    
    # Generate 3 random cards for the pack
    pack_cards = []
    
    for _ in range(3):
        # Determine rarity based on drop rates
        roll = random.randint(1, 100)
        cumulative = 0
        selected_rarity = 'common'
        
        for rarity, info in card_game.rarities.items():
            cumulative += info['drop_rate']
            if roll <= cumulative:
                selected_rarity = rarity
                break
        
        # Get random card of selected rarity
        rarity_cards = [card for card in card_game.card_library if card['rarity'] == selected_rarity]
        if rarity_cards:
            selected_card = random.choice(rarity_cards)
            pack_cards.append(selected_card)
            
            # Add card to user's collection in database
            card_data = get_card_by_name(selected_card['name'])
            if card_data:
                card_id = card_data[0]  # First column is card_id
                add_card_to_collection(ctx.author.id, card_id, 1)
    
    # Display the pack opening
    embed = discord.Embed(
        title="🎁 Card Pack Opened!", 
        description="You received 3 new cards and they've been added to your collection:",
        color=0xffd700
    )
    
    for i, card in enumerate(pack_cards, 1):
        rarity_info = card_game.rarities[card['rarity']]
        element_info = card_game.elements[card['element']]
        
        rarity_text = card['rarity'].title()
        if card['rarity'] in ['epic', 'legendary', 'mythic']:
            rarity_text = f"**{rarity_text}**"  # Bold for rare cards
        
        embed.add_field(
            name=f"Card {i}: {card['name']}", 
            value=f"{element_info['emoji']} {card['element'].title()} • {rarity_text}\n"
                  f"⚔️ {card['attack']} ATK • ❤️ {card['health']} HP • 💎 {card['cost']} Cost",
            inline=False
        )
    
    embed.set_footer(text="Use !cards to view your full collection!")
    
    await ctx.send(embed=embed)

# Placeholder commands for removed adventure game features
@bot.command(name='adventure')
async def adventure_command(ctx):
    """Adventure game has been replaced with the card game"""
    embed = discord.Embed(
        title="🎮 Adventure Game Retired", 
        description="The adventure game has been replaced with our new **Trading Card Game**!",
        color=0x9b59b6
    )
    
    embed.add_field(
        name="🃏 Try the New Card Game!", 
        value="🔹 `!cards` - View your collection\n🔹 `!pack` - Open card packs\n🔹 More features coming soon!",
        inline=False
    )
    
    embed.set_footer(text="The card game is still in development - stay tuned for battles and trading!")
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
        description="Your complete guide to XP systems and trading card battles!",
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
    
    # Trading Card Game Section  
    embed.add_field(
        name="🃏 Trading Card Game", 
        value=(
            "🔹 `!cards` - View your card collection\n"
            "🔹 `!pack` - Open card packs\n"
            "🔹 `!view <card name>` - See card in ASCII art\n"
            "🔹 `!adventure` - Info about the new card game\n"
            "⚡ *Fantasy creatures with ASCII art!*"
        ), 
        inline=True
    )
    
    # Card Elements
    embed.add_field(
        name="🌟 Card Elements", 
        value=(
            "🔥 **Fire** beats Earth\n"
            "💧 **Water** beats Fire\n"
            "🌍 **Earth** beats Air\n"
            "💨 **Air** beats Water\n"
            "✨ **Light** beats Dark\n"
            "🌑 **Dark** beats Light"
        ), 
        inline=True
    )
    
    # Card Rarities
    embed.add_field(
        name="💎 Card Rarities", 
        value=(
            "⚪ **Common** - 60% drop rate\n"
            "🔵 **Rare** - 25% drop rate\n"
            "🟣 **Epic** - 10% drop rate\n"
            "🟠 **Legendary** - 4% drop rate\n"
            "🟡 **Mythic** - 1% drop rate"
        ), 
        inline=True
    )
    
    # Quick Start Guide
    embed.add_field(
        name="🚀 Quick Start Guide", 
        value=(
            "1️⃣ Chat normally to gain XP\n"
            "2️⃣ Use `!pack` to open your first card pack\n"
            "3️⃣ Use `!cards` to view your collection\n"
            "4️⃣ Stay tuned for battles and trading!"
        ), 
        inline=True
    )
    
    # Coming Soon
    embed.add_field(
        name="🔮 Coming Soon", 
        value=(
            "⚔️ **Player vs Player Battles**\n"
            "🤖 **AI Opponents**\n"
            "💱 **Card Trading System**\n"
            "🏆 **Tournament Mode**\n"
            "🎯 **Daily Card Rewards**"
        ), 
        inline=True
    )
    
    # Footer with additional info
    embed.set_footer(
        text="💡 Tip: Open packs to collect rare cards! • 🎴 20 unique cards available",
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
