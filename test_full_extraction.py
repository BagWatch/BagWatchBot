#!/usr/bin/env python3
"""
Test the complete token data extraction including images
"""

import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import re

# Set up logging to see the detailed extraction process
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_full_bags_data(mint_address):
    """Full extraction test using the updated algorithm from main.py"""
    logger.info(f"🚀 Full Bags data extraction: https://bags.fm/{mint_address}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        driver.get(f"https://bags.fm/{mint_address}")
        time.sleep(15)
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
        result = {
            "name": "Unknown Token",
            "symbol": "UNKNOWN", 
            "image": None,
            "website": None,
            "createdBy": {"twitter": None},
            "royaltiesTo": {"twitter": None},
            "royaltyPercentage": None
        }
        
        # Extract token image using the new algorithm
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
                    
                    logger.info(f"Image: {src[:60]}... | Alt: '{alt}' | Size: {width}x{height} | Score: {score}")
                    
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
        
        # Extract other data (name, Twitter, etc.) - simplified version
        try:
            # Token name
            name_selectors = ["h1", "h2", ".title", ".token-title", ".text-4xl", ".text-3xl", ".text-2xl", ".text-xl", ".font-bold"]
            for selector in name_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and 3 <= len(text) <= 50:
                            if len(text.split()) <= 4 and not any(skip in text.lower() for skip in ["trade", "launch", "buy", "sell", "connect"]):
                                result["name"] = text
                                logger.info(f"✅ Found token name: '{text}' via {selector}")
                                break
                except:
                    continue
                if result["name"] != "Unknown Token":
                    break
            
            # Twitter handles
            twitter_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='twitter.com'], a[href*='x.com']")
            twitter_data = []
            
            for element in twitter_elements:
                try:
                    href = element.get_attribute('href')
                    if href:
                        match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', href)
                        if match:
                            handle = match.group(1)
                            if handle not in ['intent', 'share', 'home']:
                                twitter_data.append(handle)
                                logger.info(f"🔗 Found Twitter: @{handle}")
                except:
                    continue
            
            if twitter_data:
                result["createdBy"]["twitter"] = twitter_data[0]
                if len(twitter_data) > 1:
                    result["royaltiesTo"]["twitter"] = twitter_data[1]
                else:
                    result["royaltiesTo"]["twitter"] = twitter_data[0]
        
        except Exception as e:
            logger.error(f"Error extracting other data: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"Full extraction failed: {e}")
        return None
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    mint_address = 'GxTkyDCftKD5PzbWkWg2NHcmcqspWbi31T5skXKEBAGS'
    
    print("🎯 Testing COMPLETE token data extraction...")
    print("="*70)
    
    result = extract_full_bags_data(mint_address)
    
    if result:
        print("\n" + "🎉" * 5 + " EXTRACTION COMPLETE! " + "🎉" * 5)
        print("="*70)
        print(f"📛 Name: {result['name']}")
        print(f"🔤 Symbol: {result['symbol']}")
        print(f"🖼️ Image: {result['image']}")
        print(f"👤 Creator: @{result['createdBy']['twitter'] or 'None'}")
        print(f"💰 Fee Recipient: @{result['royaltiesTo']['twitter'] or 'None'}")
        print(f"📊 Royalty: {result['royaltyPercentage'] or 'None'}%")
        
        print("\n" + "📱" * 10 + " TELEGRAM MESSAGE PREVIEW " + "📱" * 10)
        
        # Simulate the Telegram message format
        name = result['name']
        symbol = result['symbol']
        creator = result['createdBy']['twitter']
        fee_recipient = result['royaltiesTo']['twitter']
        royalty = result['royaltyPercentage']
        
        message = f"""🚀 New Coin Launched on Bags!

Name: {name}
Ticker: {symbol}
Mint: {mint_address}
Solscan: https://solscan.io/token/{mint_address}
"""
        
        if creator and fee_recipient and creator != fee_recipient:
            message += f"\nCreator: @{creator}"
            message += f"\nFee Recipient: @{fee_recipient}"
        elif creator:
            message += f"\nTwitter: @{creator}"
        
        if royalty:
            message += f"\nRoyalty: {royalty}%"
        
        message += f"\nWebsite: https://bags.fm/{mint_address}"
        
        print(message)
        
        if result['image']:
            print(f"\n🖼️ TOKEN IMAGE WILL BE SENT: {result['image']}")
        else:
            print("\n❌ NO TOKEN IMAGE - Message will be text only")
        
        print("\n" + "💰" * 15 + " FEE ANALYSIS " + "💰" * 15)
        if creator and fee_recipient and creator != fee_recipient:
            print("🚨 FEE SPLIT DETECTED! This is exactly what users need!")
            print(f"Creator gets royalties, but fees go to @{fee_recipient}")
        elif creator:
            print("✅ Single creator detected")
        else:
            print("❌ No creator/fee data")
            
    else:
        print("❌ EXTRACTION FAILED!")
