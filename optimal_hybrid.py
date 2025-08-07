#!/usr/bin/env python3
"""
OPTIMAL HYBRID: Helius API (fast metadata) + Browser (fee split only)
"""

import time
import json
import requests
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import re

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use Helius API for metadata (working and fast)
HELIUS_API_KEY = "your_helius_key_here"  # You'll set this in .env
RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

def get_helius_metadata(mint_address):
    """Fast and reliable metadata using Helius API (like our original working bot)"""
    try:
        logger.info(f"🚀 Helius metadata extraction for {mint_address}")
        start_time = time.time()
        
        # Use Helius DAS API for metadata (this was working in our original bot)
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAsset",
            "params": [mint_address]
        }
        
        response = requests.post(RPC_URL, json=payload, timeout=10)
        if response.status_code != 200:
            logger.error(f"Helius API error: {response.status_code}")
            return None
            
        result = response.json()
        asset_data = result.get("result")
        
        if not asset_data:
            logger.warning("No asset data from Helius")
            return None
        
        # Extract metadata (this structure was working in our original bot)
        content = asset_data.get("content", {})
        metadata = content.get("metadata", {})
        
        token_data = {
            "name": metadata.get("name", "Unknown Token"),
            "symbol": metadata.get("symbol", "UNKNOWN"),
            "image": None,
            "description": metadata.get("description", "")
        }
        
        # Get image from files or links
        files = content.get("files", [])
        if files and len(files) > 0:
            # Usually the first file is the main image
            token_data["image"] = files[0].get("uri")
        
        # Fallback to links
        if not token_data["image"]:
            links = content.get("links", {})
            token_data["image"] = links.get("image")
        
        # If still no image, try the metadata URI
        if not token_data["image"] and metadata.get("uri"):
            try:
                uri_response = requests.get(metadata["uri"], timeout=5)
                if uri_response.status_code == 200:
                    uri_data = uri_response.json()
                    token_data["image"] = uri_data.get("image")
            except:
                pass
        
        extraction_time = time.time() - start_time
        logger.info(f"✅ Helius metadata in {extraction_time:.1f}s: {token_data['name']} ({token_data['symbol']})")
        
        return token_data
        
    except Exception as e:
        logger.error(f"Helius metadata extraction failed: {e}")
        return None

def get_fee_split_fast(mint_address):
    """SUPER FAST fee split extraction - optimized browser"""
    try:
        logger.info(f"💰 FAST fee split extraction for {mint_address}")
        start_time = time.time()
        
        # Optimized Chrome options for speed
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-images")  # Don't load images
        chrome_options.add_argument("--disable-javascript")  # Try without JS first
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-features=TranslateUI")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--aggressive-cache-discard")
        chrome_options.add_argument("--memory-pressure-off")
        
        driver = None
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set fast page load timeout
            driver.set_page_load_timeout(10)
            
            driver.get(f"https://bags.fm/{mint_address}")
            
            # Much shorter wait - we only need the DOM
            time.sleep(5)  # Reduced from 15s to 5s
            
            fee_data = {
                "createdBy": {"twitter": None},
                "royaltiesTo": {"twitter": None},
                "royaltyPercentage": None
            }
            
            # Fast Twitter extraction using CSS selectors
            twitter_handles = []
            
            # Get all Twitter links at once
            twitter_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='twitter.com'], a[href*='x.com']")
            
            for element in twitter_elements:
                try:
                    href = element.get_attribute('href')
                    if href:
                        match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', href)
                        if match:
                            handle = match.group(1)
                            if handle not in ['intent', 'share', 'home'] and handle not in twitter_handles:
                                twitter_handles.append(handle)
                except:
                    continue
            
            # Assign Twitter handles
            if twitter_handles:
                fee_data["createdBy"]["twitter"] = twitter_handles[0]
                if len(twitter_handles) > 1:
                    fee_data["royaltiesTo"]["twitter"] = twitter_handles[1]
                else:
                    fee_data["royaltiesTo"]["twitter"] = twitter_handles[0]
                
                logger.info(f"🔗 Twitter handles: {twitter_handles}")
            
            # Fast royalty extraction
            try:
                # Get page text in one operation
                page_text = driver.find_element(By.TAG_NAME, "body").text
                
                # Quick regex for percentages
                percent_matches = re.findall(r'(\d+(?:\.\d+)?)%', page_text)
                for match in percent_matches:
                    pct = float(match)
                    if 0 < pct <= 50:  # Reasonable royalty range
                        fee_data["royaltyPercentage"] = pct
                        logger.info(f"💰 Royalty: {pct}%")
                        break
            except:
                pass
            
            extraction_time = time.time() - start_time
            logger.info(f"✅ Fee extraction in {extraction_time:.1f}s")
            
            return fee_data
            
        finally:
            if driver:
                driver.quit()
        
    except Exception as e:
        logger.error(f"Fast fee extraction failed: {e}")
        return {
            "createdBy": {"twitter": None},
            "royaltiesTo": {"twitter": None},
            "royaltyPercentage": None
        }

def optimal_extraction(mint_address):
    """OPTIMAL: Helius metadata + fast fee scraping"""
    start_time = time.time()
    
    logger.info(f"🎯 OPTIMAL EXTRACTION: {mint_address}")
    
    # Step 1: Helius metadata (1-2 seconds)
    metadata = get_helius_metadata(mint_address)
    if not metadata:
        logger.error("Helius metadata failed")
        return None
    
    # Step 2: Fast fee scraping (5-7 seconds)
    fee_data = get_fee_split_fast(mint_address)
    
    # Step 3: Combine
    result = {
        "name": metadata["name"],
        "symbol": metadata["symbol"], 
        "image": metadata["image"],
        "website": f"https://bags.fm/{mint_address}",
        "createdBy": fee_data["createdBy"],
        "royaltiesTo": fee_data["royaltiesTo"],
        "royaltyPercentage": fee_data["royaltyPercentage"]
    }
    
    total_time = time.time() - start_time
    logger.info(f"🎉 OPTIMAL EXTRACTION COMPLETE in {total_time:.1f}s")
    
    return result

if __name__ == "__main__":
    mint_address = 'GxTkyDCftKD5PzbWkWg2NHcmcqspWbi31T5skXKEBAGS'
    
    print("⚡ TESTING OPTIMAL APPROACH: Helius + Fast Fee Scraping")
    print("="*70)
    
    # Test individual components
    print("\n1️⃣ HELIUS METADATA:")
    start = time.time()
    metadata = get_helius_metadata(mint_address)
    meta_time = time.time() - start
    print(f"⏱️ Helius metadata: {meta_time:.1f}s")
    if metadata:
        print(f"📛 Name: {metadata['name']}")
        print(f"🔤 Symbol: {metadata['symbol']}")
        print(f"🖼️ Image: {'✅ Found' if metadata['image'] else '❌ None'}")
    
    print("\n2️⃣ FAST FEE SCRAPING:")
    start = time.time()
    fee_data = get_fee_split_fast(mint_address)
    fee_time = time.time() - start
    print(f"⏱️ Fee extraction: {fee_time:.1f}s")
    print(f"👤 Creator: @{fee_data['createdBy']['twitter'] or 'None'}")
    print(f"💰 Fee Recipient: @{fee_data['royaltiesTo']['twitter'] or 'None'}")
    print(f"📊 Royalty: {fee_data['royaltyPercentage'] or 'None'}%")
    
    print("\n3️⃣ OPTIMAL COMBINED:")
    start = time.time()
    result = optimal_extraction(mint_address)
    optimal_time = time.time() - start
    
    if result:
        print(f"⏱️ TOTAL TIME: {optimal_time:.1f}s")
        print(f"⚡ Target: Under 10 seconds for production")
        
        print(f"\n📋 COMPLETE RESULT:")
        print(f"📛 Name: {result['name']}")
        print(f"🔤 Symbol: {result['symbol']}")
        print(f"🖼️ Image: {'✅ Found' if result['image'] else '❌ None'}")
        print(f"👤 Creator: @{result['createdBy']['twitter'] or 'None'}")
        print(f"💰 Fee Recipient: @{result['royaltiesTo']['twitter'] or 'None'}")
        print(f"📊 Royalty: {result['royaltyPercentage'] or 'None'}%")
        
        # Performance analysis
        print(f"\n📊 PERFORMANCE BREAKDOWN:")
        print(f"   🚀 Helius API: {meta_time:.1f}s")
        print(f"   🌐 Fee scraping: {fee_time:.1f}s")
        print(f"   ⚡ TOTAL: {optimal_time:.1f}s")
        
        if optimal_time <= 10:
            print(f"   ✅ SUCCESS: Under 10s target!")
        else:
            print(f"   ⚠️ Above 10s target, but still good")
        
        # Fee split analysis
        creator = result['createdBy']['twitter']
        fee_recipient = result['royaltiesTo']['twitter']
        
        if creator and fee_recipient and creator != fee_recipient:
            print(f"\n🚨 FEE SPLIT DETECTED!")
            print(f"   👤 Creator: @{creator}")
            print(f"   💰 Fee Recipient: @{fee_recipient}")
            print(f"   💯 PERFECT: We have ALL the data users need!")
    else:
        print("❌ Optimal extraction failed")
