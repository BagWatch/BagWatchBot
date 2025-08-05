# Railway Deployment Guide

## 🔒 Security-First Quick Deploy

### Before You Start
**IMPORTANT**: This repository is public-safe. All sensitive information goes in Railway environment variables, NEVER in code.

## Quick Deploy Steps

1. **🍴 Fork this repository:**
   - Click "Fork" button on GitHub
   - This creates your own copy to connect to Railway

2. **📱 Prepare your tokens:**
   - Get Telegram bot token from [@BotFather](https://t.me/BotFather)
   - **Keep it secret!** Don't put it anywhere except Railway
   - Note your channel username (e.g., `@your_channel`)

3. **🚀 Deploy to Railway:**
   - Go to [Railway.app](https://railway.app)
   - Click "New Project" → "Deploy from GitHub repo"
   - Select **your forked repository**
   - Railway will auto-detect the Python app

4. **🔐 Set Environment Variables in Railway Dashboard:**
   
   **CRITICAL**: Set these in Railway Variables tab, NOT in code:
   ```
   TELEGRAM_TOKEN=your_bot_token_from_botfather
   CHANNEL_ID=your_channel_id
   HELIUS_API_KEY=your_helius_api_key
   ```
   
   ✨ **Helius gives you:**
   - Much better performance and reliability
   - Faster WebSocket connections
   - Better rate limits
   - Enhanced metadata support

4. **Verify Deployment:**
   - Check "Deployments" tab for logs
   - Look for "Bot is running on Railway..." message
   - Test by launching a token on Bags (if possible)

## Railway Configuration Files

- `Procfile` - Tells Railway to run as worker process
- `requirements.txt` - Python dependencies
- `railway.json` - Railway-specific settings
- `runtime.txt` - Python version specification

## Environment Variables

Set these in Railway dashboard → Your Project → Variables:

| Variable | Value | Description |
|----------|--------|-------------|
| `TELEGRAM_TOKEN` | `1234567890:ABC...` | From @BotFather |
| `CHANNEL_ID` | `@channel` or `-100123...` | Your channel |
| `RPC_URL` | `https://...` | Optional: Custom RPC |

## Post-Deployment

1. **Monitor logs** in Railway dashboard
2. **Add bot as admin** to your Telegram channel
3. **Test the setup** by checking logs for WebSocket connection
4. **Wait for new Bags tokens** to verify posting works

The bot will run 24/7 on Railway and automatically restart if it crashes.