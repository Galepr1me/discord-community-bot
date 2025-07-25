# Discord Community Bot

A comprehensive Discord bot with XP leveling system and text-based adventure RPG. Everything is configurable through Discord commands - no code editing required!

## Features

### 🎯 Core Systems
- **XP System**: Users gain XP for messages, level up with progressive scaling, compete on leaderboards
- **Adventure RPG**: Full text-based game with exploration, combat, shopping, functional items, and boss battles
- **Daily Quests**: New challenges every day with gold rewards and progress tracking
- **Multiple Leaderboards**: Chat XP rankings AND adventure rankings (gold, level, monster kills)
- **Admin Controls**: Configure everything via Discord commands
- **24/7 Hosting**: Runs on Render with UptimeRobot monitoring

### 🎮 Adventure Game Features
- **3 Unique Locations**: Town (safe zone), Forest (hunting), Cave (mining)
- **Functional Combat System**: Weapons boost damage, shields reduce damage taken
- **Working Items**: Health potions heal, magic scrolls give XP, equipment provides bonuses
- **Adventure Progression**: Separate leveling system for adventuring (200 XP per level)
- **Boss Battles**: Giant Wolf Alpha (Forest), Ancient Dragon (Cave) with massive rewards
- **Rare Events**: 5% chance for epic discoveries, 1% for legendary treasures
- **Smart Inventory**: Items stack and show their effects
- **Quest System**: Daily challenges with completion tracking and rewards

### 📊 Advanced XP System
- **Progressive Scaling**: Each level requires more XP (configurable multiplier and scaling factor)
- **Cooldown System**: Prevents XP spam with configurable cooldown periods
- **Username Caching**: Remembers usernames even when users leave the server
- **Detailed Progress**: Shows exact XP needed for next level with progress bars
- **XP Tables**: View requirements for any level range

### 🏆 Competition & Social
- **Multiple Leaderboards**: Chat XP, Adventure Gold, Adventure Level, Monster Kills
- **Server Statistics**: Comprehensive bot usage stats and community metrics
- **Welcome Messages**: Configurable new member greetings
- **Level Up Announcements**: Customizable level up messages

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

*Note: The bot includes a Flask web server so Render recognizes it as a running service.*

### 4. Invite Bot & Test
1. Use invite link from step 1 to add bot to your server
2. Test with `!help_custom` command
3. Configure with `!config` commands

### 5. Keep Online (UptimeRobot)
1. Sign up at https://uptimerobot.com
2. Add HTTP monitor with your Render app URL
3. Set 5-minute intervals

## Commands

### 📊 Chat Activity & XP System
- `!level` - Check your XP and level with progress bar
- `!level @user` - Check another user's level and progress
- `!leaderboard [limit]` - See top chat XP users (default 10)
- `!xp_table [max_level]` - View XP requirements for levels (default 10, max 25)
- `!stats` - Comprehensive server bot statistics

### 🎮 Adventure RPG Game
- `!adventure` - Start/continue your adventure (shows daily quest too!)
- `!action <action>` - Perform actions:
  - **explore** - General exploration (all locations)
  - **hunt** - Hunt monsters (Forest only)
  - **mine** - Mine for gold (Cave only)
  - **shop** - View town shop (Town only)
  - **rest** - Restore full health (Town only)
  - **dig** - Alternative cave action
  - **gather** - Alternative forest action
- `!inventory` - Check your items and their effects
- `!use <item>` - Use consumable items (potions, scrolls)
- `!buy <item>` - Purchase items from the town shop

### 🏆 Leaderboards & Competition
- `!adventure_leaderboard gold` - Top gold collectors
- `!adventure_leaderboard level` - Highest adventure levels
- `!adventure_leaderboard monsters` - Most monsters defeated

### 📋 Daily Quest System
- `!daily_quest` - Check today's quest progress
- `!claim_quest` - Claim completed daily quest rewards

### 🆘 Help & Information
- `!help` or `!help_custom` - Complete command guide with examples

### ⚙️ Admin Commands (Administrator Permission Required)
- `!config list` - View all bot settings
- `!config get <setting>` - Check a specific setting
- `!config set <setting> <value>` - Change a setting

## Configuration Settings

### XP System Settings
```
!config set xp_per_message 15              # XP gained per message (default: 15)
!config set xp_cooldown 60                 # Cooldown between XP gains in seconds (default: 60)
!config set level_multiplier 100           # Base XP for first level up (default: 100)
!config set level_scaling_factor 1.2       # How much harder each level gets (default: 1.2 = 20% increase)
!config set xp_channel None                # Channel for level up messages (None = same channel)
!config set level_up_message "Congratulations {user}! You reached level {level}!"
```

### Adventure Game Settings
```
!config set game_enabled True              # Enable/disable adventure game
!config set rare_event_chance 5            # Chance for rare events (default: 5%)
!config set legendary_event_chance 1       # Chance for legendary finds (default: 1%)
!config set boss_encounter_chance 3        # Chance for boss battles (default: 3%)
!config set daily_quests_enabled True      # Enable daily quest system
!config set adventure_leaderboard_enabled True  # Show adventure leaderboards
```

### Welcome System
```
!config set welcome_message "Welcome to the server, {user}!"  # New member greeting
```

## Game Guide

### 🗺️ Adventure Locations

**🏘️ Town** - Your safe haven
- **Actions**: explore, shop, rest
- **Features**: Item shop, full health restoration, safe exploration
- **Connections**: Forest, Cave

**🌲 Forest** - The hunting grounds  
- **Actions**: hunt, gather, explore
- **Monsters**: Goblins, Wolves
- **Boss**: Giant Wolf Alpha (80 HP, 200 gold, 100 XP reward)
- **Connections**: Town, Cave

**🕳️ Cave** - The treasure depths
- **Actions**: mine, explore, dig  
- **Monsters**: Bats, Spiders, Orcs
- **Boss**: Ancient Dragon (120 HP, 500 gold, 200 XP reward)
- **Connections**: Town, Forest

### 🛍️ Shop Items & Effects

| Item | Price | Effect | Description |
|------|-------|--------|-------------|
| Health Potion | 20 gold | Heal +50 HP | Restores 50 health points |
| Sword | 100 gold | Weapon +15 damage | Increases combat damage and gold from monsters |
| Shield | 80 gold | Defense +10 | Reduces damage taken in combat |
| Magic Scroll | 150 gold | Magic +25 XP | Grants 25 adventure XP when used |

### 🎲 Special Events

**✨ Rare Events (5% chance)**
- Epic treasure discoveries worth 150-300 gold
- Mysterious wizard encounters with health bonuses
- Ancient maps leading to hidden treasures
- Lucky finds with fortune boosts

**🌟 Legendary Events (1% chance)**
- Ancient treasure chests worth 800+ gold
- Crown of Kings discoveries worth 1000+ gold  
- Legendary weapon finds (Excalibur!) worth 500+ gold
- Massive XP bonuses (200-300 adventure XP)

**👹 Boss Encounters (3% chance)**
- Location-specific bosses with high rewards
- Success based on adventure level and equipment
- Risk vs reward gameplay - high damage if you lose!

### 📋 Daily Quest Types

- **Monster Hunter**: Defeat X monsters for gold rewards
- **Explorer**: Explore X times for gold rewards  
- **Miner**: Mine X times for gold rewards
- **Gold Collector**: Collect X gold for bonus rewards

*New quest generated daily based on your user ID - everyone gets different quests!*

### 🎯 Adventure Progression

- **Adventure XP**: Separate from chat XP, gained through game actions
- **Adventure Levels**: 200 XP per level, affects boss battle success
- **Monster Tracking**: Defeats tracked for leaderboards
- **Gold Economy**: Persistent currency for items and upgrades

## Files Needed

Create these files in your GitHub repository:

**requirements.txt**:
```
discord.py>=2.3.0
python-dotenv>=1.0.0
flask>=2.3.0
```

**bot.py** - Main bot code (copy from the provided Python file)

## Advanced Features

### 🔄 Database System
- **Automatic Migrations**: Database updates itself when new features are added
- **Data Persistence**: All progress saved automatically
- **Username Caching**: Remembers usernames even when users leave
- **Backup-Friendly**: Single SQLite file for easy backups

### 🛡️ Error Handling
- **Cooldown Management**: Prevents command spam with user-friendly messages
- **Permission Checks**: Clear error messages for unauthorized commands
- **Graceful Failures**: Bot continues running even if individual commands fail
- **Auto-Cleanup**: Cooldown messages auto-delete to reduce clutter

### 🎨 Rich Embeds
- **Color-Coded Messages**: Different colors for different message types
- **Progress Bars**: Visual XP progress indicators
- **Organized Information**: Clean, easy-to-read command outputs
- **Interactive Elements**: Helpful footers and tips

## Troubleshooting

**"No open ports detected" in Render logs?**
- This is normal! The bot includes a Flask web server that should resolve this
- Your bot should still work fine in Discord even with this message
- Check if bot responds to `!help_custom` in your server

**Bot not responding?**
- Check Discord bot has "Message Content Intent" enabled
- Verify bot token is correct in Render environment variables
- Make sure bot has permission to send messages in your server

**Bot goes offline?**
- UptimeRobot should prevent this by pinging the Flask server
- Check Render logs for errors
- Free Render services sleep without monitoring

**Database issues?**
- Bot automatically handles database migrations
- If needed, redeploy on Render to reset everything
- All data is saved in a single `bot_data.db` file

**Commands not working?**
- Check bot permissions in your Discord server
- Verify the command prefix is `!`
- Use `!help_custom` to see all available commands
- Admin commands require Administrator permission

## Support & Customization

### 🔧 Easy Customization
- **No Code Required**: All settings configurable via Discord commands
- **Real-Time Changes**: Settings take effect immediately
- **Flexible Scaling**: Adjust XP rates, event chances, and rewards
- **Feature Toggles**: Enable/disable entire systems as needed

### 📊 Monitoring
- **Built-in Statistics**: Track usage with `!stats` command
- **Leaderboard Analytics**: See which features are most popular
- **Health Endpoints**: `/health` endpoint for monitoring services
- **Activity Tracking**: Comprehensive user engagement metrics

### 🎮 Game Balance
- **Configurable Rates**: Adjust rare event chances and rewards
- **Scalable Difficulty**: Progressive XP requirements prevent inflation
- **Economic Balance**: Item prices and rewards carefully tuned
- **Risk vs Reward**: Boss battles and rare events provide meaningful choices

That's it! Your bot will run 24/7 and handle everything automatically. Configure it through Discord commands and enjoy the complete RPG experience! 🎮✨

---

*Built with Discord.py • Hosted on Render • Monitored by UptimeRobot*
