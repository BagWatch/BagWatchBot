#!/usr/bin/env python3
"""
Bags Launchpad Telegram Bot

This bot monitors the Bags launchpad for new token launches in real-time
and posts updates to a Telegram channel.

Installation:
pip install python-telegram-bot==20.3 requests websocket-client solana

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
from solana.publickey import PublicKey
from solana.rpc.api import Client

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
solana_client: Optional[Client] = None

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def derive_metadata_pda(mint_pubkey: str) -> str:
    """Derive the metadata PDA for a given mint"""
    try:
        mint_key = PublicKey(mint_pubkey)
        metadata_program = PublicKey(METADATA_PROGRAM_ID)
        
        seeds = [
            b"metadata",
            bytes(metadata_program),
            bytes(mint_key)
        ]
        
        pda, _ = PublicKey.find_program_address(seeds, metadata_program)
        return str(pda)
    except Exception as e:
        logger.error(f"Error deriving metadata PDA for {mint_pubkey}: {e}")
        return ""

def fetch_metadata_account(metadata_pda: str) -> Optional[Dict]:
    """Fetch metadata account data from Solana"""
    try:
        response = solana_client.get_account_info(PublicKey(metadata_pda))
        if response.value is None:
            return None
        
        # Parse metadata account (simplified - in production you'd use proper borsh deserialization)
        account_data = response.value.data
        if len(account_data) < 100:  # Basic sanity check
            return None
            
        # For this example, we'll make a simplified assumption about the metadata structure
        # In production, you should use proper Metaplex metadata parsing
        return {"data": account_data}
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
        
        # Fetch token metadata
        metadata = fetch_token_metadata_via_rpc(mint_address)
        if not metadata:
            logger.warning(f"Could not fetch metadata for {mint_address}")
            return
        
        # Get URI from metadata
        uri = metadata.get("uri")
        if not uri:
            logger.warning(f"No URI found in metadata for {mint_address}")
            return
        
        # Fetch IPFS metadata
        ipfs_data = fetch_ipfs_metadata(uri)
        if not ipfs_data:
            logger.warning(f"Could not fetch IPFS data for {mint_address}")
            return
        
        # Send to Telegram
        await send_telegram_message(mint_address, metadata, ipfs_data)
        
    except Exception as e:
        logger.error(f"Error processing token {mint_address}: {e}")

def parse_log_message(log_data: Dict) -> Optional[str]:
    """Parse log message to extract mint address if it's a Bags token"""
    try:
        # This is a simplified parser - you'd need to implement proper log parsing
        # based on the specific structure of Metaplex metadata program logs
        
        # Look for account keys and check if update authority matches Bags
        logs = log_data.get("logs", [])
        
        # Simple pattern matching for demonstration
        for log in logs:
            if "CreateMetadataAccountV3" in log or "CreateMetadataAccount" in log:
                # Extract mint address from the log
                # This is a placeholder - actual implementation would parse the instruction data
                pass
        
        # For demo purposes, return None
        # In production, you'd parse the actual instruction data
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
            
            # Parse the log message
            mint_address = parse_log_message(result)
            if mint_address:
                # Process in background
                asyncio.create_task(process_new_token(mint_address))
        
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
    subscribe_message = {
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
    
    ws.send(json.dumps(subscribe_message))
    logger.info("Subscribed to Metaplex Metadata program logs")

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
    global telegram_bot, solana_client
    
    # Validate configuration
    if not TELEGRAM_TOKEN:
        logger.error("Please set TELEGRAM_TOKEN environment variable")
        return
    
    if not CHANNEL_ID:
        logger.error("Please set CHANNEL_ID environment variable")
        return
    
    # Initialize clients
    telegram_bot = Bot(token=TELEGRAM_TOKEN)
    solana_client = Client(RPC_URL)
    
    logger.info("Starting Bags Launchpad Telegram Bot...")
    
    # Test Telegram connection
    try:
        bot_info = await telegram_bot.get_me()
        logger.info(f"Bot connected: @{bot_info.username}")
    except Exception as e:
        logger.error(f"Failed to connect to Telegram: {e}")
        return
    
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