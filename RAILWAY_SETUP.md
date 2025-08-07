# Railway Environment Setup

## 🔐 SECURITY: API Keys in Railway Environment

**NEVER** commit API keys to Git! Always set them as environment variables in Railway.

## Railway Environment Variables

Set these environment variables in your Railway dashboard:

### Required Variables
```bash
TELEGRAM_TOKEN=your_telegram_bot_token_from_botfather
CHANNEL_ID=@your_channel_or_-100123456789
HELIUS_API_KEY=your_helius_api_key_from_helius_xyz
BAGS_API_KEY=your_bags_api_key_here
```

## How to Set Environment Variables in Railway

1. Go to your Railway project dashboard
2. Click on your service
3. Go to the **Variables** tab
4. Add each environment variable:
   - **Variable**: `TELEGRAM_TOKEN`
   - **Value**: `your_actual_token_here`
   - Click **Add**
   - Repeat for all variables

## Deploy Command

Once environment variables are set:

```bash
git add -A
git commit -m "Deploy API-only version"
git push origin main
```

## 🎯 What This Version Does

✅ **Uses ONLY Official Bags API** - No browser scraping
✅ **Gets Complete Fee Split Data** - Creator and recipient Twitter
✅ **Fast & Reliable** - Direct API calls
✅ **Secure** - No API keys in code
✅ **Clean Dependencies** - No Selenium/ChromeDriver needed

## API Endpoints Used

- `/token-launch/creator/v2` - Gets creator and fee recipient info
- `/token-launch/lifetime-fees` - Gets token fee data

## Expected Message Format

```
🚀 New Coin Launched on Bags!

Name: Dione
Ticker: DIONE
Mint: 9qGkBEwSEAZrosHpLBcKuW61w8WuyCCMyYdy93TJBAGS
Solscan: https://solscan.io/token/9qGk...

Creator: @0xBUBO
Fee Recipient: @dioneapp

🎒 View on Bags
📈 TRADE NOW:
• AXIOM
• Photon
```
