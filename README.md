# Discord Community Bot

A Discord bot with XP leveling system and text-based adventure game. Everything is configurable through Discord commands - no code editing required!

## Features

- **XP System**: Users gain XP for messages, level up, compete on leaderboards
- **Adventure Game**: Text RPG with exploration, combat, shopping, functional items, and boss battles
- **Daily Quests**: New challenges every day with gold rewards  
- **Rare Events**: 5% chance for epic discoveries, 1% for legendary treasures, 3% for boss encounters
- **Adventure Progression**: Separate leveling system for adventuring with XP rewards
- **Multiple Leaderboards**: Chat XP rankings AND adventure rankings (gold, level, monster kills)
- **Functional Items**: Potions actually heal, weapons boost combat, shields reduce damage
- **Admin Controls**: Configure everything via Discord commands
- **24/7 Hosting**: Runs on Render with UptimeRobot monitoring

## Quick Setup

### 1. Discord Developer Portal
1. Go to https://discord.com/developers/applications
2. Create New Application → Add Bot
3. Copy the bot token (save it!)
4. Enable "Message Content Intent" and "Server Members Intent"
5. Go to OAuth2 → URL Generator → Select "bot" → Copy invite link

### 2. GitHub Repository  
1. Create new public repository
2. Upload these files:
   - `bot.py` (the main bot code)
   - `requirements.txt` (dependencies)
   - `README.md` (this file)

### 3. Render Deployment
1. Sign up at https://render.com with GitHub
2. Create Web Service → Connect your repository
3. Settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
   - Add Environment Variable: `DISCORD_TOKEN` = your bot token
4. Deploy (takes 5-10 minutes)

*Note: The bot includes a simple web server so Render recognizes it as a running service.*

### 4. Invite Bot & Test
1. Use invite link from step 1 to add bot to your server
2. Test with `!help_custom` command
3. Configure with `!config` commands

### 5. Keep Online (UptimeRobot)
1. Sign up at https://uptimerobot.com
2. Add HTTP monitor with your Render app URL
3. Set 5-minute intervals

## Commands

### For Everyone
- `!level` - Check your XP and level
- `!leaderboard` - See top chat XP users
- `!adventure` - Start the adventure game (shows daily quest too!)
- `!action <action>` - Do things in the game (explore, hunt, shop, mine, etc.)
- `!inventory` - Check your items and their effects
- `!use <item>` - Use potions and consumable items
- `!buy <item>` - Purchase items from the town shop
- `!adventure_leaderboard <type>` - Adventure rankings (gold/level/monsters)
- `!daily_quest` - Check today's quest progress  
- `!claim_quest` - Claim completed daily quest rewards
- `!help_custom` - Show all commands

### For Admins Only
- `!config list` - See all settings
- `!config set <setting> <value>` - Change settings
- `!config get <setting>` - Check a setting

## Configuration Examples

```
# Standard XP Settings
!config set xp_per_message 25          # XP per message
!config set xp_cooldown 30              # Cooldown in seconds  
!config set welcome_message "Welcome {user}!"  # New member message

# Adventure Game Settings  
!config set rare_event_chance 10        # 10% chance for rare events
!config set legendary_event_chance 2    # 2% chance for legendary finds
!config set boss_encounter_chance 5     # 5% chance for boss battles
!config set daily_quests_enabled True   # Enable daily quests
!config set adventure_leaderboard_enabled True  # Show adventure rankings

# Disable features if needed
!config set game_enabled False          # Turn off adventure game
!config set daily_quests_enabled False  # Disable daily quests
```

## Game Overview

**🏘️ Town** - Shop for items, rest to heal, safe exploration
**🌲 Forest** - Hunt monsters (Goblins, Wolves), chance for Giant Wolf Alpha boss  
**🕳️ Cave** - Mine for gold, fight dangerous creatures (Bats, Spiders, Orcs), Ancient Dragon boss

### New Exciting Features:
- **🎲 Rare Events (5%)**: Find epic treasures worth 150-300 gold
- **🌟 Legendary Events (1%)**: Discover ancient artifacts worth 500-1000 gold  
- **👹 Boss Battles (3%)**: Fight powerful bosses for massive rewards (but high risk!)
- **📋 Daily Quests**: "Defeat 5 monsters", "Explore 10 times", "Collect 300 gold", etc.
- **⚔️ Functional Combat**: Swords boost damage, shields reduce damage taken
- **💚 Working Items**: Health potions actually heal you, magic scrolls give XP
- **📈 Adventure Levels**: Separate progression system - gain XP for all adventure actions!

Use `!adventure` to start, then `!action explore` to begin your journey!

## Files Needed

Create these files in your GitHub repository:

**bot.py** - Main bot code (copy from the Python code artifact)
**requirements.txt** - Just these three lines:
```
discord.py>=2.3.0
python-dotenv>=1.0.0
flask>=2.3.0
```

## Troubleshooting

**"No open ports detected" in Render logs?**
- This is normal! The bot includes a web server that should resolve this
- Your bot should still work fine in Discord even with this message
- Check if bot responds to `!help_custom` in your server

**Bot not responding?**
- Check Discord bot has "Message Content Intent" enabled
- Verify bot token is correct in Render environment variables
- Make sure bot has permission to send messages in your server

**Bot goes offline?**
- UptimeRobot should prevent this
- Check Render logs for errors
- Free Render services sleep without monitoring

## Support

All data is saved automatically. The bot creates its own database file. If you need to reset everything, just redeploy on Render.

That's it! Your bot will run 24/7 and handle everything automatically. Configure it through Discord commands and enjoy! 🎮
