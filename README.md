# Discord Community Bot

A Discord bot with XP leveling system and text-based adventure game. Everything is configurable through Discord commands - no code editing required!

## Features

- **XP System**: Users gain XP for messages, level up, compete on leaderboards
- **Adventure Game**: Text RPG with exploration, combat, shopping, and inventory  
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
- `!leaderboard` - See top users
- `!adventure` - Start the adventure game
- `!action <action>` - Do things in the game (explore, hunt, shop, etc.)
- `!inventory` - Check your items
- `!help_custom` - Show all commands

### For Admins Only
- `!config list` - See all settings
- `!config set <setting> <value>` - Change settings
- `!config get <setting>` - Check a setting

## Configuration Examples

```
!config set xp_per_message 25          # XP per message
!config set xp_cooldown 30              # Cooldown in seconds  
!config set welcome_message "Welcome {user}!"  # New member message
!config set game_enabled False          # Turn off adventure game
```

## Game Overview

**Town** 🏘️ - Shop for items, rest to heal
**Forest** 🌲 - Hunt monsters for gold
**Cave** 🕳️ - Mine for treasure

Use `!adventure` to start, then `!action explore` to do things!

## Files Needed

Create these files in your GitHub repository:

**bot.py** - Main bot code (copy from the Python code artifact)
**requirements.txt** - Just these two lines:
```
discord.py>=2.3.0
python-dotenv>=1.0.0
```

## Troubleshooting

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
