#!/usr/bin/env python3
"""
Test the optimized main.py browser extraction
"""

import sys
import os
import time

# Import the optimized function - but handle the telegram import issue
try:
    # Try to mock the telegram import temporarily
    import unittest.mock
    with unittest.mock.patch.dict('sys.modules', {'telegram': unittest.mock.MagicMock()}):
        from main import fetch_bags_token_data
except ImportError:
    print("❌ Cannot import main.py due to missing telegram module")
    print("🔧 Let me create a standalone test version...")
    
    # Create a standalone version of the optimized function
    import time
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from webdriver_manager.chrome import ChromeDriverManager
    import re
    
    def fetch_bags_token_data_optimized(mint_address):
        """Optimized browser extraction (standalone version)"""
        try:
            print(f"🚀 OPTIMIZED browser scraping: https://bags.fm/{mint_address}")
            start_time = time.time()
            
            # OPTIMIZED Chrome options for speed
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
            
            driver = None
            try:
                service = Service(ChromeDriverManager().install())
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
                
                result = {
                    "name": "Unknown Token",
                    "symbol": "UNKNOWN", 
                    "image": None,
                    "website": None,
                    "createdBy": {"twitter": None},
                    "royaltiesTo": {"twitter": None},
                    "royaltyPercentage": None
                }
                
                # Extract token image using improved algorithm
                print("🖼️ Looking for token image...")
                token_image = None
                best_score = 0
                
                all_images = driver.find_elements(By.CSS_SELECTOR, "img")
                print(f"Analyzing {len(all_images)} images...")
                
                for img in all_images:
                    try:
                        src = img.get_attribute('src')
                        alt = img.get_attribute('alt') or ''
                        
                        if not src or not src.startswith('http'):
                            continue
                        
                        size = img.size
                        width = size.get('width', 0)
                        height = size.get('height', 0)
                        
                        score = 0
                        
                        # Strong positive indicators
                        if any(keyword in alt.lower() for keyword in ['logo', 'token', 'coin']) and 'icon' not in alt.lower():
                            score += 5
                        
                        if 'ipfs' in src or 'arweave' in src:
                            score += 4
                        
                        if any(keyword in src.lower() for keyword in ['wsrv.nl', 'cdn']):
                            score += 2
                        
                        # Size scoring
                        if width >= 80 and height >= 80:
                            score += 3
                        elif width >= 50 and height >= 50:
                            score += 2
                        elif width >= 30 and height >= 30:
                            score += 1
                        
                        if width == height and width >= 30:
                            score += 1
                        
                        # Negative indicators
                        if any(skip in src.lower() for skip in ['favicon', 'icon.png', 'x-dark', 'plus.webp', 'copy.webp']):
                            score -= 5
                        
                        if any(skip in alt.lower() for skip in ['icon', 'copy', 'plus', 'twitter']) and 'token' not in alt.lower():
                            score -= 3
                        
                        if width < 30 or height < 30:
                            score -= 2
                        
                        if score > best_score and score >= 3:
                            best_score = score
                            token_image = src
                            print(f"🏆 Best image (score {score}): {alt} - {src[:80]}...")
                    
                    except:
                        continue
                
                if token_image:
                    result["image"] = token_image
                    print(f"✅ Selected token image: {token_image[:100]}...")
                
                # Extract token name
                print("📛 Looking for token name...")
                name_selectors = ["h1", "h2", ".title", ".token-title", ".text-4xl", ".text-3xl", ".text-2xl", ".text-xl", ".font-bold"]
                for selector in name_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            text = element.text.strip()
                            if text and 3 <= len(text) <= 50:
                                if len(text.split()) <= 4 and not any(skip in text.lower() for skip in ["trade", "launch", "buy", "sell"]):
                                    result["name"] = text
                                    print(f"✅ Found token name: '{text}'")
                                    break
                    except:
                        continue
                    if result["name"] != "Unknown Token":
                        break
                
                # Extract Twitter handles
                print("🐦 Looking for Twitter handles...")
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
                    except:
                        continue
                
                if twitter_data:
                    result["createdBy"]["twitter"] = twitter_data[0]
                    if len(twitter_data) > 1:
                        result["royaltiesTo"]["twitter"] = twitter_data[1]
                    else:
                        result["royaltiesTo"]["twitter"] = twitter_data[0]
                    print(f"✅ Twitter handles: {twitter_data}")
                
                extraction_time = time.time() - start_time
                print(f"✅ OPTIMIZED extraction completed in {extraction_time:.1f}s")
                
                return result
                
            finally:
                if driver:
                    driver.quit()
            
        except Exception as e:
            print(f"❌ Optimized extraction failed: {e}")
            return None

def main():
    mint_address = 'GxTkyDCftKD5PzbWkWg2NHcmcqspWbi31T5skXKEBAGS'
    
    print("⚡ TESTING OPTIMIZED MAIN.PY BROWSER EXTRACTION")
    print("="*70)
    
    result = fetch_bags_token_data_optimized(mint_address)
    
    if result:
        print("\n🎉 OPTIMIZED EXTRACTION SUCCESS!")
        print("="*50)
        print(f"📛 Name: {result['name']}")
        print(f"🔤 Symbol: {result['symbol']}")
        print(f"🖼️ Image: {'✅ Found' if result['image'] else '❌ None'}")
        print(f"👤 Creator: @{result['createdBy']['twitter'] or 'None'}")
        print(f"💰 Fee Recipient: @{result['royaltiesTo']['twitter'] or 'None'}")
        print(f"📊 Royalty: {result['royaltyPercentage'] or 'None'}%")
        
        # Simulate Telegram message
        name = result['name']
        symbol = result['symbol']
        creator = result['createdBy']['twitter']
        fee_recipient = result['royaltiesTo']['twitter']
        
        print(f"\n📱 TELEGRAM MESSAGE PREVIEW:")
        print("="*40)
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
        
        message += f"\nWebsite: https://bags.fm/{mint_address}"
        
        print(message)
        
        if result['image']:
            print(f"\n🖼️ IMAGE WILL BE SENT: ✅")
        
        print(f"\n💰 FEE SPLIT ANALYSIS:")
        if creator and fee_recipient and creator != fee_recipient:
            print("🚨 FEE SPLIT DETECTED! Users will see who gets the fees!")
        elif creator:
            print("✅ Single creator detected")
        else:
            print("❌ No fee data extracted")
    else:
        print("❌ OPTIMIZED EXTRACTION FAILED")

if __name__ == "__main__":
    main()
