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
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import re

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

def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram Markdown"""
    if not text:
        return ""
    
    # Characters that need escaping in Telegram Markdown
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def get_helius_metadata(mint_address: str) -> Dict:
    """Get complete metadata from Helius API including name, symbol, image, website, social"""
    try:
        # Use Helius getAsset API for metadata
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAsset",
            "params": [mint_address]
        }
        
        # Use the RPC URL which should have Helius if HELIUS_API_KEY is set
        response = requests.post(RPC_URL, json=payload, timeout=5)
        if response.status_code == 200:
            result = response.json()
            asset_data = result.get("result")
            
            if asset_data:
                content = asset_data.get("content", {})
                metadata = content.get("metadata", {})
                
                helius_data = {
                    "name": None,
                    "symbol": None,
                    "image": None,
                    "website": None,
                    "twitter": None
                }
                
                # Get token name
                name = metadata.get("name")
                if name and name.strip() and name != mint_address:
                    helius_data["name"] = name.strip()
                    logger.info(f"✅ Helius name: {name}")
                
                # Get token symbol
                symbol = metadata.get("symbol")
                if symbol and symbol.strip():
                    helius_data["symbol"] = symbol.strip()
                    logger.info(f"✅ Helius symbol: {symbol}")
                
                # Get token image
                image = metadata.get("image")
                if image and image.strip():
                    helius_data["image"] = image.strip()
                    logger.info(f"✅ Helius image: {image}")
                
                # Get project website from metadata
                website = metadata.get("external_url") or metadata.get("website")
                if website and website.strip():
                    helius_data["website"] = website.strip()
                    logger.info(f"✅ Helius website: {website}")
                
                # Get Twitter from metadata attributes or properties
                attributes = metadata.get("attributes", [])
                for attr in attributes:
                    if isinstance(attr, dict):
                        trait_type = attr.get("trait_type", "").lower()
                        value = attr.get("value", "")
                        
                        if "twitter" in trait_type or "x" in trait_type:
                            # Clean Twitter handle
                            if value and isinstance(value, str):
                                clean_handle = value.replace("@", "").replace("https://twitter.com/", "").replace("https://x.com/", "").strip()
                                if clean_handle:
                                    helius_data["twitter"] = clean_handle
                                    logger.info(f"✅ Helius Twitter: @{clean_handle}")
                        elif "website" in trait_type and not helius_data["website"]:
                            if value and isinstance(value, str) and value.startswith("http"):
                                helius_data["website"] = value
                                logger.info(f"✅ Helius website from attributes: {value}")
                
                # Also check links section
                links = content.get("links", {})
                if isinstance(links, dict):
                    if not helius_data["website"] and links.get("external_url"):
                        helius_data["website"] = links["external_url"]
                        logger.info(f"✅ Helius website from links: {links['external_url']}")
                    
                    if not helius_data["twitter"] and links.get("twitter"):
                        twitter_url = links["twitter"]
                        if "twitter.com/" in twitter_url or "x.com/" in twitter_url:
                            handle = twitter_url.split("/")[-1]
                            helius_data["twitter"] = handle
                            logger.info(f"✅ Helius Twitter from links: @{handle}")
                
                return helius_data
        
        logger.debug("No valid metadata from Helius")
        return {"name": None, "symbol": None, "image": None, "website": None, "twitter": None}
        
    except Exception as e:
        logger.debug(f"Helius metadata lookup failed: {e}")
        return {"name": None, "symbol": None, "image": None, "website": None, "twitter": None}

def fetch_bags_token_data(mint_address: str) -> Optional[Dict]:
    """Fetch token data from Bags website using browser automation"""
    try:
        logger.info(f"🚀 Browser scraping Bags page: https://bags.fm/{mint_address}")
        
        # OPTIMIZED Chrome options for speed + Railway/Docker compatibility
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--log-level=3")
        # Performance optimizations
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--aggressive-cache-discard")
        # Railway/Docker compatibility
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--remote-debugging-port=9222")
        
        # Use system Chrome binary if available (Railway/Docker)
        chrome_binary = os.getenv("CHROME_BIN")
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            logger.info(f"Using Chrome binary: {chrome_binary}")
        
        # Use system ChromeDriver if available
        chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
        
        driver = None
        try:
            # Use system ChromeDriver if available, otherwise download
            if chromedriver_path and os.path.exists(chromedriver_path):
                service = Service(chromedriver_path)
                logger.info(f"Using system ChromeDriver: {chromedriver_path}")
            else:
                service = Service(ChromeDriverManager().install())
                logger.info("Using downloaded ChromeDriver")
            
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set fast page load timeout
            driver.set_page_load_timeout(10)
            
            # Load the Bags page
            driver.get(f"https://bags.fm/{mint_address}")
            
            # OPTIMIZED: Reduced wait times for faster extraction
            time.sleep(8)  # Reduced from 15s to 8s
            
            # Quick scroll to trigger any lazy loading
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)  # Reduced from 3s to 1s
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)  # Reduced from 2s to 1s
            
            # Initialize result structure
            result = {
                "name": "Unknown Token",
                "symbol": "UNKNOWN", 
                "image": None,
                "website": None,
                "createdBy": {"twitter": None},
                "royaltiesTo": {"twitter": None},
                "royaltyPercentage": None
            }
            
            # Extract token image FIRST (most important)
            logger.info("🖼️ Looking for token image...")
            
            token_image = None
            best_score = 0
            
            try:
                all_images = driver.find_elements(By.CSS_SELECTOR, "img")
                logger.info(f"Analyzing {len(all_images)} images for token image...")
                
                for img in all_images:
                    try:
                        src = img.get_attribute('src')
                        alt = img.get_attribute('alt') or ''
                        
                        if not src or not src.startswith('http'):
                            continue
                        
                        # Get actual rendered size
                        size = img.size
                        width = size.get('width', 0)
                        height = size.get('height', 0)
                        
                        # Score this image as a potential token image
                        score = 0
                        
                        # Strong positive indicators for token images
                        if any(keyword in alt.lower() for keyword in ['logo', 'token', 'coin']) and 'icon' not in alt.lower():
                            score += 5  # Alt text mentions logo/token/coin
                        
                        if 'ipfs' in src or 'arweave' in src:
                            score += 4  # Decentralized storage = likely token image
                        
                        if any(keyword in src.lower() for keyword in ['wsrv.nl', 'cdn']):
                            score += 2  # CDN images are often token images
                        
                        # Size-based scoring (larger = more likely to be token image)
                        if width >= 80 and height >= 80:
                            score += 3
                        elif width >= 50 and height >= 50:
                            score += 2
                        elif width >= 30 and height >= 30:
                            score += 1
                        
                        # Square images are more likely to be tokens
                        if width == height and width >= 30:
                            score += 1
                        
                        # Strong negative indicators
                        if any(skip in src.lower() for skip in ['favicon', 'icon.png', 'icon.ico', 'x-dark', 'plus.webp', 'copy.webp']):
                            score -= 5  # Definitely UI icons
                        
                        if any(skip in alt.lower() for skip in ['icon', 'copy', 'plus', 'twitter', 'logo']) and 'token' not in alt.lower():
                            score -= 3  # UI element descriptions
                        
                        if width < 30 or height < 30:
                            score -= 2  # Too small to be main token image
                        
                        if width != height and max(width, height) < 60:
                            score -= 1  # Small non-square images
                        
                        logger.debug(f"Image: {src[:60]}... | Alt: {alt} | Size: {width}x{height} | Score: {score}")
                        
                        if score > best_score and score >= 3:  # Minimum threshold
                            best_score = score
                            token_image = src
                            logger.info(f"🏆 New best token image candidate (score {score}): {alt} - {src[:100]}...")
                    
                    except Exception as e:
                        logger.debug(f"Error analyzing image: {e}")
                        continue
                
                if token_image:
                    result["image"] = token_image
                    logger.info(f"✅ Selected token image (score {best_score}): {token_image}")
                else:
                    logger.warning("❌ No suitable token image found")
                    
            except Exception as e:
                logger.error(f"Error in token image extraction: {e}")
            
            # Extract token name with improved detection
            logger.info("📛 Looking for token name...")
            name_selectors = ["h1", "h2", ".title", ".token-title", ".text-4xl", ".text-3xl", ".text-2xl", ".text-xl", ".font-bold", ".font-semibold"]
            
            for selector in name_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and 2 <= len(text) <= 100:  # More flexible length
                            # Skip navigation and UI elements
                            if not any(skip in text.lower() for skip in ["trade", "launch", "buy", "sell", "connect", "wallet", "settings", "home", "back"]):
                                # Prefer names that look like token names
                                if any(indicator in text for indicator in ["$", "TOKEN", "COIN"]) or len(text.split()) <= 5:
                                    result["name"] = text
                                    logger.info(f"✅ Found token name: '{text}' via {selector}")
                                    break
                                # Fallback: any reasonable text that's not too generic
                                elif len(text) >= 3 and result["name"] == "Unknown Token":
                                    result["name"] = text
                                    logger.info(f"✅ Found potential token name: '{text}' via {selector}")
                except:
                    continue
                if result["name"] != "Unknown Token":
                    break
            
            # Get page text for all extractions
            try:
                page_text = driver.find_element(By.TAG_NAME, "body").text
                logger.info(f"📄 Page loaded successfully, text length: {len(page_text)}")
            except Exception as e:
                logger.error(f"Failed to get page text: {e}")
                page_text = ""

            # Additional token name search in page text if still not found
            if result["name"] == "Unknown Token":
                try:
                    # Look for patterns like $TOKENNAME
                    dollar_tokens = re.findall(r'\$([A-Z0-9]{2,20})', page_text)
                    if dollar_tokens:
                        result["name"] = f"${dollar_tokens[0]}"
                        logger.info(f"✅ Found token name from $ pattern: {result['name']}")
                except:
                    pass

            # Always get complete metadata from Helius (primary data source)
            logger.info(f"🔍 Getting complete metadata from Helius for {mint_address}")
            helius_metadata = get_helius_metadata(mint_address)
            
            # Use Helius data as primary source for main token info
            if helius_metadata["name"] and helius_metadata["name"] != "Unknown Token":
                result["name"] = helius_metadata["name"]
                logger.info(f"✅ Using Helius token name: {helius_metadata['name']}")
            
            if helius_metadata["symbol"] and helius_metadata["symbol"].strip():
                result["symbol"] = helius_metadata["symbol"]
                logger.info(f"✅ Using Helius symbol: {helius_metadata['symbol']}")
            
            if helius_metadata["image"] and helius_metadata["image"].strip():
                result["image"] = helius_metadata["image"]
                logger.info(f"✅ Using Helius image: {helius_metadata['image']}")
            
            if helius_metadata["website"]:
                result["website"] = helius_metadata["website"]
                logger.info(f"✅ Using Helius website: {helius_metadata['website']}")
            
            # Store Helius Twitter for reference
            helius_twitter = helius_metadata["twitter"]
            if helius_twitter:
                logger.info(f"✅ Found Helius project Twitter: @{helius_twitter}")
            
            # Extract ticker from Bags page ($ version) as backup/supplement
            try:
                dollar_symbols = re.findall(r'\$([A-Z0-9]+)', page_text)
                dollar_symbols = [clean_ticker(sym) for sym in dollar_symbols if len(sym) <= 10 and sym != mint_address[:10]]
                
                if dollar_symbols:
                    # If no symbol from Helius, use the $ version as ticker
                    if not result["symbol"]:
                        result["symbol"] = f"${dollar_symbols[0]}"
                        logger.info(f"✅ Using Bags ticker: {result['symbol']}")
                    
            except Exception as e:
                logger.debug(f"Error extracting ticker: {e}")
            
            # BULLETPROOF fee split extraction - this CANNOT fail
            logger.info("🎯 BULLETPROOF FEE SPLIT EXTRACTION...")
            logger.info(f"📄 Full page text for debugging:\n{page_text}")
            try:
                # Method 1: Target specific HTML elements that contain the user info
                creator_handle = None
                fee_handle = None
                
                # Look for elements that contain "created by" text
                try:
                    # Find all text elements that might contain "created by"
                    all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'created by')]")
                    logger.info(f"🔍 Found {len(all_elements)} elements containing 'created by'")
                    
                    for i, element in enumerate(all_elements):
                        try:
                            element_text = element.text
                            logger.info(f"🔍 Element {i} text: '{element_text}'")
                            
                            # Get parent container that should have the Twitter link
                            parent = element.find_element(By.XPATH, "..")
                            twitter_links = parent.find_elements(By.CSS_SELECTOR, "a[href*='x.com'], a[href*='twitter.com']")
                            logger.info(f"🔍 Found {len(twitter_links)} Twitter links in parent")
                            
                            for link in twitter_links:
                                href = link.get_attribute('href')
                                logger.info(f"🔗 Twitter link: {href}")
                                
                                handle_match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', href)
                                if handle_match:
                                    creator_handle = handle_match.group(1)
                                    logger.info(f"🎯 CREATOR found via 'created by' element: @{creator_handle}")
                                    break
                            if creator_handle:
                                break
                        except Exception as sub_e:
                            logger.debug(f"Error processing created by element {i}: {sub_e}")
                            continue
                except Exception as e:
                    logger.debug(f"Created by element search failed: {e}")
                
                # Look for elements that contain "royalties to" text
                try:
                    all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'royalties to')]")
                    logger.info(f"🔍 Found {len(all_elements)} elements containing 'royalties to'")
                    
                    for i, element in enumerate(all_elements):
                        try:
                            element_text = element.text
                            logger.info(f"🔍 Element {i} text: '{element_text}'")
                            
                            # Get parent container that should have the Twitter link
                            parent = element.find_element(By.XPATH, "..")
                            twitter_links = parent.find_elements(By.CSS_SELECTOR, "a[href*='x.com'], a[href*='twitter.com']")
                            logger.info(f"🔍 Found {len(twitter_links)} Twitter links in parent")
                            
                            for link in twitter_links:
                                href = link.get_attribute('href')
                                logger.info(f"🔗 Twitter link: {href}")
                                
                                handle_match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', href)
                                if handle_match:
                                    fee_handle = handle_match.group(1)
                                    logger.info(f"💰 FEE RECIPIENT found via 'royalties to' element: @{fee_handle}")
                                    break
                            if fee_handle:
                                break
                        except Exception as sub_e:
                            logger.debug(f"Error processing royalties to element {i}: {sub_e}")
                            continue
                except Exception as e:
                    logger.debug(f"Royalties to element search failed: {e}")
                
                # Method 2: If HTML targeting failed, use improved text pattern matching
                if not creator_handle or not fee_handle:
                    logger.info("🔍 Fallback to improved text patterns...")
                    logger.info(f"🔍 Missing: creator={not creator_handle}, fee_recipient={not fee_handle}")
                    
                    # Look for exact pattern: "created by" followed by username and "X"
                    creator_pattern = r'created by[^@]*?([A-Z0-9_]{3,20})\s*X'
                    logger.info(f"🔍 Searching for creator pattern: {creator_pattern}")
                    creator_match = re.search(creator_pattern, page_text, re.IGNORECASE)
                    if creator_match and not creator_handle:
                        creator_handle = creator_match.group(1).strip()
                        logger.info(f"🎯 CREATOR found via text pattern: @{creator_handle}")
                    else:
                        logger.info(f"🔍 Creator pattern {'found' if creator_match else 'NOT found'}, already have creator: {bool(creator_handle)}")
                    
                    # Look for exact pattern: "royalties to" followed by username and "X"  
                    royalty_pattern = r'royalties to[^@]*?([A-Z0-9_]{3,20})\s*X'
                    logger.info(f"🔍 Searching for royalty pattern: {royalty_pattern}")
                    royalty_match = re.search(royalty_pattern, page_text, re.IGNORECASE)
                    if royalty_match and not fee_handle:
                        fee_handle = royalty_match.group(1).strip()
                        logger.info(f"💰 FEE RECIPIENT found via text pattern: @{fee_handle}")
                    else:
                        logger.info(f"🔍 Royalty pattern {'found' if royalty_match else 'NOT found'}, already have fee_handle: {bool(fee_handle)}")
                
                # Method 3: Last resort - try to parse the structured data
                if not creator_handle or not fee_handle:
                    logger.info("🆘 LAST RESORT: Parse any Twitter handles and match with context...")
                    
                    # Get all Twitter links on the page
                    twitter_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='twitter.com'], a[href*='x.com']")
                    handles_found = []
                    
                    for element in twitter_elements:
                        try:
                            href = element.get_attribute('href')
                            handle_match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', href)
                            if handle_match:
                                handle = handle_match.group(1)
                                if handle not in ['intent', 'share', 'home']:
                                    handles_found.append(handle)
                        except:
                            continue
                    
                    logger.info(f"🔗 Found Twitter handles: {handles_found}")
                    
                    # Match handles with text context
                    for handle in handles_found:
                        if handle.upper() in page_text.upper():
                            # Check if this handle appears near "created by"
                            created_context = page_text.lower().find('created by')
                            handle_pos = page_text.upper().find(handle.upper())
                            
                            if created_context != -1 and handle_pos != -1:
                                distance = abs(handle_pos - created_context)
                                if distance < 200 and not creator_handle:  # Within 200 chars
                                    creator_handle = handle
                                    logger.info(f"🎯 CREATOR matched by proximity: @{handle}")
                            
                            # Check if this handle appears near "royalties to"
                            royalty_context = page_text.lower().find('royalties to')
                            if royalty_context != -1 and handle_pos != -1:
                                distance = abs(handle_pos - royalty_context)
                                if distance < 200 and not fee_handle:  # Within 200 chars
                                    fee_handle = handle
                                    logger.info(f"💰 FEE RECIPIENT matched by proximity: @{handle}")
                
                # CRITICAL: Do not assign fallbacks that could be wrong
                if creator_handle:
                    result["createdBy"]["twitter"] = creator_handle
                    logger.info(f"✅ CREATOR SET: @{creator_handle}")
                else:
                    logger.warning("❌ NO CREATOR FOUND - leaving empty")
                    
                if fee_handle:
                    result["royaltiesTo"]["twitter"] = fee_handle
                    logger.info(f"✅ FEE RECIPIENT SET: @{fee_handle}")
                else:
                    logger.warning("❌ NO FEE RECIPIENT FOUND - leaving empty")
                
                logger.info(f"🏁 BULLETPROOF RESULT - Creator: @{creator_handle}, Fee Recipient: @{fee_handle}")
                    
            except Exception as e:
                logger.error(f"Error in bulletproof fee split extraction: {e}")
                # Do NOT set any fallback values that could be wrong
            
            # Extract project website (if different from Bags page)
            logger.info("🌐 Looking for project website...")
            try:
                # Look for website links that aren't Bags, Twitter, or common domains
                website_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='http']")
                for element in website_elements:
                    try:
                        href = element.get_attribute('href')
                        if href and href.startswith('http'):
                            # Skip Bags, Twitter, and trading links
                            if not any(domain in href.lower() for domain in [
                                'bags.fm', 'twitter.com', 'x.com', 'solscan.io', 
                                'axiomspace.xyz', 'photon-sol.tinyastro.io'
                            ]):
                                # Check if this looks like a project website
                                context = element.text.strip().lower()
                                parent_context = ""
                                try:
                                    parent_context = element.find_element(By.XPATH, "..").text.strip().lower()
                                except:
                                    pass
                                
                                # Look for website indicators
                                if any(indicator in f"{context} {parent_context}" for indicator in [
                                    'website', 'site', 'web', 'official', 'project'
                                ]) or len(context) == 0:  # Empty text often indicates website icon
                                    result["website"] = href
                                    logger.info(f"✅ Found project website: {href}")
                                    break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Error extracting website: {e}")
            
            # Extract royalty percentage
            logger.info("💰 Looking for royalty percentage...")
            try:
                all_elements = driver.find_elements(By.CSS_SELECTOR, "*")
                for element in all_elements:
                    try:
                        text = element.text
                        if '%' in text:
                            percent_matches = re.findall(r'(\d+(?:\.\d+)?)%', text)
                            for match in percent_matches:
                                pct = float(match)
                                if 0 < pct <= 50:
                                    result["royaltyPercentage"] = pct
                                    logger.info(f"✅ Found royalty: {pct}%")
                                    break
                    except:
                        continue
                    if result["royaltyPercentage"]:
                        break
            except Exception as e:
                logger.debug(f"Error extracting royalty: {e}")
            
            logger.info(f"✅ Successfully extracted Bags data for {mint_address}")
            return result
            
        finally:
            if driver:
                driver.quit()
        
    except Exception as e:
        logger.error(f"Failed to fetch token data from Bags for {mint_address}: {e}")
        return None

def format_telegram_message(mint_address: str, token_data: Dict) -> str:
    """Format the Telegram message using Bags browser-extracted data"""
    try:
        # Extract data from browser scraping result
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
        
        # Build the message with proper escaping
        message = f"""🚀 New Coin Launched on Bags!

Name: {escape_markdown(name)}
Ticker: {escape_markdown(symbol)}
Mint: {mint_address}
Solscan: https://solscan.io/token/{mint_address}
"""
        
        # Handle Twitter display logic with clickable usernames
        if creator_clean and royalty_clean and creator_clean.lower() != royalty_clean.lower():
            # Different creator and fee recipient - FEE SPLIT DETECTED
            message += f"\nCreator: [@{creator_clean}](https://x.com/{creator_clean})"
            message += f"\nFee Recipient: [@{royalty_clean}](https://x.com/{royalty_clean})"
        elif creator_clean:
            # Always show as Creator (not just "Twitter") - this person created the token
            message += f"\nCreator: [@{creator_clean}](https://x.com/{creator_clean})"
            
            # If there's additional social info that's different, show it separately
            # (This would require detecting project social vs creator social)
            
        elif royalty_clean:
            # Fallback: only fee recipient found
            message += f"\nCreator: [@{royalty_clean}](https://x.com/{royalty_clean})"
        
        # Add royalty percentage if available
        if royalty_percentage is not None:
            message += f"\nRoyalty: {royalty_percentage}%"
        
        # Add project website if available (separate from Bags)
        if website and website != f"https://bags.fm/{mint_address}" and not website.startswith("https://bags.fm/"):
            message += f"\nWebsite: {escape_markdown(website)}"
        
        # Add clean Bags link (not the long URL)
        message += f"\n\n🎒 [View on Bags](https://bags.fm/{mint_address})"
        
        # Add trading links
        message += f"\n📈 TRADE NOW:"
        message += f"\n• [AXIOM](http://axiom.trade/t/{mint_address}/@bagwatch)"
        message += f"\n• [Photon](https://photon-sol.tinyastro.io/@BagWatch/{mint_address})"
        
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
                    caption=message,
                    parse_mode="Markdown"
                )
                logger.info(f"Sent token update with image for {mint_address}")
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
    """Process a newly detected token using Bags browser automation"""
    try:
        if mint_address in seen_mints:
            return
        
        logger.info(f"Processing new token: {mint_address}")
        seen_mints.add(mint_address)
        
        # Fetch token data from Bags website using browser automation
        token_data = fetch_bags_token_data(mint_address)
        
        if token_data:
            # Send Telegram message with browser-extracted data
            await send_telegram_message(mint_address, token_data)
        else:
            # Fallback if browser automation fails
            logger.warning(f"Bags browser extraction failed for {mint_address}, sending basic notification")
            fallback_message = f"""🚀 New Coin Launched on Bags!

Mint: {mint_address}
Solscan: https://solscan.io/token/{mint_address}
Website: https://bags.fm/{mint_address}

💡 Visit Bags page for fee split info and token details"""
            
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
    
    logger.info("Starting Bags Launchpad Telegram Bot (Browser Automation)...")
    logger.info(f"Monitoring for tokens from deployer: {BAGS_UPDATE_AUTHORITY}")
    logger.info(f"Using Bags browser extraction for complete fee split data")
    
    # Test Telegram connection
    try:
        bot_info = await telegram_bot.get_me()
        logger.info(f"Bot connected: @{bot_info.username}")
        
        # Send startup message
        startup_message = "🤖 BagWatch Bot is online with FULL FEE SPLIT DETECTION! 💰🔍"
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
