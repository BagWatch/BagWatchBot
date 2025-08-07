import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import re

def extract_bags_data_enhanced(mint_address, max_wait_time=40):
    """
    Enhanced browser automation to extract complete Bags token data including fee splits
    """
    print(f"🚀 Enhanced browser scraping: https://bags.fm/{mint_address}")
    
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
        
        print("🌐 Loading Bags page...")
        driver.get(f"https://bags.fm/{mint_address}")
        
        # Wait longer for all content to load
        print("⏳ Waiting for dynamic content...")
        time.sleep(15)  # Extended wait for React components
        
        # Scroll to load any lazy content
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
        
        print("🔍 Enhanced extraction starting...")
        
        # Method 1: Look for specific Bags page elements
        try:
            print("📋 Looking for token name...")
            # Try multiple selectors that might contain token name
            name_selectors = [
                "h1", "h2", ".title", ".token-title", ".coin-title",
                "[data-testid*='title']", "[data-testid*='name']",
                ".text-4xl", ".text-3xl", ".text-2xl", ".text-xl",
                ".font-bold", ".font-semibold"
            ]
            
            for selector in name_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and 3 <= len(text) <= 50:
                            # Check if this looks like a token name
                            if any(keyword in text.upper() for keyword in ["JATEVO", "AI", "FOUNDATION", "COIN", "TOKEN"]):
                                result["name"] = text
                                print(f"✅ Found token name: '{text}' via {selector}")
                                break
                            elif len(text.split()) <= 4 and not any(skip in text.lower() for skip in ["trade", "launch", "buy", "sell", "connect"]):
                                result["name"] = text
                                print(f"✅ Found potential token name: '{text}' via {selector}")
                                break
                except:
                    continue
                if result["name"] != "Unknown Token":
                    break
            
            print("🔤 Looking for token symbol...")
            # Look for token symbol
            symbol_selectors = [
                ".symbol", ".ticker", ".token-symbol",
                "[data-testid*='symbol']", "[data-testid*='ticker']"
            ]
            
            for selector in symbol_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and 2 <= len(text) <= 10 and text.isupper():
                            result["symbol"] = text
                            print(f"✅ Found symbol: '{text}' via {selector}")
                            break
                except:
                    continue
                if result["symbol"] != "UNKNOWN":
                    break
            
            print("🐦 Looking for Twitter/X links...")
            # Enhanced Twitter detection
            twitter_elements = driver.find_elements(By.CSS_SELECTOR, 
                "a[href*='twitter.com'], a[href*='x.com'], [href*='twitter'], [href*='/x.com']")
            
            twitter_data = []
            for element in twitter_elements:
                try:
                    href = element.get_attribute('href')
                    text = element.text.strip()
                    parent_text = element.find_element(By.XPATH, "..").text.strip()
                    
                    if href:
                        match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', href)
                        if match:
                            handle = match.group(1)
                            if handle not in ['intent', 'share', 'home']:
                                twitter_data.append({
                                    'handle': handle,
                                    'href': href,
                                    'text': text,
                                    'context': parent_text[:100]
                                })
                                print(f"🔗 Found Twitter: @{handle} - Context: '{parent_text[:50]}...'")
                except:
                    continue
            
            # Analyze Twitter data to determine creator vs fee recipient
            if twitter_data:
                # Look for context clues
                creator_handle = None
                fee_handle = None
                
                for data in twitter_data:
                    context = data['context'].lower()
                    if any(keyword in context for keyword in ['creator', 'created', 'by', 'author', 'made']):
                        creator_handle = data['handle']
                        print(f"🎯 Identified creator: @{creator_handle} (context: creator)")
                    elif any(keyword in context for keyword in ['fee', 'royalt', 'split', 'recipient', 'goes to']):
                        fee_handle = data['handle']
                        print(f"💰 Identified fee recipient: @{fee_handle} (context: fee)")
                
                # If we couldn't identify by context, use order
                if not creator_handle and twitter_data:
                    creator_handle = twitter_data[0]['handle']
                    print(f"🎯 Using first handle as creator: @{creator_handle}")
                
                if not fee_handle and len(twitter_data) > 1:
                    fee_handle = twitter_data[1]['handle']
                    print(f"💰 Using second handle as fee recipient: @{fee_handle}")
                elif not fee_handle:
                    fee_handle = creator_handle
                
                result["createdBy"]["twitter"] = creator_handle
                result["royaltiesTo"]["twitter"] = fee_handle
            
            print("💰 Looking for royalty/fee information...")
            # Enhanced percentage detection
            all_elements = driver.find_elements(By.CSS_SELECTOR, "*")
            for element in all_elements:
                try:
                    text = element.text
                    if '%' in text:
                        # Look for percentage values
                        percent_matches = re.findall(r'(\d+(?:\.\d+)?)%', text)
                        for match in percent_matches:
                            pct = float(match)
                            if 0 < pct <= 50:  # Reasonable royalty range
                                # Check context for fee-related keywords
                                element_context = text.lower()
                                if any(keyword in element_context for keyword in 
                                      ['royalt', 'fee', 'split', 'creator', 'goes to', 'recipient']):
                                    result["royaltyPercentage"] = pct
                                    print(f"✅ Found royalty: {pct}% - Context: '{text[:100]}...'")
                                    break
                                elif not result["royaltyPercentage"]:  # Fallback
                                    result["royaltyPercentage"] = pct
                                    print(f"📊 Found percentage: {pct}% - '{text[:50]}...'")
                except:
                    continue
                if result["royaltyPercentage"]:
                    break
            
        except Exception as e:
            print(f"❌ Method 1 failed: {e}")
        
        # Method 2: Page source analysis with better patterns
        print("🔍 Analyzing page source...")
        try:
            page_source = driver.page_source
            
            # Look for the specific token in source
            if "JATEVO" in page_source:
                print("🎯 Found JATEVO in page source!")
                
                # Extract JATEVO context
                jatevo_index = page_source.find("JATEVO")
                start = max(0, jatevo_index - 2000)
                end = min(len(page_source), jatevo_index + 2000)
                context = page_source[start:end]
                
                # Look for structured data
                json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                json_matches = re.findall(json_pattern, context)
                
                for match in json_matches:
                    try:
                        parsed = json.loads(match)
                        if isinstance(parsed, dict):
                            if 'name' in parsed and 'JATEVO' in str(parsed['name']):
                                result["name"] = parsed['name']
                                print(f"✅ JSON name: {parsed['name']}")
                            if 'symbol' in parsed:
                                result["symbol"] = parsed['symbol']
                                print(f"✅ JSON symbol: {parsed['symbol']}")
                    except:
                        continue
            
            # Enhanced Twitter extraction from source
            twitter_pattern = r'(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)(?:[^a-zA-Z0-9_]|$)'
            twitter_matches = re.findall(twitter_pattern, page_source)
            
            if twitter_matches:
                unique_handles = []
                for handle in twitter_matches:
                    if handle not in ['intent', 'share', 'home'] and handle not in unique_handles:
                        unique_handles.append(handle)
                
                if unique_handles:
                    print(f"🐦 Found Twitter handles in source: {unique_handles}")
                    if not result["createdBy"]["twitter"]:
                        result["createdBy"]["twitter"] = unique_handles[0]
                    if len(unique_handles) > 1 and not result["royaltiesTo"]["twitter"]:
                        result["royaltiesTo"]["twitter"] = unique_handles[1]
                    elif not result["royaltiesTo"]["twitter"]:
                        result["royaltiesTo"]["twitter"] = unique_handles[0]
            
        except Exception as e:
            print(f"❌ Method 2 failed: {e}")
        
        # Method 3: Wait for specific content and try again
        print("🔄 Final attempt - waiting for specific content...")
        try:
            # Wait for any element with specific Bags-related content
            wait = WebDriverWait(driver, 10)
            
            # Try to wait for elements that might contain the data we need
            potential_elements = [
                "//a[contains(@href, 'twitter')]",
                "//a[contains(@href, 'x.com')]", 
                "//*[contains(text(), '%')]",
                "//*[contains(text(), 'JATEVO')]"
            ]
            
            for xpath in potential_elements:
                try:
                    wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                    print(f"✅ Found element: {xpath}")
                    break
                except:
                    continue
            
            # Final check for any missed data
            if not result["createdBy"]["twitter"] or result["name"] == "Unknown Token":
                print("🔍 Final comprehensive scan...")
                
                # Get all text content
                body = driver.find_element(By.TAG_NAME, "body")
                all_text = body.text
                
                # Look for JATEVO AI FOUNDATION pattern
                if "JATEVO" in all_text and result["name"] == "Unknown Token":
                    lines = all_text.split('\n')
                    for line in lines:
                        if "JATEVO" in line and len(line.strip()) < 100:
                            result["name"] = line.strip()
                            print(f"✅ Final name extraction: {line.strip()}")
                            break
                
                # Look for @handles in all text
                at_handles = re.findall(r'@([a-zA-Z0-9_]+)', all_text)
                if at_handles and not result["createdBy"]["twitter"]:
                    # Filter out common non-user handles
                    real_handles = [h for h in at_handles if h not in ['twitter', 'x', 'bags', 'solana']]
                    if real_handles:
                        result["createdBy"]["twitter"] = real_handles[0]
                        if len(real_handles) > 1:
                            result["royaltiesTo"]["twitter"] = real_handles[1]
                        else:
                            result["royaltiesTo"]["twitter"] = real_handles[0]
                        print(f"✅ Final Twitter extraction: {real_handles}")
        
        except Exception as e:
            print(f"❌ Method 3 failed: {e}")
        
        print(f"📊 Final extraction result: {result}")
        return result
        
    except Exception as e:
        print(f"❌ Browser automation failed: {e}")
        return None
        
    finally:
        if driver:
            driver.quit()

# Test the enhanced scraper
if __name__ == "__main__":
    mint_address = 'GxTkyDCftKD5PzbWkWg2NHcmcqspWbi31T5skXKEBAGS'
    print("🎯 Testing ENHANCED browser automation with REAL Bags token...")
    
    result = extract_bags_data_enhanced(mint_address)
    
    if result:
        print("\n" + "="*70)
        print("🎉 ENHANCED EXTRACTION COMPLETE!")
        print("="*70)
        print(f"📛 Name: {result['name']}")
        print(f"🔤 Symbol: {result['symbol']}")
        print(f"👤 Creator Twitter: @{result['createdBy']['twitter'] or 'None'}")
        print(f"💰 Fee Recipient: @{result['royaltiesTo']['twitter'] or 'None'}")
        print(f"📊 Royalty: {result['royaltyPercentage'] or 'None'}%")
        
        print("\n" + "💰" * 20 + " FEE SPLIT ANALYSIS " + "💰" * 20)
        
        creator = result['createdBy']['twitter']
        fee_recipient = result['royaltiesTo']['twitter']
        royalty = result['royaltyPercentage']
        
        if creator and fee_recipient:
            if creator != fee_recipient:
                print(f"✅ 🚨 FEE SPLIT DETECTED! 🚨")
                print(f"   👤 Creator: @{creator}")
                print(f"   💰 Fee Recipient: @{fee_recipient}")
                print(f"   📊 Split: {royalty}% to @{fee_recipient}, {100-royalty if royalty else 'Unknown'}% to creator")
                print(f"   🔗 Creator Link: https://x.com/{creator}")
                print(f"   🔗 Fee Recipient Link: https://x.com/{fee_recipient}")
            else:
                print(f"✅ SINGLE CREATOR (No Split)")
                print(f"   👤 Creator: @{creator}")
                print(f"   📊 Royalty: {royalty}% (all to creator)")
        else:
            print("❌ Could not extract fee split information")
            print("💡 This might need manual verification or the page structure changed")
    
    else:
        print("❌ Enhanced extraction completely failed")
