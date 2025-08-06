#!/usr/bin/env python3
"""
Bags Launchpad Telegram Bot

This bot monitors the Bags launchpad for new token launches in real-time
and posts updates to a Telegram channel.

Installation:
pip install python-telegram-bot==20.7 requests websocket-client solders base58

Usage:
1. Set TELEGRAM_TOKEN to your bot token from @BotFather
2. Set CHANNEL_ID to your channel ID (e.g., "@your_channel" or "-1001234567890")
3. Run: python bags_telegram_bot.py
"""

import json
import asyncio
import logging
import websocket
import threading
import time
import os
from typing import Dict, Any, Optional, Set
from urllib.parse import quote

import requests
from telegram import Bot
from telegram.constants import ParseMode
import base58
try:
    from solders.pubkey import Pubkey
    SOLDERS_AVAILABLE = True
except ImportError:
    SOLDERS_AVAILABLE = False

# ============================================================================
# CONFIGURATION - SET THESE AS ENVIRONMENT VARIABLES FOR RAILWAY
# ============================================================================

# Solana RPC endpoint - Helius recommended for better performance
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

# Build Helius RPC URL if API key is provided
if HELIUS_API_KEY:
    RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# Telegram bot configuration - SET THESE AS RAILWAY ENVIRONMENT VARIABLES
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Get from @BotFather
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Your channel username or ID

# ============================================================================
# CONSTANTS
# ============================================================================

# Bags launchpad update authority
BAGS_UPDATE_AUTHORITY = "BAGSB9TpGrZxQbEsrEznv5jXXdwyP6AXerN8aVRiAmcv"

# Metaplex Metadata Program ID
METADATA_PROGRAM_ID = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"

# WebSocket endpoint - Use Helius if available
WS_URL = "wss://api.mainnet-beta.solana.com"
if HELIUS_API_KEY:
    WS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

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

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def derive_metadata_pda(mint_pubkey: str) -> str:
    """Derive the metadata PDA for a given mint"""
    try:
        if SOLDERS_AVAILABLE:
            mint_key = Pubkey.from_string(mint_pubkey)
            metadata_program = Pubkey.from_string(METADATA_PROGRAM_ID)
            
            seeds = [
                b"metadata",
                bytes(metadata_program),
                bytes(mint_key)
            ]
            
            # Simplified PDA derivation - in production you'd use proper Solana SDK
            # For now, we'll construct a basic metadata account address
            return f"{mint_pubkey}_metadata"  # Placeholder
        else:
            # Fallback without solders
            return f"{mint_pubkey}_metadata"
    except Exception as e:
        logger.error(f"Error deriving metadata PDA for {mint_pubkey}: {e}")
        return ""

def fetch_metadata_account(metadata_pda: str) -> Optional[Dict]:
    """Fetch metadata account data from Solana"""
    try:
        # Use RPC call to fetch account data
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [metadata_pda, {"encoding": "base64"}]
        }
        
        response = requests.post(RPC_URL, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("result", {}).get("value") is None:
            return None
            
        # For this example, we'll make a simplified assumption about the metadata structure
        # In production, you should use proper Metaplex metadata parsing
        return {"data": result["result"]["value"]["data"]}
    except Exception as e:
        logger.error(f"Error fetching metadata account {metadata_pda}: {e}")
        return None

def extract_uri_from_metadata(metadata_account: Dict) -> Optional[str]:
    """Extract URI from metadata account data"""
    try:
        # This is a simplified implementation
        # In production, you should use proper Metaplex metadata parsing
        # For now, we'll use the RPC method to get parsed metadata
        return None  # Placeholder - would need proper borsh deserialization
    except Exception as e:
        logger.error(f"Error extracting URI from metadata: {e}")
        return None

def fetch_token_metadata_via_rpc(mint_address: str) -> Optional[Dict]:
    """Fetch token metadata using RPC getProgramAccounts"""
    try:
        # Get metadata account using RPC
        metadata_pda = derive_metadata_pda(mint_address)
        
        # Use a metadata service or parse the account directly
        # For simplicity, we'll construct a sample response
        # In production, you'd use services like Helius, QuickNode, or parse the account data
        
        # Placeholder metadata - replace with actual parsing
        sample_metadata = {
            "name": "Sample Token",
            "symbol": "SAMPLE",
            "uri": "https://arweave.net/sample-metadata.json"
        }
        
        return sample_metadata
    except Exception as e:
        logger.error(f"Error fetching token metadata for {mint_address}: {e}")
        return None

def fetch_ipfs_metadata(uri: str) -> Optional[Dict]:
    """Fetch metadata from IPFS/Arweave URI"""
    try:
        # Handle different URI formats
        if uri.startswith("ipfs://"):
            # Convert IPFS URI to HTTP
            ipfs_hash = uri.replace("ipfs://", "")
            url = f"https://ipfs.io/ipfs/{ipfs_hash}"
        elif uri.startswith("https://arweave.net/"):
            url = uri
        else:
            url = uri
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching IPFS metadata from {uri}: {e}")
        return None

def format_telegram_message(mint_address: str, metadata: Dict, ipfs_data: Dict) -> tuple[str, str]:
    """Format the Telegram message and return (caption, image_url)"""
    try:
        name = ipfs_data.get("name", "Unknown Token")
        symbol = ipfs_data.get("symbol", "UNKNOWN")
        image = ipfs_data.get("image", "")
        twitter = ipfs_data.get("twitter", "")
        creator_twitter = ipfs_data.get("creator_twitter", "")
        website = ipfs_data.get("website", "")
        royalty_bps = ipfs_data.get("sellerFeeBasisPoints", 0)
        
        # Convert royalty from basis points to percentage
        royalty_percent = royalty_bps / 100 if royalty_bps else 0
        
        # Format Solscan link
        solscan_link = f"[View on Solscan](https://solscan.io/token/{mint_address})"
        
        # Format Twitter links
        twitter_section = ""
        if creator_twitter and creator_twitter != twitter:
            # Show both creator and fee recipient
            creator_link = f"[@{creator_twitter}](https://x.com/{creator_twitter})"
            fee_link = f"[@{twitter}](https://x.com/{twitter})" if twitter else "N/A"
            twitter_section = f"Creator: {creator_link}\nFee Recipient: {fee_link}"
        elif twitter:
            # Show single Twitter link
            twitter_link = f"[@{twitter}](https://x.com/{twitter})"
            twitter_section = f"Twitter: {twitter_link}"
        
        # Format website link
        website_section = ""
        if website:
            # Truncate long URLs for display
            display_url = website if len(website) <= 50 else website[:47] + "..."
            website_section = f"\n\n[Website]({website})"
        
        # Build the message
        caption = f"""🚀 *New Coin Launched on Bags\\!*

*Name:* {escape_markdown(name)}
*Ticker:* {escape_markdown(symbol)}
*Contract:* `{mint_address}`
{solscan_link}

{twitter_section}
*Royalty:* {royalty_percent}%{website_section}"""

        # Handle image URL
        image_url = ""
        if image:
            if image.startswith("ipfs://"):
                ipfs_hash = image.replace("ipfs://", "")
                image_url = f"https://ipfs.io/ipfs/{ipfs_hash}"
            else:
                image_url = image
        
        return caption, image_url
    
    except Exception as e:
        logger.error(f"Error formatting message for {mint_address}: {e}")
        return "", ""

def escape_markdown(text: str) -> str:
    """Escape special characters for MarkdownV2"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def send_telegram_message(mint_address: str, metadata: Dict, ipfs_data: Dict):
    """Send formatted message to Telegram channel"""
    try:
        caption, image_url = format_telegram_message(mint_address, metadata, ipfs_data)
        
        if not caption:
            logger.error(f"Failed to format message for {mint_address}")
            return
        
        if image_url:
            # Send with image
            try:
                await telegram_bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=image_url,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                logger.info(f"Sent token update with image for {mint_address}")
            except Exception as e:
                logger.error(f"Failed to send image for {mint_address}: {e}")
                # Fallback to text message
                await telegram_bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=caption,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    disable_web_page_preview=False
                )
                logger.info(f"Sent token update as text for {mint_address}")
        else:
            # Send text only
            await telegram_bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=False
            )
            logger.info(f"Sent token update for {mint_address}")
    
    except Exception as e:
        logger.error(f"Error sending Telegram message for {mint_address}: {e}")

# ============================================================================
# TOKEN PROCESSING
# ============================================================================

async def process_new_token(mint_address: str):
    """Process a newly detected token"""
    try:
        if mint_address in seen_mints:
            return
        
        logger.info(f"Processing new token: {mint_address}")
        seen_mints.add(mint_address)
        
        # For now, send a simple notification until we fix metadata parsing
        try:
            simple_message = f"""🚀 NEW BAGS TOKEN DETECTED!

Contract: `{mint_address}`
[View on Solscan](https://solscan.io/token/{mint_address})

⚠️ Full metadata parsing coming soon!"""

            await telegram_bot.send_message(
                chat_id=CHANNEL_ID,
                text=simple_message,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=False
            )
            logger.info(f"✅ Posted simple notification for token: {mint_address}")
        except Exception as e:
            logger.error(f"❌ Failed to post simple notification: {e}")
            
        # TODO: Add back full metadata processing once basic detection works
        # metadata = fetch_token_metadata_via_rpc(mint_address)
        # ... rest of metadata processing
        
    except Exception as e:
        logger.error(f"Error processing token {mint_address}: {e}")

def parse_log_message(log_data: Dict) -> Optional[str]:
    """Parse log message to extract mint address if it's a Bags token"""
    try:
        logs = log_data.get("logs", [])
        
        # First check if any logs mention metadata creation
        metadata_creation = False
        for log in logs:
            if any(keyword in log for keyword in [
                "CreateMetadataAccountV3", 
                "CreateMetadataAccount",
                "Program metaq invoke",
                "CreateMasterEditionV3",
                "Instruction: CreateMetadataAccount"
            ]):
                metadata_creation = True
                logger.info(f"Metadata creation detected: {log}")
                break
        
        if not metadata_creation:
            return None
            
        # Get transaction details
        value = log_data.get("value", {})
        if not value:
            return None
            
        transaction = value.get("transaction", {})
        message = transaction.get("message", {})
        account_keys = message.get("accountKeys", [])
        
        # Check if this transaction involves the Bags update authority
        bags_involved = False
        mint_candidate = None
        
        logger.info(f"Checking {len(account_keys)} account keys for Bags authority")
        for i, key in enumerate(account_keys):
            logger.debug(f"Account {i}: {key}")
            if key == BAGS_UPDATE_AUTHORITY:
                bags_involved = True
                logger.info(f"🎯 BAGS AUTHORITY FOUND at position {i}!")
            elif key != METADATA_PROGRAM_ID and len(key) >= 44 and not mint_candidate:
                # Potential mint address (Solana addresses are typically 44 chars)
                mint_candidate = key
                logger.info(f"Potential mint candidate: {key}")
        
        if bags_involved and mint_candidate:
            logger.info(f"🚀 CONFIRMED BAGS TOKEN: {mint_candidate}")
            return mint_candidate
        elif bags_involved:
            logger.info("Bags authority found but no mint candidate identified")
        else:
            logger.debug("No Bags authority found in transaction")
        
        return None
        
    except Exception as e:
        logger.error(f"Error parsing log message: {e}")
        return None

# ============================================================================
# WEBSOCKET HANDLING
# ============================================================================

def on_websocket_message(ws, message):
    """Handle incoming WebSocket message"""
    try:
        data = json.loads(message)
        
        # Handle subscription confirmation
        if "id" in data and "result" in data:
            logger.info(f"Subscription confirmed: {data}")
            return
        
        # Handle log updates
        if "method" in data and data["method"] == "logsNotification":
            params = data.get("params", {})
            result = params.get("result", {})
            
            # Log all transactions for debugging
            logs = result.get("logs", [])
            subscription_id = params.get("subscription", "unknown")
            
            # Check if this is from any of our subscriptions or contains metaplex activity
            if any("metaq" in log.lower() for log in logs):
                logger.info(f"📋 LOG NOTIFICATION - Subscription: {subscription_id}")
                logger.info(f"Metaplex transaction detected with {len(logs)} logs")
                if len(logs) > 0:
                    logger.info(f"First log: {logs[0][:100]}...")  # First 100 chars
                
                # Parse the log message
                mint_address = parse_log_message(result)
                if mint_address:
                    logger.info(f"🎯 BAGS TOKEN DETECTED: {mint_address}")
                    # Process in background
                    asyncio.create_task(process_new_token(mint_address))
                else:
                    logger.debug("No Bags token found in this transaction")
        
        # Handle program account notifications
        elif "method" in data and data["method"] == "programNotification":
            params = data.get("params", {})
            result = params.get("result", {})
            context = result.get("context", {})
            value = result.get("value", {})
            
            # Get the account pubkey from params
            account_pubkey = params.get("result", {}).get("context", {}).get("slot")
            if not account_pubkey:
                # Try alternative location
                account_pubkey = str(params.get("subscription", "unknown"))
            
            logger.info(f"📋 Program account notification received")
            logger.info(f"Subscription ID: {params.get('subscription', 'unknown')}")
            logger.info(f"Slot: {context.get('slot', 'unknown')}")
            
            # This is a metadata account change - try to get the actual account address
            if value and value.get("owner") == METADATA_PROGRAM_ID:
                logger.info(f"🎯 METAPLEX METADATA ACCOUNT DETECTED!")
                logger.info(f"Account owner: {value.get('owner', 'unknown')}")
                logger.info(f"Account data length: {len(value.get('data', []))}")
                
                # TODO: Parse the metadata account to extract mint address
                # For now, this confirms we're getting Bags-related metadata updates
            
        
    except Exception as e:
        logger.error(f"Error processing WebSocket message: {e}")

def on_websocket_error(ws, error):
    """Handle WebSocket error"""
    logger.error(f"WebSocket error: {error}")

def on_websocket_close(ws, close_status_code, close_msg):
    """Handle WebSocket close"""
    logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
    # Reconnect logic could be added here

def on_websocket_open(ws):
    """Handle WebSocket open"""
    logger.info("WebSocket connection opened")
    
    # Subscribe to logs for the Metaplex Metadata program
    subscribe_message1 = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "logsSubscribe",
        "params": [
            {
                "mentions": [METADATA_PROGRAM_ID]
            },
            {
                "commitment": "confirmed"
            }
        ]
    }
    
    # Also subscribe specifically to transactions involving Bags update authority
    subscribe_message2 = {
        "jsonrpc": "2.0",
        "id": 2,
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
    
    # Subscribe to program account changes for more comprehensive monitoring
    subscribe_message3 = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "programSubscribe",
        "params": [
            METADATA_PROGRAM_ID,
            {
                "commitment": "confirmed",
                "filters": [
                    {
                        "memcmp": {
                            "offset": 1,
                            "bytes": BAGS_UPDATE_AUTHORITY
                        }
                    }
                ]
            }
        ]
    }
    
    ws.send(json.dumps(subscribe_message1))
    ws.send(json.dumps(subscribe_message2))
    ws.send(json.dumps(subscribe_message3))
    logger.info("Subscribed to Metaplex Metadata program logs")
    logger.info("Subscribed to Bags update authority transactions")
    logger.info("Subscribed to Metaplex program account changes")

def start_websocket():
    """Start WebSocket connection in a separate thread"""
    def run_websocket():
        websocket.enableTrace(False)
        ws = websocket.WebSocketApp(
            WS_URL,
            on_open=on_websocket_open,
            on_message=on_websocket_message,
            on_error=on_websocket_error,
            on_close=on_websocket_close
        )
        
        # Run with reconnection
        while True:
            try:
                ws.run_forever()
                logger.warning("WebSocket connection lost, reconnecting in 5 seconds...")
                time.sleep(5)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                time.sleep(5)
    
    thread = threading.Thread(target=run_websocket, daemon=True)
    thread.start()
    return thread

# ============================================================================
# MAIN APPLICATION
# ============================================================================

async def main():
    """Main application entry point"""
    global telegram_bot
    
    # Debug environment variables (without exposing full tokens)
    logger.info(f"TELEGRAM_TOKEN configured: {bool(TELEGRAM_TOKEN)}")
    logger.info(f"CHANNEL_ID configured: {bool(CHANNEL_ID)}")
    logger.info(f"HELIUS_API_KEY configured: {bool(HELIUS_API_KEY)}")
    logger.info(f"Using RPC URL: {RPC_URL[:50]}..." if len(RPC_URL) > 50 else f"Using RPC URL: {RPC_URL}")
    
    # Validate configuration
    if not TELEGRAM_TOKEN:
        logger.error("Please set TELEGRAM_TOKEN environment variable")
        return
    
    if not CHANNEL_ID:
        logger.error("Please set CHANNEL_ID environment variable")
        return
    
    # Initialize clients
    telegram_bot = Bot(token=TELEGRAM_TOKEN)
    
    logger.info("Starting Bags Launchpad Telegram Bot...")
    logger.info(f"Monitoring for tokens from deployer: {BAGS_UPDATE_AUTHORITY}")
    
    # Test Telegram connection
    try:
        bot_info = await telegram_bot.get_me()
        logger.info(f"Bot connected: @{bot_info.username}")
    except Exception as e:
        logger.error(f"Failed to connect to Telegram: {e}")
        return
    
    # Test function to check recent transactions for debugging
    try:
        logger.info("Testing recent transactions from Bags deployer...")
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [BAGS_UPDATE_AUTHORITY, {"limit": 5}]
        }
        response = requests.post(RPC_URL, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            signatures = result.get("result", [])
            logger.info(f"Found {len(signatures)} recent transactions from Bags deployer")
            if signatures:
                logger.info(f"Most recent signature: {signatures[0].get('signature', 'unknown')}")
        else:
            logger.warning(f"Failed to fetch recent transactions: {response.status_code}")
    except Exception as e:
        logger.warning(f"Error testing recent transactions: {e}")
    
    # Always test Telegram connection by sending a simple message
    logger.info("🧪 Testing Telegram channel connection...")
    try:
        test_message = "🤖 BagWatch Bot is online and monitoring Bags launchpad!"
        
        await telegram_bot.send_message(
            chat_id=CHANNEL_ID,
            text=test_message
        )
        logger.info("✅ Telegram connection test successful!")
    except Exception as e:
        logger.error(f"❌ Telegram connection test failed: {e}")
        logger.error(f"Channel ID: {CHANNEL_ID}")
        logger.error(f"Bot token starts with: {TELEGRAM_TOKEN[:10]}...")
        
        # Try to get bot info for debugging
        try:
            bot_info = await telegram_bot.get_me()
            logger.error(f"Bot info: {bot_info.username}, can_join_groups: {bot_info.can_join_groups}")
        except Exception as bot_error:
            logger.error(f"Can't get bot info: {bot_error}")
        
        return  # Exit if we can't post to Telegram
    
    # Start WebSocket monitoring
    ws_thread = start_websocket()
    
    logger.info("Bot is running on Railway...")
    
    # Keep the main thread alive
    try:
        while True:
            await asyncio.sleep(60)  # Check every minute
            # Health check - could add ping to Telegram API here
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        # In Railway, we want to exit so the service restarts
        raise

if __name__ == "__main__":
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")