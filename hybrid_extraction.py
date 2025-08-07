#!/usr/bin/env python3
"""
Hybrid extraction: Fast metadata + targeted fee scraping
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

def get_metadata_fast(mint_address, rpc_url="https://api.mainnet-beta.solana.com"):
    """Fast metadata extraction using RPC calls"""
    try:
        logger.info(f"🚀 Fast metadata extraction for {mint_address}")
        
        # Get account info to find metadata PDA
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [
                mint_address,
                {"encoding": "base64", "commitment": "confirmed"}
            ]
        }
        
        response = requests.post(rpc_url, json=payload, timeout=10)
        if response.status_code != 200:
            return None
            
        result = response.json()
        account_data = result.get("result", {}).get("value")
        
        if not account_data:
            return None
        
        # Try to get metadata using Helius DAS API (faster for metadata)
        das_url = "https://api.helius.xyz/v0/tokens/metadata"
        params = {"mint-accounts": [mint_address]}
        
        das_response = requests.get(das_url, params=params, timeout=5)
        if das_response.status_code == 200:
            das_data = das_response.json()
            if das_data and len(das_data) > 0:
                token_info = das_data[0]
                
                # Extract metadata
                metadata = {
                    "name": token_info.get("onChainMetadata", {}).get("metadata", {}).get("name", "Unknown Token"),
                    "symbol": token_info.get("onChainMetadata", {}).get("metadata", {}).get("symbol", "UNKNOWN"),
                    "image": None,
                    "description": token_info.get("onChainMetadata", {}).get("metadata", {}).get("description", "")
                }
                
                # Get image from URI
                uri = token_info.get("onChainMetadata", {}).get("metadata", {}).get("uri")
                if uri:
                    try:
                        uri_response = requests.get(uri, timeout=5)
                        if uri_response.status_code == 200:
                            uri_data = uri_response.json()
                            metadata["image"] = uri_data.get("image")
                            
                            # Update name/symbol from URI if better
                            if uri_data.get("name") and len(uri_data["name"]) > len(metadata["name"]):
                                metadata["name"] = uri_data["name"]
                            if uri_data.get("symbol") and len(uri_data["symbol"]) > len(metadata["symbol"]):
                                metadata["symbol"] = uri_data["symbol"]
                                
                    except Exception as e:
                        logger.debug(f"Error fetching URI data: {e}")
                
                logger.info(f"✅ Fast metadata: {metadata['name']} ({metadata['symbol']})")
                return metadata
        
        # Fallback: basic metadata
        return {
            "name": "Unknown Token",
            "symbol": "UNKNOWN",
            "image": None,
            "description": ""
        }
        
    except Exception as e:
        logger.error(f"Error in fast metadata extraction: {e}")
        return None

def get_fee_split_only(mint_address):
    """Targeted browser automation ONLY for fee split data"""
    try:
        logger.info(f"💰 Fee split extraction for {mint_address}")
        
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
        chrome_options.add_argument("--disable-images")  # Don't load images (we don't need them for fee data)
        chrome_options.add_argument("--disable-javascript")  # Try without JS first
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-extensions")
        
        driver = None
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            start_time = time.time()
            driver.get(f"https://bags.fm/{mint_address}")
            
            # Shorter wait since we only need fee data
            time.sleep(8)
            
            fee_data = {
                "createdBy": {"twitter": None},
                "royaltiesTo": {"twitter": None},
                "royaltyPercentage": None
            }
            
            # Extract Twitter handles quickly
            twitter_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='twitter.com'], a[href*='x.com']")
            twitter_handles = []
            
            for element in twitter_elements:
                try:
                    href = element.get_attribute('href')
                    if href:
                        match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', href)
                        if match:
                            handle = match.group(1)
                            if handle not in ['intent', 'share', 'home'] and handle not in twitter_handles:
                                twitter_handles.append(handle)
                                logger.info(f"🔗 Found Twitter: @{handle}")
                except:
                    continue
            
            # Assign fee split data
            if twitter_handles:
                fee_data["createdBy"]["twitter"] = twitter_handles[0]
                if len(twitter_handles) > 1:
                    fee_data["royaltiesTo"]["twitter"] = twitter_handles[1]
                else:
                    fee_data["royaltiesTo"]["twitter"] = twitter_handles[0]
            
            # Quick royalty percentage scan
            try:
                page_text = driver.find_element(By.TAG_NAME, "body").text
                percent_matches = re.findall(r'(\d+(?:\.\d+)?)%', page_text)
                for match in percent_matches:
                    pct = float(match)
                    if 0 < pct <= 50:  # Reasonable royalty range
                        fee_data["royaltyPercentage"] = pct
                        logger.info(f"💰 Found royalty: {pct}%")
                        break
            except:
                pass
            
            extraction_time = time.time() - start_time
            logger.info(f"✅ Fee extraction completed in {extraction_time:.1f}s")
            
            return fee_data
            
        finally:
            if driver:
                driver.quit()
        
    except Exception as e:
        logger.error(f"Fee split extraction failed: {e}")
        return {
            "createdBy": {"twitter": None},
            "royaltiesTo": {"twitter": None}, 
            "royaltyPercentage": None
        }

def hybrid_extraction(mint_address):
    """Combine fast metadata + targeted fee scraping"""
    start_time = time.time()
    
    logger.info(f"🎯 HYBRID EXTRACTION: {mint_address}")
    
    # Step 1: Fast metadata (2-3 seconds)
    metadata = get_metadata_fast(mint_address)
    if not metadata:
        logger.error("Failed to get metadata")
        return None
    
    # Step 2: Targeted fee scraping (8-10 seconds)
    fee_data = get_fee_split_only(mint_address)
    
    # Step 3: Combine results
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
    logger.info(f"🎉 HYBRID EXTRACTION COMPLETE in {total_time:.1f}s")
    
    return result

if __name__ == "__main__":
    mint_address = 'GxTkyDCftKD5PzbWkWg2NHcmcqspWbi31T5skXKEBAGS'
    
    print("🚀 TESTING HYBRID APPROACH: Fast Metadata + Fee Scraping")
    print("="*70)
    
    # Compare timings
    print("\n1️⃣ FAST METADATA ONLY:")
    start = time.time()
    metadata = get_metadata_fast(mint_address)
    meta_time = time.time() - start
    print(f"⏱️ Metadata extraction: {meta_time:.1f}s")
    if metadata:
        print(f"📛 Name: {metadata['name']}")
        print(f"🔤 Symbol: {metadata['symbol']}")
        print(f"🖼️ Image: {metadata['image'][:100] if metadata['image'] else 'None'}...")
    
    print("\n2️⃣ FEE SCRAPING ONLY:")
    start = time.time()
    fee_data = get_fee_split_only(mint_address)
    fee_time = time.time() - start
    print(f"⏱️ Fee extraction: {fee_time:.1f}s")
    print(f"👤 Creator: @{fee_data['createdBy']['twitter'] or 'None'}")
    print(f"💰 Fee Recipient: @{fee_data['royaltiesTo']['twitter'] or 'None'}")
    print(f"📊 Royalty: {fee_data['royaltyPercentage'] or 'None'}%")
    
    print("\n3️⃣ HYBRID APPROACH:")
    start = time.time()
    result = hybrid_extraction(mint_address)
    hybrid_time = time.time() - start
    
    if result:
        print(f"⏱️ TOTAL TIME: {hybrid_time:.1f}s")
        print(f"⚡ Speedup vs full browser: ~{(20-hybrid_time)/20*100:.0f}% faster")
        
        print(f"\n📋 COMPLETE RESULT:")
        print(f"📛 Name: {result['name']}")
        print(f"🔤 Symbol: {result['symbol']}")
        print(f"🖼️ Image: {'✅ Found' if result['image'] else '❌ None'}")
        print(f"👤 Creator: @{result['createdBy']['twitter'] or 'None'}")
        print(f"💰 Fee Recipient: @{result['royaltiesTo']['twitter'] or 'None'}")
        print(f"📊 Royalty: {result['royaltyPercentage'] or 'None'}%")
        
        # Analysis
        creator = result['createdBy']['twitter']
        fee_recipient = result['royaltiesTo']['twitter']
        
        print(f"\n💡 PERFORMANCE ANALYSIS:")
        print(f"   📊 Metadata: {meta_time:.1f}s (fast RPC)")
        print(f"   💰 Fee data: {fee_time:.1f}s (targeted scraping)")
        print(f"   🎯 Total: {hybrid_time:.1f}s")
        print(f"   ⚡ vs Full Browser (~20s): {((20-hybrid_time)/20*100):.0f}% faster")
        
        if creator and fee_recipient and creator != fee_recipient:
            print(f"\n🚨 FEE SPLIT DETECTED!")
            print(f"   👤 Creator: @{creator}")
            print(f"   💰 Fee Recipient: @{fee_recipient}")
            print(f"   💯 SUCCESS: We got the critical data users need!")
    else:
        print("❌ Hybrid extraction failed")
