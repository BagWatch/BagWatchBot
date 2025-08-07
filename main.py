#!/usr/bin/env python3
"""
Bags Telegram Bot - OFFICIAL API ONLY VERSION
Complete rewrite to use ONLY the Bags API for all data
"""

import os
import sys
import json
import time
import asyncio
import logging
import websockets
import requests
from typing import Dict, Optional, Set
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID") 
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
BAGS_API_KEY = os.getenv("BAGS_API_KEY")

# Solana configuration
BAGS_UPDATE_AUTHORITY = "BAGSB9TpGrZxQbEsrEznv5jXXdwyP6AXerN8aVRiAmcv"
RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}" if HELIUS_API_KEY else "https://api.mainnet-beta.solana.com"
WS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}" if HELIUS_API_KEY else "wss://api.mainnet-beta.solana.com"

# Global state
telegram_bot = None
seen_mints: Set[str] = set()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def get_bags_token_data(mint_address: str) -> Optional[Dict]:
    """
    Fetch complete token data from OFFICIAL Bags API
    Using documented endpoints and authentication
    """
    try:
        logger.info(f"🔑 Fetching token data from OFFICIAL Bags API: {mint_address}")
        
        # OFFICIAL API configuration from docs
        base_url = "https://public-api-v2.bags.fm/api/v1"
        
        # WORKING authentication method from successful test
        headers = {
            "x-api-key": BAGS_API_KEY,  # CONFIRMED WORKING
            "Content-Type": "application/json"
        }
        
        # EXACT endpoints from official Bags API documentation
        endpoints_to_try = [
            # Get Token Launch Creators - EXACT endpoint from docs
            f"{base_url}/token-launch/creator/v2?tokenMint={mint_address}",
            
            # Get Token Lifetime Fees - EXACT endpoint from docs
            f"{base_url}/token-launch/lifetime-fees?tokenMint={mint_address}",
        ]
        
        for endpoint in endpoints_to_try:
            try:
                logger.info(f"🔍 Trying official endpoint: {endpoint}")
                logger.info(f"   Using x-api-key authentication")
                
                response = requests.get(endpoint, headers=headers, timeout=10)
                
                logger.info(f"   Response status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logger.info(f"✅ SUCCESS! Official Bags API working!")
                        logger.info(f"   Endpoint: {endpoint}")
                        logger.info(f"   Data structure: {type(data)}")
                        
                        if isinstance(data, dict):
                            logger.info(f"   Response keys: {list(data.keys())}")
                            
                            # Check if this is a successful API response
                            if data.get('success') or 'response' in data or len(data) > 0:
                                logger.info(f"   📊 Processing successful API response")
                                return normalize_bags_response(data, mint_address)
                            
                        elif isinstance(data, list) and len(data) > 0:
                            logger.info(f"   📊 Processing list response with {len(data)} items")
                            return normalize_bags_response(data, mint_address)
                        
                        logger.info(f"   ⚠️ Got 200 but empty/invalid data structure")
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"   ❌ Invalid JSON response: {e}")
                        logger.info(f"   Raw response: {response.text[:200]}...")
                        continue
                        
                elif response.status_code == 401:
                    logger.warning(f"   🔐 Unauthorized - API key might be invalid")
                    
                elif response.status_code == 403:
                    logger.warning(f"   🚫 Forbidden - API key might not have access")
                    
                elif response.status_code == 404:
                    logger.info(f"   ❌ Not Found - endpoint doesn't exist or no data for this token")
                    
                elif response.status_code == 429:
                    logger.warning(f"   ⚠️ Rate Limited - need to slow down requests")
                    # Check rate limit headers
                    remaining = response.headers.get('X-RateLimit-Remaining', 'unknown')
                    reset_time = response.headers.get('X-RateLimit-Reset', 'unknown')
                    logger.info(f"     Remaining requests: {remaining}")
                    logger.info(f"     Reset time: {reset_time}")
                    
                else:
                    logger.warning(f"   ❓ Unexpected status {response.status_code}")
                    logger.info(f"   Response: {response.text[:200]}...")
                    
            except Exception as e:
                logger.debug(f"   ❌ Request failed: {e}")
                continue
        
        logger.error(f"❌ All official Bags API endpoints failed for {mint_address}")
        return None
        
    except Exception as e:
        logger.error(f"Official Bags API error: {e}")
        return None

def normalize_bags_response(data: Dict, mint_address: str) -> Dict:
    """
    Normalize OFFICIAL Bags API response based on documented endpoints
    Handle Analytics API, Fee Share API, and Token API responses
    """
    try:
        logger.info(f"📊 Normalizing Bags API response for {mint_address}")
        
        # Initialize normalized structure
        normalized = {
            "name": None,
            "symbol": None, 
            "image": None,
            "website": None,
            "description": None,
            "createdBy": {"twitter": None},
            "royaltiesTo": {"twitter": None},
            "royaltyPercentage": None
        }
        
        # Handle the EXACT API response format from docs
        if isinstance(data, dict) and data.get('success'):
            # Official Bags API format: {"success": true, "response": [...]}
            logger.info(f"   Processing official Bags API response")
            
            response_data = data.get('response', [])
            logger.info(f"   Response data type: {type(response_data)}, length: {len(response_data) if isinstance(response_data, (list, dict)) else 'N/A'}")
            
            if isinstance(response_data, list) and len(response_data) > 0:
                logger.info(f"   Found {len(response_data)} items in response")
                
                for i, item in enumerate(response_data):
                    logger.info(f"   Processing item {i}: {type(item)}")
                    if isinstance(item, dict):
                        # Extract from /token-launch/creator/v2 endpoint
                        # Response: {"username":"<string>","pfp":"<string>","twitterUsername":"<string>","royaltyBps":123,"isCreator":true,"wallet":"<string>"}
                        
                        if 'twitterUsername' in item:
                            twitter_handle = item['twitterUsername']
                            is_creator = item.get('isCreator', False)
                            royalty_bps = item.get('royaltyBps', 0)
                            
                            if is_creator:
                                normalized["createdBy"]["twitter"] = twitter_handle
                                logger.info(f"   ✅ Found creator Twitter: @{twitter_handle}")
                            else:
                                normalized["royaltiesTo"]["twitter"] = twitter_handle
                                logger.info(f"   ✅ Found fee recipient Twitter: @{twitter_handle}")
                            
                            # Convert BPS to percentage
                            if royalty_bps > 0:
                                normalized["royaltyPercentage"] = royalty_bps / 100
                                logger.info(f"   ✅ Found royalty: {royalty_bps / 100}%")
                        
                        # Extract other basic info if available
                        if 'username' in item:
                            # This might be the token name in some contexts
                            if not normalized["name"]:
                                normalized["name"] = item["username"]
                                logger.info(f"   ✅ Found name from username: {item['username']}")
            else:
                logger.warning(f"   ⚠️ Response data is empty or not a list: {response_data}")
            
            if isinstance(response_data, str):
                # /token-launch/lifetime-fees returns a string (lamports amount)
                logger.info(f"   Processing lifetime fees response: {response_data}")
                # This is useful but not directly for our token display
                
        elif isinstance(data, dict):
            logger.info(f"   Processing object response with keys: {list(data.keys())}")
            
            # Handle nested response structures
            response_data = data
            if 'response' in data:
                response_data = data['response']
                logger.info(f"   Found nested response: {type(response_data)}")
            
            if 'data' in data:
                response_data = data['data']
                logger.info(f"   Found nested data: {type(response_data)}")
            
            # Handle array within object
            if isinstance(response_data, list) and len(response_data) > 0:
                return normalize_bags_response(response_data, mint_address)
            
            # Handle direct object response
            if isinstance(response_data, dict):
                # Extract all possible fields using multiple field names
                normalized["name"] = extract_field(response_data, [
                    "name", "token_name", "tokenName", "title", "displayName"
                ])
                
                normalized["symbol"] = extract_field(response_data, [
                    "symbol", "ticker", "token_symbol", "tokenSymbol"
                ])
                
                normalized["image"] = extract_field(response_data, [
                    "image", "logo", "image_url", "imageUrl", "icon", "logoUrl"
                ])
                
                normalized["website"] = extract_field(response_data, [
                    "website", "external_url", "externalUrl", "project_url", "websiteUrl"
                ])
                
                # Handle creator information
                creator_twitter = extract_nested_field(response_data, [
                    "createdBy.twitter", "created_by.twitter", "creator.twitter",
                    "author.twitter", "minter.twitter", "user.twitter"
                ])
                if creator_twitter:
                    normalized["createdBy"]["twitter"] = creator_twitter
                
                # Handle fee recipient information  
                fee_twitter = extract_nested_field(response_data, [
                    "royaltiesTo.twitter", "royalties_to.twitter", "fee_recipient.twitter",
                    "royalty_recipient.twitter", "fees.twitter", "feeRecipient.twitter"
                ])
                if fee_twitter:
                    normalized["royaltiesTo"]["twitter"] = fee_twitter
                
                # Handle royalty percentage
                normalized["royaltyPercentage"] = extract_field(response_data, [
                    "royaltyPercentage", "royalty_percentage", "royalty", "fee_percentage", "fees"
                ])
        
        # Log what we successfully extracted
        extracted_fields = []
        for key, value in normalized.items():
            if key in ["createdBy", "royaltiesTo"]:
                if value.get("twitter"):
                    extracted_fields.append(f"{key}.twitter")
            elif value:
                extracted_fields.append(key)
        
        logger.info(f"📊 Successfully extracted fields: {extracted_fields}")
        return normalized
        
    except Exception as e:
        logger.error(f"Error normalizing official Bags response: {e}")
        return create_fallback_token_data(mint_address)

def extract_field(data: Dict, possible_keys: list) -> Optional[str]:
    """Extract a field from data using multiple possible keys"""
    for key in possible_keys:
        if key in data and data[key]:
            return str(data[key])
    return None

def extract_nested_field(data: Dict, possible_paths: list) -> Optional[str]:
    """Extract nested field using dot notation paths"""
    for path in possible_paths:
        try:
            current = data
            for part in path.split('.'):
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    break
            else:
                if current:
                    return str(current)
        except:
            continue
    return None

def create_fallback_token_data(mint_address: str) -> Dict:
    """Create fallback token data structure"""
    return {
        "name": f"Token {mint_address[:8]}...",
        "symbol": "UNKNOWN",
        "image": None,
        "website": None,
        "description": None,
        "createdBy": {"twitter": None},
        "royaltiesTo": {"twitter": None},
        "royaltyPercentage": None
    }

def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram Markdown"""
    if not text:
        return ""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def clean_twitter_handle(handle: str) -> str:
    """Clean Twitter handle"""
    if not handle:
        return ""
    cleaned = (handle
             .replace("@", "")
             .replace("https://x.com/", "")
             .replace("https://twitter.com/", "")
             .strip())
    if "/" in cleaned:
        cleaned = cleaned.split("/")[0]
    return cleaned

def format_telegram_message(mint_address: str, token_data: Dict) -> str:
    """Format Telegram message with proper escaping"""
    try:
        name = token_data.get("name", "Unknown Token")
        symbol = token_data.get("symbol", "UNKNOWN")
        website = token_data.get("website", "")
        
        creator_twitter = token_data.get("createdBy", {}).get("twitter", "")
        royalty_twitter = token_data.get("royaltiesTo", {}).get("twitter", "")
        royalty_percentage = token_data.get("royaltyPercentage")
        
        creator_clean = clean_twitter_handle(creator_twitter)
        royalty_clean = clean_twitter_handle(royalty_twitter)
        
        message = f"""🚀 New Coin Launched on Bags!

Name: {escape_markdown(name)}
Ticker: {escape_markdown(symbol)}
Mint: {mint_address}
Solscan: https://solscan.io/token/{mint_address}
"""
        
        # Handle Twitter display logic
        if creator_clean and royalty_clean and creator_clean.lower() != royalty_clean.lower():
            message += f"\nCreator: [@{creator_clean}](https://x.com/{creator_clean})"
            message += f"\nFee Recipient: [@{royalty_clean}](https://x.com/{royalty_clean})"
        elif creator_clean:
            message += f"\nCreator: [@{creator_clean}](https://x.com/{creator_clean})"
        elif royalty_clean:
            message += f"\nCreator: [@{royalty_clean}](https://x.com/{royalty_clean})"
        
        # Royalty percentage
        if royalty_percentage:
            message += f"\nRoyalty: {royalty_percentage}%"
        
        # Website (if it's not just the Bags page)
        if website and not website.startswith("https://bags.fm/"):
            message += f"\nWebsite: {escape_markdown(website)}"
        
        message += f"\n\n🎒 [View on Bags](https://bags.fm/{mint_address})"
        message += f"\n📈 TRADE NOW:"
        message += f"\n• [AXIOM](http://axiom.trade/t/{mint_address}/@bagwatch)"
        message += f"\n• [Photon](https://photon-sol.tinyastro.io/@BagWatch/{mint_address})"
        
        return message
        
    except Exception as e:
        logger.error(f"Error formatting message: {e}")
        return f"🚀 New token detected: {mint_address}\nhttps://bags.fm/{mint_address}"

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
                    caption=message,
                    parse_mode="Markdown"
                )
                logger.info(f"✅ Sent token update with image for {mint_address}")
                return
            except Exception as e:
                logger.warning(f"Failed to send image for {mint_address}: {e}")
        
        # Send as text message
        await telegram_bot.send_message(
            chat_id=CHANNEL_ID,
            text=message,
            parse_mode="Markdown",
            disable_web_page_preview=False
        )
        logger.info(f"✅ Sent token update for {mint_address}")
        
    except Exception as e:
        logger.error(f"Error sending Telegram message for {mint_address}: {e}")

async def get_helius_metadata(mint_address: str) -> Dict:
    """Get token metadata from Helius API for name, symbol, and image"""
    if not HELIUS_API_KEY:
        return {"name": None, "symbol": None, "image": None, "website": None}
    
    try:
        url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
        
        payload = {
            "jsonrpc": "2.0",
            "id": "text",
            "method": "getAsset",
            "params": {"id": mint_address}
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            result = data.get("result", {})
            
            # Extract metadata
            content = result.get("content", {})
            metadata = content.get("metadata", {})
            
            name = metadata.get("name", "").strip()
            symbol = metadata.get("symbol", "").strip()
            
            # Get image from files
            image_url = None
            files = content.get("files", [])
            if files and len(files) > 0:
                image_url = files[0].get("uri")
            
            # Extract website from attributes
            website = None
            attributes = metadata.get("attributes", [])
            for attr in attributes:
                if attr.get("trait_type", "").lower() == "website":
                    website = attr.get("value")
                    break
            
            logger.info(f"✅ Helius metadata for {mint_address}: name={name}, symbol={symbol}")
            
            return {
                "name": name if name else None,
                "symbol": symbol if symbol else None, 
                "image": image_url,
                "website": website
            }
        
        logger.warning(f"Helius API returned {response.status_code}")
        return {"name": None, "symbol": None, "image": None, "website": None}
        
    except Exception as e:
        logger.error(f"Failed to get Helius metadata: {e}")
        return {"name": None, "symbol": None, "image": None, "website": None}

async def get_helius_metadata_with_delay(mint_address: str) -> Dict:
    """Get Helius metadata with short delay to allow indexing"""
    logger.info(f"⏳ Waiting 3 seconds for Helius to index new token: {mint_address}")
    await asyncio.sleep(3)
    
    logger.info(f"🔍 Fetching Helius metadata for {mint_address}")
    helius_data = await get_helius_metadata(mint_address)
    
    if helius_data.get("name") and helius_data.get("symbol"):
        logger.info(f"✅ Helius metadata found: {helius_data.get('name')} ({helius_data.get('symbol')})")
    else:
        logger.warning(f"⚠️ Helius metadata not yet available for {mint_address}")
    
    return helius_data

async def process_new_token(mint_address: str):
    """Process a newly detected token with hybrid approach: Bags API for fees + Helius for metadata"""
    try:
        if mint_address in seen_mints:
            return
        
        logger.info(f"🔄 Processing new token: {mint_address}")
        seen_mints.add(mint_address)
        
        # Get fee split data from Bags API (needs time to index)
        logger.info(f"⏳ Waiting 4.25 seconds for Bags API to index creator information: {mint_address}")
        await asyncio.sleep(4.25)
        
        bags_data = get_bags_token_data(mint_address)
        
        if not bags_data:
            logger.warning(f"⚠️ No data from Bags API after 4.25s delay, skipping token {mint_address}")
            return
        
        # Get metadata from Helius with delay to allow indexing
        helius_data = await get_helius_metadata_with_delay(mint_address)
        
        # Validate that we have essential metadata from Helius
        if not helius_data.get("name") or not helius_data.get("symbol"):
            logger.warning(f"⚠️ Skipping token {mint_address} - Helius metadata not available after 3s delay")
            return
        
        # Combine data - Helius for name/image, Bags for fee split
        combined_data = {
            "mint": mint_address,
            "name": helius_data.get("name"),
            "symbol": helius_data.get("symbol"),
            "image": helius_data.get("image"),
            "website": helius_data.get("website"),
            "createdBy": bags_data.get("createdBy", {}),
            "royaltiesTo": bags_data.get("royaltiesTo", {}), 
            "royaltyPercentage": bags_data.get("royaltyPercentage")
        }
        
        logger.info(f"✅ Combined token data: name={combined_data['name']}, creator={combined_data['createdBy']}, royalty={combined_data['royaltiesTo']}")
        await send_telegram_message(mint_address, combined_data)
        
    except Exception as e:
        logger.error(f"Error processing token {mint_address}: {e}")

# WebSocket monitoring and transaction processing (unchanged)
async def check_transaction_for_token_creation(signature: str):
    """Check if transaction contains Bags token creation with retry logic"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🔍 POLLING: New Bags transaction: {signature} (attempt {attempt + 1})")
            
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
            
            # Increase timeout for better reliability
            response = requests.post(RPC_URL, json=payload, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                
                if "result" in result and result["result"]:
                    tx_data = result["result"]
                    
                    # Look for token creation in logs
                    if "meta" in tx_data and "logMessages" in tx_data["meta"]:
                        logs = tx_data["meta"]["logMessages"]
                        
                        # Check for token creation patterns
                        token_creation_indicators = [
                            "CreateMetadataAccount",
                            "Program metaq invoke",
                            "CreateMasterEdition",
                            "InitializeMint"
                        ]
                        
                        for log in logs:
                            if any(indicator in log for indicator in token_creation_indicators):
                                logger.info(f"🎯 BAGS TOKEN CREATION: {signature}")
                                
                                # Extract mint address from transaction
                                mint_address = extract_mint_from_transaction(tx_data)
                                if mint_address:
                                    logger.info(f"🚀 POTENTIAL BAGS TOKEN FOUND: {mint_address}")
                                    await process_new_token(mint_address)
                                return  # Success, exit retry loop
                                
                    logger.info(f"📝 Transaction {signature} processed - no token creation detected")
                    return  # Success, exit retry loop
                    
                elif "error" in result:
                    logger.warning(f"⚠️ RPC error for {signature}: {result['error']}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                else:
                    logger.warning(f"⚠️ No result data for transaction {signature}")
                    return  # No point retrying
                    
            else:
                logger.warning(f"⚠️ RPC request failed with status {response.status_code} for {signature}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                    
        except requests.exceptions.Timeout:
            logger.warning(f"⏰ Timeout fetching transaction {signature} (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
        except Exception as e:
            logger.error(f"❌ Error checking transaction {signature} (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
                
    logger.error(f"❌ Failed to process transaction {signature} after {max_retries} attempts")
    
    # Add rate limiting
    await asyncio.sleep(1)

def extract_mint_from_transaction(tx_data: Dict) -> Optional[str]:
    """Extract mint address from transaction data"""
    try:
        if "transaction" in tx_data and "message" in tx_data["transaction"]:
            message = tx_data["transaction"]["message"]
            
            if "accountKeys" in message:
                account_keys = message["accountKeys"]
                
                # Look for potential mint addresses (Bags tokens typically end with "BAGS")
                for account in account_keys:
                    if isinstance(account, str) and account.endswith("BAGS"):
                        return account
                        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting mint: {e}")
        return None

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
                        
                        if "method" in data and data["method"] == "logsNotification":
                            signature = data["params"]["result"]["value"]["signature"]
                            await check_transaction_for_token_creation(signature)
                        elif "id" in data and data["id"] == 1:
                            logger.info(f"Subscription confirmed: {data.get('result')}")
                            
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
                        
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            logger.info("Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

async def main():
    """Main application entry point"""
    global telegram_bot
    
    # Validate configuration
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not found in environment variables")
        sys.exit(1)
    
    if not CHANNEL_ID:
        logger.error("CHANNEL_ID not found in environment variables")
        sys.exit(1)
    
    if not BAGS_API_KEY:
        logger.error("BAGS_API_KEY not found in environment variables")
        sys.exit(1)
    
    # Initialize Telegram bot
    telegram_bot = Bot(token=TELEGRAM_TOKEN)
    
    try:
        # Test bot connection
        bot_info = await telegram_bot.get_me()
        logger.info(f"Bot connected: @{bot_info.username}")
        
        # Test channel access
        await telegram_bot.send_message(
            chat_id=CHANNEL_ID,
            text="✅ Bags Bot started! Monitoring for new tokens... (Hybrid API with 4.25s Bags + 3s Helius delays)"
        )
        logger.info(f"✅ Telegram connection test successful!")
        
    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}")
        sys.exit(1)
    
    logger.info("Starting Bags Launchpad Telegram Bot (HYBRID VERSION WITH DUAL DELAYS)...")
    logger.info(f"Monitoring for tokens from deployer: {BAGS_UPDATE_AUTHORITY}")
    logger.info(f"Using Bags API (4.25s delay) for fee split + Helius (3s delay) for metadata")
    
    # Log configuration for debugging
    logger.info("=" * 50)
    logger.info("🔧 BOT CONFIGURATION:")
    logger.info(f"🎯 Monitoring wallet: {BAGS_UPDATE_AUTHORITY}")
    logger.info(f"🔗 RPC URL: {RPC_URL}")
    logger.info(f"🔗 WebSocket URL: {WS_URL}")
    logger.info(f"📱 Channel ID: {CHANNEL_ID}")
    logger.info(f"🔑 Helius API: {'✅ SET' if HELIUS_API_KEY else '❌ NOT SET'}")
    logger.info(f"🔑 Bags API: {'✅ SET' if BAGS_API_KEY else '❌ NOT SET'}")
    logger.info("=" * 50)
    
    logger.info("🚀 Starting monitoring services...")
    
    # Start monitoring
    await monitor_websocket()

if __name__ == "__main__":
    asyncio.run(main())
