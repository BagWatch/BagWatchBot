#!/usr/bin/env python3
"""
Test script for fee split detection - test locally before Railway deployment
"""

import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def test_fee_split_detection(mint_address: str):
    """Test fee split detection for a specific token"""
    print(f"🧪 Testing fee split detection for: {mint_address}")
    print(f"🌐 URL: https://bags.fm/{mint_address}")
    
    # Setup Chrome options for testing
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    try:
        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(15)
        
        # Load the page
        print("📥 Loading Bags page...")
        driver.get(f"https://bags.fm/{mint_address}")
        
        # Wait for page to load
        time.sleep(5)
        
        # Scroll to trigger any lazy loading
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
        # Wait for fee split content
        max_wait = 10
        for i in range(max_wait):
            try:
                page_source = driver.page_source
                if "created by" in page_source.lower() and ("royalties to" in page_source.lower() or "earns" in page_source.lower()):
                    print(f"✅ Fee split content detected after {5 + 4 + i}s")
                    break
                time.sleep(1)
            except:
                time.sleep(1)
        
        # Get page info
        page_text = driver.find_element(By.TAG_NAME, "body").text
        page_source = driver.page_source
        
        print(f"📄 Page text length: {len(page_text)}")
        print(f"📄 Page source length: {len(page_source)}")
        print(f"🔍 Contains 'created by': {'created by' in page_source.lower()}")
        print(f"🔍 Contains 'royalties to': {'royalties to' in page_source.lower()}")
        
        # Find Twitter links
        twitter_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='twitter.com'], a[href*='x.com']")
        print(f"🔗 Found {len(twitter_links)} Twitter links")
        
        creator_handle = None
        fee_handle = None
        
        for link in twitter_links:
            try:
                href = link.get_attribute('href')
                handle_match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', href)
                if handle_match:
                    handle = handle_match.group(1)
                    if handle in ['intent', 'share', 'home']:
                        continue
                    
                    print(f"\n🔍 Analyzing handle: @{handle}")
                    
                    # Get position of this handle in the full page source
                    handle_upper = handle.upper()
                    
                    # Find all occurrences of this handle in the page
                    handle_positions = []
                    start = 0
                    while True:
                        pos = page_source.upper().find(handle_upper, start)
                        if pos == -1:
                            break
                        handle_positions.append(pos)
                        start = pos + 1
                    
                    print(f"  📍 Handle found at {len(handle_positions)} positions")
                    
                    # For each position, check the surrounding text
                    for pos in handle_positions:
                        # Get text around this position (±300 chars)
                        start_pos = max(0, pos - 300)
                        end_pos = min(len(page_source), pos + 300)
                        context = page_source[start_pos:end_pos].lower()
                        
                        # Show a snippet of the context
                        context_snippet = context[280:320] if len(context) > 320 else context[-40:]
                        print(f"  📄 Context: ...{context_snippet}...")
                        
                        # Check for fee split indicators
                        if "created by" in context and handle_upper.lower() in context and not creator_handle:
                            creator_handle = handle
                            print(f"  🎯 CREATOR: @{handle} (found near 'created by')")
                            break
                        elif "royalties to" in context and handle_upper.lower() in context and not fee_handle:
                            fee_handle = handle
                            print(f"  💰 FEE RECIPIENT: @{handle} (found near 'royalties to')")
                            break
                        elif "earns 100%" in context and handle_upper.lower() in context and not fee_handle:
                            fee_handle = handle
                            print(f"  💰 FEE RECIPIENT: @{handle} (found near 'earns 100%')")
                            break
                        elif "earns 0%" in context and handle_upper.lower() in context and not creator_handle:
                            creator_handle = handle
                            print(f"  🎯 CREATOR: @{handle} (found near 'earns 0%')")
                            break
                            
            except Exception as e:
                print(f"  ❌ Error analyzing @{handle}: {e}")
                continue
        
        # Results
        print(f"\n🏁 FINAL RESULTS:")
        print(f"🎯 Creator: @{creator_handle}" if creator_handle else "❌ Creator: Not found")
        print(f"💰 Fee Recipient: @{fee_handle}" if fee_handle else "❌ Fee Recipient: Not found")
        
        driver.quit()
        return creator_handle, fee_handle
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return None, None

if __name__ == "__main__":
    # Test with the $BOSS token from the screenshot
    boss_mint = "C5gs44PXUV4QGk7yHu4CYwF2X2f96SLVEL98JFZYBAGS"
    
    print("🧪 TESTING FEE SPLIT DETECTION")
    print("=" * 50)
    
    creator, fee_recipient = test_fee_split_detection(boss_mint)
    
    print("\n" + "=" * 50)
    print("📊 EXPECTED RESULTS (from Bags page screenshot):")
    print("🎯 Creator: SILVERHAND83")
    print("💰 Fee Recipient: BUBBLEBATHGIRL")
    
    print("\n📊 ACTUAL RESULTS:")
    print(f"🎯 Creator: {creator or 'NOT FOUND'}")
    print(f"💰 Fee Recipient: {fee_recipient or 'NOT FOUND'}")
    
    print("\n✅ TEST RESULT:")
    if creator and fee_recipient:
        if creator.upper() == "SILVERHAND83" and fee_recipient.upper() == "BUBBLEBATHGIRL":
            print("🎉 PERFECT! Both creator and fee recipient detected correctly!")
        else:
            print("⚠️ PARTIAL: Detected handles but not matching expected values")
    else:
        print("❌ FAILED: Could not detect fee split information")
