# Bags Launchpad Telegram Bot

A real-time Telegram bot that monitors the Bags launchpad for new token launches using Solana WebSocket subscriptions.

## 🔒 Security Notice

**IMPORTANT**: This repository is designed to be public-safe. Never commit sensitive information like bot tokens or private keys to the repository. All sensitive configuration is handled through environment variables.

## Features

- 🚀 Real-time monitoring of new token launches on Bags launchpad
- 📱 Automatic Telegram channel posting with token details
- 🖼️ Token image previews in messages
- 🔗 Clickable Twitter and Solscan links
- 💰 Royalty percentage display
- 🔄 Automatic reconnection and error handling
- 🚫 Duplicate prevention

## Railway Deployment

### Prerequisites

1. Create a Telegram bot:
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Create a new bot with `/newbot`
   - Save the bot token

2. Get your channel ID:
   - Add your bot to your Telegram channel as an admin
   - Use your channel username (e.g., `@your_channel`) or numeric ID

### Deploy to Railway

1. **Fork this repository to your GitHub account**
   - Click "Fork" in the top right of this repository
   - This creates your own copy that you can safely connect to Railway

2. **Get your Telegram credentials:**
   - Create bot with [@BotFather](https://t.me/BotFather)
   - Save the bot token (keep it secret!)
   - Get your channel username or ID

3. **Connect to Railway:**
   - Go to [Railway.app](https://railway.app)
   - Sign up/Login with GitHub
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your forked repository

4. **🔐 Set Environment Variables in Railway Dashboard:**
   
   **CRITICAL**: Never put these values in code! Set them in Railway:
   
   Go to your Railway project → Variables tab and add:
   ```
   TELEGRAM_TOKEN=1234567890:ABC...xyz
   CHANNEL_ID=@your_channel_username
   HELIUS_API_KEY=your_helius_api_key
   ```

   Optional variables (only if not using Helius):
   ```
   RPC_URL=your_custom_solana_rpc_endpoint
   ```

5. **Deploy:**
   - Railway will automatically detect the Python app
   - It will install dependencies from `requirements.txt`
   - The bot will start as a worker process (defined in `Procfile`)
   - Check the logs to confirm it's running

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TELEGRAM_TOKEN` | ✅ | Bot token from @BotFather | `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz` |
| `CHANNEL_ID` | ✅ | Channel username or ID | `@mybagschannel` or `-1001234567890` |
| `HELIUS_API_KEY` | 🔥 | Helius API key (highly recommended) | `your-helius-api-key` |
| `RPC_URL` | ❌ | Custom RPC (only if not using Helius) | `https://your-rpc-endpoint.com` |

### Getting Your Channel ID

**Method 1: Using Channel Username**
- Use your channel username: `@your_channel_name`

**Method 2: Using Numeric ID**
1. Add [@userinfobot](https://t.me/userinfobot) to your channel
2. Forward a message from your channel to the bot
3. It will reply with the channel ID (e.g., `-1001234567890`)
4. Remove the bot from your channel

### Local Development

**🔒 Security First**: Never commit your actual tokens!

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Copy the example environment file:**
   ```bash
   cp env.example .env
   ```

3. **Edit .env with your actual values:**
   ```bash
   # Edit .env file (this is gitignored for security)
   TELEGRAM_TOKEN=your_actual_bot_token
   CHANNEL_ID=@your_actual_channel
   ```

4. **Load environment and run:**
   ```bash
   # On Unix/Mac:
   source .env && python bags_telegram_bot.py
   
   # On Windows PowerShell:
   Get-Content .env | ForEach-Object { 
     $key, $value = $_ -split '=', 2
     [Environment]::SetEnvironmentVariable($key, $value, 'Process')
   }
   python bags_telegram_bot.py
   ```

**Alternative - Direct export (Unix/Mac):**
```bash
export TELEGRAM_TOKEN="your_bot_token"
export CHANNEL_ID="@your_channel"
python bags_telegram_bot.py
```

### Monitoring

- **Railway Logs:** Check the "Deployments" tab in Railway for real-time logs
- **Bot Status:** The bot logs connection status and token processing
- **Error Handling:** Automatic reconnection for WebSocket and comprehensive error logging

### Message Format

The bot sends messages like this:

```
🚀 New Coin Launched on Bags!

Name: OG BAGS
Ticker: OGBAGS
Contract: HUQT5qnag1RQCbRFUM1h4f45YZ6nSsEBzg2spomfBAGS
View on Solscan

Creator: @creator_twitter
Fee Recipient: @fee_recipient
Royalty: 5%

Website: https://token-website.com
```

### Technical Details

- **WebSocket Monitoring:** Uses Solana's `logsSubscribe` for real-time updates
- **Metadata Parsing:** Fetches token metadata from Metaplex program
- **IPFS Integration:** Retrieves token details from IPFS/Arweave
- **Duplicate Prevention:** Maintains seen tokens to avoid reposts
- **Auto-reconnection:** Handles WebSocket disconnections gracefully

### Troubleshooting

**Bot not posting:**
- Check Railway logs for errors
- Verify environment variables are set correctly
- Ensure bot is admin in the channel
- Check if channel ID format is correct

**WebSocket errors:**
- The bot automatically reconnects on failures
- Check if RPC endpoint is accessible
- Consider using a premium RPC provider for better reliability

**Rate limiting:**
- Bot includes proper rate limiting for Telegram API
- WebSocket updates are processed asynchronously

### Support

For issues related to:
- **Railway deployment:** Check Railway documentation
- **Telegram Bot API:** See [Telegram Bot API docs](https://core.telegram.org/bots/api)
- **Solana integration:** Refer to [Solana documentation](https://docs.solana.com/)

### License

MIT License - Feel free to modify and distribute.