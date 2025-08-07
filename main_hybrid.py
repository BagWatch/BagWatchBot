#!/usr/bin/env python3
"""
Bags Launchpad Telegram Bot - Hybrid Version

This bot monitors the Bags launchpad for new token launches using:
1. WebSocket detection for new mints from Bags deployer
2. Web scraping from Bags token pages for enhanced metadata
3. RPC fallback for basic metadata when scraping fails

The best of both worlds - reliable detection + rich Bags data when available.
"""

import json
import asyncio
import logging
import time
import os
import re
from typing import Dict, Any, Optional, Set
import requests
from telegram import Bot
from telegram.constants import ParseMode
import websockets
from bs4 import BeautifulSoup

# ============================================================================
# CONFIGURATION
# ============================================================================

# Telegram bot configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Solana RPC endpoint - only used for mint detection
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")

if HELIUS_API_KEY:
    RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# WebSocket endpoint
WS_URL = "wss://api.mainnet-beta.solana.com"
if HELIUS_API_KEY:
    WS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# ============================================================================
# CONSTANTS
# ============================================================================

BAGS_UPDATE_AUTHORITY = "BAGSB9TpGrZxQbEsrEznv5jXXdwyP6AXerN8aVRiAmcv"
METADATA_PROGRAM_ID = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"

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
royalty_data: Dict[str, Dict] = {}

# ============================================================================
# BAGS WEB SCRAPING
# ============================================================================

def scrape_bags_token_page(mint_address: str) -> Optional[Dict]:
    """Scrape token data from Bags.fm token page"""
    try:
        url = f"https://bags.fm/{mint_address}"
        logger.info(f"Scraping Bags page: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Try to extract JSON data from the page
        html_content = response.text
        
        # Look for potential JSON data in script tags or meta tags
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try to find the title which often contains the token name
        title_tag = soup.find('title')
        title_text = title_tag.text if title_tag else ""
        
        # Extract token name from title (format might be "TokenName on Bags" or similar)
        token_name = "Unknown Token"
        if title_tag and "on Bags" in title_text:
            token_name = title_text.replace(" on Bags", "").strip()
        elif title_tag and "Token on Bags" in title_text:
            token_name = title_text.replace("Token on Bags", "").strip()
        
        # Look for metadata in the HTML
        metadata = {
            "name": token_name,
            "symbol": "UNKNOWN",
            "image": None,
            "website": None,
            "createdBy": {"twitter": None},
            "royaltiesTo": {"twitter": None},
            "royaltyPercentage": None
        }
        
        # Try to find Open Graph or Twitter meta tags
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            metadata["name"] = og_title.get('content')
        
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            metadata["image"] = og_image.get('content')
        
        # Look for Twitter links in the HTML
        twitter_links = soup.find_all('a', href=re.compile(r'(twitter\.com|x\.com)'))
        twitter_handles = []
        
        for link in twitter_links:
            href = link.get('href', '')
            # Extract Twitter handle from URL
            match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', href)
            if match:
                handle = match.group(1)
                if handle not in ['intent', 'share'] and not handle.startswith('intent'):
                    twitter_handles.append(handle)
        
        # Assign Twitter handles (first one as creator, second as royalty recipient if different)
        if twitter_handles:
            metadata["createdBy"]["twitter"] = twitter_handles[0]
            if len(twitter_handles) > 1 and twitter_handles[1] != twitter_handles[0]:
                metadata["royaltiesTo"]["twitter"] = twitter_handles[1]
            else:
                metadata["royaltiesTo"]["twitter"] = twitter_handles[0]
        
        logger.info(f"Scraped data for {mint_address}: {metadata}")
        return metadata
        
    except Exception as e:
        logger.error(f"Failed to scrape Bags page for {mint_address}: {e}")
        return None

# ============================================================================
# RPC METADATA FALLBACK
# ============================================================================

def fetch_rpc_metadata(mint_address: str) -> Optional[Dict]:
    """Fetch basic metadata using Helius/RPC as fallback"""
    try:
        logger.info(f"Fetching RPC metadata for {mint_address}")
        
        # Try Helius getAsset first
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAsset",
            "params": {"id": mint_address}
        }
        
        response = requests.post(RPC_URL, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json().get("result", {})
            if result:
                content = result.get("content", {})
                metadata = content.get("metadata", {})
                
                return {
                    "name": metadata.get("name", "Unknown Token"),
                    "symbol": metadata.get("symbol", "UNKNOWN"),
                    "image": None,
                    "website": None,
                    "createdBy": {"twitter": None},
                    "royaltiesTo": {"twitter": None},
                    "royaltyPercentage": None
                }
        
        return None
        
    except Exception as e:
        logger.error(f"RPC metadata fetch failed for {mint_address}: {e}")
        return None

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def clean_twitter_handle(handle: str) -> str:
    """Clean a Twitter handle removing prefixes, URLs, and extracting username"""
    if not handle:
        return ""
    
    # Handle tweet URLs
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

def format_telegram_message(mint_address: str, token_data: Dict) -> str:
    """Format the Telegram message using token data"""
    try:
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
        
        # Build the message
        message = f"""🚀 New Coin Launched on Bags!

Name: {name}
Ticker: {symbol}
Mint: {mint_address}
Solscan: https://solscan.io/token/{mint_address}
"""
        
        # Handle Twitter display logic
        if creator_clean and royalty_clean and creator_clean.lower() != royalty_clean.lower():
            message += f"\nCreator: @{creator_clean}"
            message += f"\nFee Recipient: @{royalty_clean}"
        elif creator_clean and royalty_clean and creator_clean.lower() == royalty_clean.lower():
            message += f"\nTwitter: @{creator_clean}"
        elif creator_clean:
            message += f"\nCreator: @{creator_clean}"
        elif royalty_clean:
            message += f"\nFee Recipient: @{royalty_clean}"
        
        # Add royalty percentage if available
        if royalty_percentage is not None:
            message += f"\nRoyalty: {royalty_percentage}%"
        
        # Add website
        message += f"\nWebsite: https://bags.fm/{mint_address}"
        
        return message
        
    except Exception as e:
        logger.error(f"Error formatting message for {mint_address}: {e}")
        return f"""🚀 New Coin Launched on Bags!

Mint: {mint_address}
Solscan: https://solscan.io/token/{mint_address}
Website: https://bags.fm/{mint_address}

(Error fetching details)"""

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

# ============================================================================
# TOKEN PROCESSING
# ============================================================================

async def process_new_token(mint_address: str):
    """Process a newly detected token using hybrid approach"""
    try:
        if mint_address in seen_mints:
            return
        
        logger.info(f"Processing new token: {mint_address}")
        seen_mints.add(mint_address)
        
        # Try Bags web scraping first
        token_data = scrape_bags_token_page(mint_address)
        
        # If scraping fails, fall back to RPC metadata
        if not token_data:
            logger.info(f"Bags scraping failed for {mint_address}, trying RPC fallback")
            token_data = fetch_rpc_metadata(mint_address)
        
        # If both fail, create minimal data
        if not token_data:
            logger.warning(f"All metadata methods failed for {mint_address}, using minimal data")
            token_data = {
                "name": "Unknown Token",
                "symbol": "UNKNOWN",
                "image": None,
                "website": None,
                "createdBy": {"twitter": None},
                "royaltiesTo": {"twitter": None},
                "royaltyPercentage": None
            }
        
        # Send Telegram message
        await send_telegram_message(mint_address, token_data)
        
    except Exception as e:
        logger.error(f"Error processing token {mint_address}: {e}")

# ============================================================================
# MINT DETECTION (Same as before)
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
                logs = transaction_data.get("meta", {}).get("logMessages", [])
                account_keys = transaction_data.get("transaction", {}).get("message", {}).get("accountKeys", [])
                
                metadata_creation = any("CreateMetadataAccount" in log or "metaq" in log.lower() for log in logs)
                bags_involved = BAGS_UPDATE_AUTHORITY in account_keys
                
                if metadata_creation and bags_involved:
                    logger.info(f"🎯 BAGS TOKEN CREATION: {signature}")
                    
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
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        
                        if "id" in data and "result" in data:
                            logger.info(f"Subscription confirmed: {data['result']}")
                            continue
                        
                        if "method" in data and data["method"] == "logsNotification":
                            params = data.get("params", {})
                            result = params.get("result", {})
                            
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
    """Backup polling method"""
    last_signature = None
    
    while True:
        try:
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
        
        await asyncio.sleep(30)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

async def main():
    """Main application entry point"""
    global telegram_bot
    
    if not TELEGRAM_TOKEN:
        logger.error("Please set TELEGRAM_TOKEN environment variable")
        return
    
    if not CHANNEL_ID:
        logger.error("Please set CHANNEL_ID environment variable")
        return
    
    telegram_bot = Bot(token=TELEGRAM_TOKEN)
    
    logger.info("Starting Bags Launchpad Telegram Bot (Hybrid Version)...")
    logger.info(f"Monitoring for tokens from deployer: {BAGS_UPDATE_AUTHORITY}")
    logger.info("Using hybrid approach: Bags scraping + RPC fallback")
    
    try:
        bot_info = await telegram_bot.get_me()
        logger.info(f"Bot connected: @{bot_info.username}")
        
        startup_message = "🤖 BagWatch Bot is online and monitoring Bags launchpad (Hybrid Version with enhanced data)!"
        await telegram_bot.send_message(
            chat_id=CHANNEL_ID,
            text=startup_message
        )
        logger.info("✅ Telegram connection test successful!")
        
    except Exception as e:
        logger.error(f"Failed to connect to Telegram: {e}")
        return
    
    logger.info("Starting monitoring services...")
    
    websocket_task = asyncio.create_task(monitor_websocket())
    polling_task = asyncio.create_task(monitor_polling())
    
    try:
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
