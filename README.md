# 🤖 VibeBot - Discord Community Bot

A comprehensive Discord bot featuring XP leveling and a complete **Trading Card Game** with 58 unique fantasy creatures! Everything is configurable through Discord commands - no code editing required!

## ✨ Features

### 🎯 Core Systems
- **XP System**: Users gain XP for messages, level up with progressive scaling, compete on leaderboards
- **Trading Card Game**: Collect 58 unique cards across 6 elements and 5 rarities with ASCII art
- **Pack Token Economy**: Daily rewards give tokens, spend tokens to open card packs
- **Daily Rewards**: Streak-based system with increasing rewards for consistent play
- **Admin Controls**: Configure everything via Discord slash commands
- **24/7 Cloud Hosting**: Runs on Render with PostgreSQL database support

### 🃏 Trading Card Game Features
- **58 Unique Cards**: Fantasy creatures with custom ASCII art and abilities
- **6 Elements**: Fire, Water, Earth, Air, Light, Dark with rock-paper-scissors advantages
- **5 Rarity Tiers**: Common (60%), Rare (25%), Epic (10%), Legendary (4%), Mythic (1%)
- **Pack Token System**: Earn tokens daily, spend to open 3-card packs
- **Collection Tracking**: View your cards with pagination and rarity breakdowns
- **Card Viewing**: See individual cards in full ASCII art glory
- **Strategic Depth**: Each card has attack, health, cost, and unique abilities

### 📊 Advanced XP System
- **Progressive Scaling**: Each level requires more XP (configurable multiplier and scaling factor)
- **Cooldown System**: Prevents XP spam with configurable cooldown periods
- **Username Caching**: Remembers usernames even when users leave the server
- **Detailed Progress**: Shows exact XP needed for next level with progress bars
- **XP Tables**: View requirements for any level range

### 🏆 Competition & Social
- **XP Leaderboards**: See top chat contributors with cached usernames
- **Collection Stats**: Track total cards, unique cards, and rare finds
- **Server Statistics**: Comprehensive bot usage stats and community metrics
- **Welcome Messages**: Configurable new member greetings
- **Level Up Announcements**: Customizable level up messages

## 🚀 Quick Setup

### 1. Discord Developer Portal
1. Go to https://discord.com/developers/applications
2. Create New Application → Add Bot
3. Copy the bot token (save it!)
4. Enable "Message Content Intent"
5. Go to OAuth2 → URL Generator → Select "bot" and "applications.commands" → Copy invite link

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
   - (Optional) Add `DATABASE_URL` for PostgreSQL cloud database
4. Deploy (takes 5-10 minutes)

*Note: The bot includes a Flask web server so Render recognizes it as a running service.*

### 4. Invite Bot & Test
1. Use invite link from step 1 to add bot to your server
2. Test with `/help` command
3. Configure with `/config` commands

### 5. Keep Online (UptimeRobot)
1. Sign up at https://uptimerobot.com
2. Add HTTP monitor with your Render app URL
3. Set 5-minute intervals

## 📋 Commands

### 🃏 Trading Card Game
- `/cards [page]` - View your card collection with stats and pagination
- `/pack` - Open a card pack using pack tokens (3 random cards)
- `/view <card_name>` - View a specific card in full ASCII art
- `/daily` - Claim daily pack tokens (streak bonuses available!)

### 📊 Chat Activity & XP System
- `/level [user]` - Check XP and level with progress bar
- `/leaderboard [limit]` - See top chat XP users (default 10, max 25)
- `/xp_table [max_level]` - View XP requirements for levels (default 10, max 25)
- `/stats` - Comprehensive server bot statistics

### 🆘 Help & Information
- `/help` - Complete command guide with card game info

### ⚙️ Admin Commands (Administrator Permission Required)
- `/config action:list` - View all bot settings
- `/config action:get key:<setting>` - Check a specific setting
- `/config action:set key:<setting> value:<value>` - Change a setting
- `/status` - Detailed bot and database status dashboard
- `/wipe_cards` - Reset all card data (with button confirmation)

### 🎮 Legacy Commands (Still Available)
- `!level`, `!leaderboard`, `!cards`, `!pack`, `!view`, `!help` - Traditional prefix commands
- `!config list/get/set` - Traditional admin configuration

## ⚙️ Configuration Settings

### XP System Settings
```
/config action:set key:xp_per_message value:15              # XP gained per message (default: 15)
/config action:set key:xp_cooldown value:60                 # Cooldown between XP gains in seconds (default: 60)
/config action:set key:level_multiplier value:100           # Base XP for first level up (default: 100)
/config action:set key:level_scaling_factor value:1.2       # How much harder each level gets (default: 1.2)
/config action:set key:xp_channel value:None                # Channel for level up messages (None = same channel)
/config action:set key:level_up_message value:"Congratulations {user}! You reached level {level}!"
```

### Card Game Settings
```
/config action:set key:game_enabled value:True              # Enable/disable card game
```

### Welcome System
```
/config action:set key:welcome_message value:"Welcome to the server, {user}!"  # New member greeting
```

## 🃏 Card Game Guide

### 🌟 Card Elements & Advantages

| Element | Emoji | Beats | Color |
|---------|-------|-------|-------|
| 🔥 Fire | 🔥 | Earth | Orange |
| 💧 Water | 💧 | Fire | Blue |
| 🌍 Earth | 🌍 | Air | Brown |
| 💨 Air | 💨 | Water | Light Blue |
| ✨ Light | ✨ | Dark | Gold |
| 🌑 Dark | 🌑 | Light | Purple |

### 💎 Card Rarities & Drop Rates

| Rarity | Emoji | Drop Rate | Border | Description |
|--------|-------|-----------|--------|-------------|
| Common | ⚪ | 60% | ─ | Basic creatures, reliable stats |
| Rare | 🔵 | 25% | ═ | Enhanced abilities and stats |
| Epic | 🟣 | 10% | ━ | Powerful creatures with special effects |
| Legendary | 🟠 | 4% | █ | Iconic creatures with game-changing abilities |
| Mythic | 🟡 | 1% | ▓ | Ultra-rare, the most powerful cards |

### 🎁 Daily Reward System

**Streak Rewards:**
- **Days 1-6**: 1 pack token
- **Day 7**: 2 pack tokens + Weekly Bonus
- **Day 30**: 3 pack tokens + Monthly Legendary
- **Every 7 days**: 2 pack tokens + Streak Milestone
- **After 14 days**: Chance for bonus tokens based on streak length

### 🎯 Card Collection Goals

- **Total Cards**: 58 unique cards to collect
- **Complete Sets**: Collect all cards from each element
- **Rarity Master**: Obtain at least one card of each rarity
- **Element Master**: Get powerful cards from your favorite element
- **Mythic Hunter**: Find the ultra-rare 1% drop rate cards

### 🎮 Card Abilities (Examples)

- **Rush**: Can attack immediately when played
- **Stealth**: Cannot be targeted by enemies
- **Armor**: Reduces incoming damage
- **Flying**: Cannot be blocked by ground creatures
- **Burn**: Deals extra damage over time
- **Heal**: Restores health when played
- **Draw**: Draw additional cards when played

## 📁 Files Needed

Create these files in your GitHub repository:

**requirements.txt**:
```
discord.py>=2.3.0
python-dotenv>=1.0.0
flask>=2.3.0
psycopg2-binary>=2.9.0
psutil>=5.9.0
```

**bot.py** - Main bot code (copy from the provided Python file)

## 🔧 Advanced Features

### 🗄️ Database System
- **Hybrid Database**: PostgreSQL for cloud (with DATABASE_URL) or SQLite for local
- **Automatic Migrations**: Database updates itself when new features are added
- **Data Persistence**: All progress and cards saved automatically
- **Username Caching**: Remembers usernames even when users leave
- **Card Storage**: Efficient storage of user collections and pack tokens

### 🛡️ Error Handling
- **Slash Command Support**: Modern Discord slash commands with fallback to traditional
- **Permission Checks**: Clear error messages for unauthorized commands
- **Graceful Failures**: Bot continues running even if individual commands fail
- **Auto-Cleanup**: Cooldown messages auto-delete to reduce clutter
- **Button Confirmations**: Safe admin actions with interactive buttons

### 🎨 Rich Embeds
- **Color-Coded Cards**: Each rarity has its own color scheme
- **ASCII Art Display**: Beautiful card presentations in code blocks
- **Progress Bars**: Visual XP progress indicators
- **Organized Information**: Clean, easy-to-read command outputs
- **Interactive Elements**: Helpful footers and navigation tips

### 🔮 Coming Soon (Phase 2)
- **Player vs Player Battles**: Strategic turn-based combat
- **Deck Building**: Create custom 20-card decks
- **Battle Rankings**: Competitive ladder system
- **Card Trading**: Exchange cards with other players
- **Tournament Mode**: Weekly competitions with prizes

## 🛠️ Troubleshooting

**"No open ports detected" in Render logs?**
- This is normal! The bot includes a Flask web server that should resolve this
- Your bot should still work fine in Discord even with this message
- Check if bot responds to `/help` in your server

**Bot not responding to slash commands?**
- Make sure you invited the bot with "applications.commands" scope
- Slash commands may take up to 1 hour to sync globally
- Try traditional commands like `!help` as a fallback

**Bot not responding at all?**
- Check Discord bot has "Message Content Intent" enabled
- Verify bot token is correct in Render environment variables
- Make sure bot has permission to send messages in your server

**Database issues?**
- Bot automatically handles database migrations
- Check `/status` command for database connection info
- PostgreSQL is used if DATABASE_URL is set, otherwise SQLite

**Card game not working?**
- Check if game is enabled: `/config action:get key:game_enabled`
- Enable if needed: `/config action:set key:game_enabled value:True`
- Try `/daily` to get your first pack tokens

## 🎯 Support & Customization

### 🔧 Easy Customization
- **No Code Required**: All settings configurable via Discord commands
- **Real-Time Changes**: Settings take effect immediately
- **Flexible Scaling**: Adjust XP rates and level requirements
- **Feature Toggles**: Enable/disable systems as needed

### 📊 Monitoring
- **Built-in Statistics**: Track usage with `/stats` command
- **Status Dashboard**: Comprehensive system health with `/status`
- **Health Endpoints**: `/health` endpoint for monitoring services
- **Activity Tracking**: User engagement and card collection metrics

### 🎮 Game Balance
- **Carefully Tuned**: Drop rates balanced for engaging progression
- **Scalable Difficulty**: Progressive XP requirements prevent inflation
- **Daily Engagement**: Streak system encourages consistent play
- **Collection Goals**: Multiple achievement paths for different play styles

## 🌟 What Makes This Special

- **58 Unique Cards**: Each with custom ASCII art and lore
- **No Pay-to-Win**: All cards obtainable through daily play
- **Streak Rewards**: Consistent players get better rewards
- **Visual Appeal**: Beautiful ASCII art cards in Discord
- **Strategic Depth**: Element advantages and card abilities
- **Community Focus**: Leaderboards and collection sharing
- **Future-Proof**: Built for upcoming battle system

---

**Ready to start your card collection journey?** Invite the bot and use `/daily` to get your first pack tokens! 🃏✨

*Built with Discord.py • Hosted on Render • PostgreSQL Database • 24/7 Uptime*
