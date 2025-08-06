#!/usr/bin/env python3
"""
Bags Launchpad Telegram Bot - Upgraded Version

This bot monitors the Bags launchpad for new token launches using minimal RPC calls
and fetches all metadata from the Bags API for better reliability and performance.

Key improvements:
- Reduced RPC dependency (only for detecting new mints)
- Uses Bags API for all token metadata
- Simplified WebSocket monitoring
- Better error handling and fallbacks

Installation:
pip install python-telegram-bot==20.3 requests websockets solana

Usage:
1. Set TELEGRAM_TOKEN to your bot token from @BotFather
2. Set CHANNEL_ID to your channel ID (e.g., "@your_channel" or "-1001234567890")
3. Run: python main.py
"""

import json
import asyncio
import logging
import time
import os
from typing import Dict, Any, Optional, Set
import requests
from telegram import Bot
from telegram.constants import ParseMode
import websockets

# ============================================================================
# CONFIGURATION
# ============================================================================

# Telegram bot configuration - SET THESE AS RAILWAY ENVIRONMENT VARIABLES
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Get from @BotFather
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Your channel username or ID

# Solana RPC endpoint - only used for mint detection
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")

# Build Helius RPC URL if API key is provided
if HELIUS_API_KEY:
    RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# WebSocket endpoint
WS_URL = "wss://api.mainnet-beta.solana.com"
if HELIUS_API_KEY:
    WS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# ============================================================================
# CONSTANTS
# ============================================================================

# Bags launchpad update authority
BAGS_UPDATE_AUTHORITY = "BAGSB9TpGrZxQbEsrEznv5jXXdwyP6AXerN8aVRiAmcv"

# Metaplex Metadata Program ID (for mint detection)
METADATA_PROGRAM_ID = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"

# Bags API base URL
BAGS_API_BASE = "https://bags.fm/api/token"

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL STATE
# ============================================================================

seen_mints: Set[str] = set()
telegram_bot: Optional[Bot] = None

# Optional: Store royalty data for future reference
royalty_data: Dict[str, Dict] = {}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def clean_twitter_handle(handle: str) -> str:
    """Clean a Twitter handle removing prefixes, URLs, and extracting username"""
    if not handle:
        return ""
    
    # Handle tweet URLs like "@username/status/1234567890"
    if "/status/" in handle:
        handle = handle.split("/status/")[0]
    
    # Clean common prefixes and domains
    cleaned = (handle
             .replace("@", "")
             .replace("https://x.com/", "")
             .replace("https://twitter.com/", "")
             .replace("https://www.x.com/", "")
             .replace("https://www.twitter.com/", "")
             .replace("x.com/", "")
             .replace("twitter.com/", "")
             .strip())
    
    # Remove any remaining path components
    if "/" in cleaned:
        cleaned = cleaned.split("/")[0]
    
    return cleaned

def fetch_bags_token_data(mint_address: str) -> Optional[Dict]:
    """Fetch token data from Bags API"""
    try:
        url = f"{BAGS_API_BASE}/{mint_address}"
        logger.info(f"Fetching token data from Bags API: {url}")
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Successfully fetched token data for {mint_address}")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch token data from Bags API for {mint_address}: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response from Bags API for {mint_address}: {e}")
        return None

def format_telegram_message(mint_address: str, token_data: Dict) -> str:
    """Format the Telegram message using Bags API data"""
    try:
        # Extract data from Bags API response
        name = token_data.get("name", "Unknown Token")
        symbol = token_data.get("symbol", "UNKNOWN")
        image_url = token_data.get("image", "")
        website = token_data.get("website", "")
        royalty_percentage = token_data.get("royaltyPercentage")
        
        # Extract Twitter handles
        created_by = token_data.get("createdBy", {})
        royalties_to = token_data.get("royaltiesTo", {})
        
        creator_twitter = created_by.get("twitter", "") if created_by else ""
        royalty_twitter = royalties_to.get("twitter", "") if royalties_to else ""
        
        # Clean Twitter handles
        creator_clean = clean_twitter_handle(creator_twitter)
        royalty_clean = clean_twitter_handle(royalty_twitter)
        
        # Store royalty data for bonus tracking
        if royalties_to and royalties_to.get("wallet"):
            royalty_data[mint_address] = {
                "creator_twitter": creator_clean,
                "royalty_twitter": royalty_clean,
                "royalty_wallet": royalties_to.get("wallet")
            }
        
        # Build the message
        message = f"""🚀 New Coin Launched on Bags!

Name: {name}
Ticker: {symbol}
Mint: {mint_address}
Solscan: https://solscan.io/token/{mint_address}
"""
        
        # Handle Twitter display logic
        if creator_clean and royalty_clean and creator_clean.lower() != royalty_clean.lower():
            # Different creator and fee recipient
            message += f"\nCreator: @{creator_clean}"
            message += f"\nFee Recipient: @{royalty_clean}"
        elif creator_clean and royalty_clean and creator_clean.lower() == royalty_clean.lower():
            # Same person for both
            message += f"\nTwitter: @{creator_clean}"
        elif creator_clean:
            # Only creator
            message += f"\nCreator: @{creator_clean}"
        elif royalty_clean:
            # Only fee recipient
            message += f"\nFee Recipient: @{royalty_clean}"
        
        # Add royalty percentage if available
        if royalty_percentage is not None:
            message += f"\nRoyalty: {royalty_percentage}%"
        
        # Add website
        message += f"\nWebsite: https://bags.fm/{mint_address}"
        
        return message
        
    except Exception as e:
        logger.error(f"Error formatting message for {mint_address}: {e}")
        # Return a basic fallback message
        return f"""🚀 New Coin Launched on Bags!

Mint: {mint_address}
Solscan: https://solscan.io/token/{mint_address}
Website: https://bags.fm/{mint_address}

(Error fetching full details)"""

async def send_telegram_message(mint_address: str, token_data: Dict):
    """Send formatted message to Telegram channel"""
    try:
        message = format_telegram_message(mint_address, token_data)
        image_url = token_data.get("image", "")
        
        if image_url:
            # Try to send with image
            try:
                await telegram_bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=image_url,
                    caption=message
                )
                logger.info(f"Sent token update with image for {mint_address}")
                return
            except Exception as e:
                logger.warning(f"Failed to send image for {mint_address}: {e}")
        
        # Send as text message
        await telegram_bot.send_message(
            chat_id=CHANNEL_ID,
            text=message,
            disable_web_page_preview=False
        )
        logger.info(f"Sent token update for {mint_address}")
        
    except Exception as e:
        logger.error(f"Error sending Telegram message for {mint_address}: {e}")
        
        # Emergency fallback message
        try:
            fallback = f"🚀 NEW BAGS TOKEN: {mint_address}\nhttps://bags.fm/{mint_address}"
            await telegram_bot.send_message(
                chat_id=CHANNEL_ID,
                text=fallback
            )
            logger.info(f"Sent fallback message for {mint_address}")
        except Exception as fallback_error:
            logger.error(f"Failed to send fallback message: {fallback_error}")

# ============================================================================
# TOKEN PROCESSING
# ============================================================================

async def process_new_token(mint_address: str):
    """Process a newly detected token using Bags API"""
    try:
        if mint_address in seen_mints:
            return
        
        logger.info(f"Processing new token: {mint_address}")
        seen_mints.add(mint_address)
        
        # Fetch token data from Bags API
        token_data = fetch_bags_token_data(mint_address)
        
        if token_data:
            # Send Telegram message with Bags API data
            await send_telegram_message(mint_address, token_data)
        else:
            # Fallback if Bags API fails
            logger.warning(f"Bags API failed for {mint_address}, sending basic notification")
            fallback_message = f"""🚀 New Coin Launched on Bags!

Mint: {mint_address}
Solscan: https://solscan.io/token/{mint_address}
Website: https://bags.fm/{mint_address}

⚠️ Full details temporarily unavailable"""
            
            await telegram_bot.send_message(
                chat_id=CHANNEL_ID,
                text=fallback_message
            )
            logger.info(f"Sent fallback notification for {mint_address}")
        
    except Exception as e:
        logger.error(f"Error processing token {mint_address}: {e}")

# ============================================================================
# MINT DETECTION
# ============================================================================

async def check_transaction_for_token_creation(signature: str):
    """Check a specific transaction for token creation"""
    try:
        # Get transaction details
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                signature,
                {
                    "encoding": "json",
                    "commitment": "confirmed",
                    "maxSupportedTransactionVersion": 0
                }
            ]
        }
        
        response = requests.post(RPC_URL, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            transaction_data = result.get("result")
            
            if transaction_data and transaction_data.get("meta", {}).get("err") is None:
                # Transaction was successful
                logs = transaction_data.get("meta", {}).get("logMessages", [])
                account_keys = transaction_data.get("transaction", {}).get("message", {}).get("accountKeys", [])
                
                # Check if this involves metadata creation and Bags authority
                metadata_creation = any("CreateMetadataAccount" in log or "metaq" in log.lower() for log in logs)
                bags_involved = BAGS_UPDATE_AUTHORITY in account_keys
                
                if metadata_creation and bags_involved:
                    logger.info(f"🎯 BAGS TOKEN CREATION: {signature}")
                    
                    # Look for potential mint address
                    for account in account_keys:
                        if (account != METADATA_PROGRAM_ID and 
                            account != BAGS_UPDATE_AUTHORITY and 
                            len(account) >= 44):
                            logger.info(f"🚀 POTENTIAL BAGS TOKEN FOUND: {account}")
                            await process_new_token(account)
                            break
        
    except Exception as e:
        logger.error(f"Error checking transaction {signature}: {e}")

async def monitor_websocket():
    """Monitor WebSocket for new transactions"""
    while True:
        try:
            logger.info("Connecting to WebSocket...")
            async with websockets.connect(WS_URL) as websocket:
                logger.info("WebSocket connected")
                
                # Subscribe to logs for Bags update authority
                subscribe_message = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "logsSubscribe",
                    "params": [
                        {
                            "mentions": [BAGS_UPDATE_AUTHORITY]
                        },
                        {
                            "commitment": "confirmed"
                        }
                    ]
                }
                
                await websocket.send(json.dumps(subscribe_message))
                logger.info("Subscribed to Bags update authority transactions")
                
                # Listen for messages
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        
                        # Handle subscription confirmation
                        if "id" in data and "result" in data:
                            logger.info(f"Subscription confirmed: {data['result']}")
                            continue
                        
                        # Handle log notifications
                        if "method" in data and data["method"] == "logsNotification":
                            params = data.get("params", {})
                            result = params.get("result", {})
                            
                            # Get signature
                            signature = result.get("signature")
                            if signature:
                                logger.info(f"🔍 New Bags transaction: {signature}")
                                await check_transaction_for_token_creation(signature)
                        
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
                        
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            logger.info("Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

async def monitor_polling():
    """Backup polling method for detecting new transactions"""
    last_signature = None
    
    while True:
        try:
            # Get recent signatures from Bags deployer
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [BAGS_UPDATE_AUTHORITY, {"limit": 3}]
            }
            
            response = requests.post(RPC_URL, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                signatures = result.get("result", [])
                
                if signatures and signatures[0].get("signature") != last_signature:
                    new_signature = signatures[0].get("signature")
                    logger.info(f"🔍 POLLING: New Bags transaction: {new_signature}")
                    last_signature = new_signature
                    
                    await check_transaction_for_token_creation(new_signature)
            
        except Exception as e:
            logger.debug(f"Error polling transactions: {e}")
        
        # Poll every 30 seconds (WebSocket should catch most, this is backup)
        await asyncio.sleep(30)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

async def main():
    """Main application entry point"""
    global telegram_bot
    
    # Validate configuration
    if not TELEGRAM_TOKEN:
        logger.error("Please set TELEGRAM_TOKEN environment variable")
        return
    
    if not CHANNEL_ID:
        logger.error("Please set CHANNEL_ID environment variable")
        return
    
    # Initialize Telegram bot
    telegram_bot = Bot(token=TELEGRAM_TOKEN)
    
    logger.info("Starting Bags Launchpad Telegram Bot (Upgraded)...")
    logger.info(f"Monitoring for tokens from deployer: {BAGS_UPDATE_AUTHORITY}")
    logger.info(f"Using Bags API: {BAGS_API_BASE}")
    
    # Test Telegram connection
    try:
        bot_info = await telegram_bot.get_me()
        logger.info(f"Bot connected: @{bot_info.username}")
        
        # Send startup message
        startup_message = "🤖 BagWatch Bot is online and monitoring Bags launchpad (Upgraded Version)!"
        await telegram_bot.send_message(
            chat_id=CHANNEL_ID,
            text=startup_message
        )
        logger.info("✅ Telegram connection test successful!")
        
    except Exception as e:
        logger.error(f"Failed to connect to Telegram: {e}")
        return
    
    # Start monitoring tasks
    logger.info("Starting monitoring services...")
    
    # Create tasks for both WebSocket and polling
    websocket_task = asyncio.create_task(monitor_websocket())
    polling_task = asyncio.create_task(monitor_polling())
    
    try:
        # Run both monitoring methods concurrently
        await asyncio.gather(websocket_task, polling_task)
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
