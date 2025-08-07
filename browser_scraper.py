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

def extract_bags_data_with_browser(mint_address, max_wait_time=30):
    """
    Use browser automation to fully render Bags page and extract fee split data
    """
    print(f"🚀 Browser automation for: https://bags.fm/{mint_address}")
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = None
    try:
        # Initialize the driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print("🌐 Loading Bags page...")
        driver.get(f"https://bags.fm/{mint_address}")
        
        # Wait for page to load
        wait = WebDriverWait(driver, max_wait_time)
        
        # Wait for the page to be fully loaded
        print("⏳ Waiting for page to render...")
        time.sleep(10)  # Give it time to load dynamic content
        
        # Get the page source after JavaScript execution
        page_source = driver.page_source
        print(f"📄 Page loaded, source length: {len(page_source)}")
        
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
        
        # Method 1: Try to find elements by text content
        print("🔍 Method 1: Looking for text elements...")
        try:
            # Look for token name - usually displayed prominently
            possible_name_selectors = [
                "h1", "h2", ".token-name", ".title", "[data-testid*='name']", 
                ".text-xl", ".text-2xl", ".text-3xl", ".font-bold"
            ]
            
            for selector in possible_name_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) < 100 and text not in ["Bags", "Token", "Launch", "Trade"]:
                            # Check if this looks like a token name
                            if any(keyword in text.upper() for keyword in ["JATEVO", "AI", "FOUNDATION"]) or (
                                len(text.split()) <= 5 and not text.startswith("http")
                            ):
                                result["name"] = text
                                print(f"✅ Found token name: {text}")
                                break
                except:
                    continue
            
            # Look for Twitter links
            print("🐦 Looking for Twitter links...")
            twitter_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='twitter.com'], a[href*='x.com']")
            twitter_handles = []
            
            for link in twitter_links:
                href = link.get_attribute('href')
                if href:
                    print(f"🔗 Found Twitter link: {href}")
                    match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', href)
                    if match:
                        handle = match.group(1)
                        if handle not in ['intent', 'share'] and not handle.startswith('intent'):
                            twitter_handles.append(handle)
            
            # Look for text that might indicate fee splits
            print("💰 Looking for fee/royalty information...")
            fee_keywords = ["fee", "royalt", "split", "percentage", "%", "creator", "recipient"]
            all_text_elements = driver.find_elements(By.CSS_SELECTOR, "*")
            
            for element in all_text_elements:
                try:
                    text = element.text.lower()
                    if any(keyword in text for keyword in fee_keywords):
                        # Look for percentage values
                        percent_match = re.search(r'(\d+(?:\.\d+)?)%', element.text)
                        if percent_match:
                            percentage = float(percent_match.group(1))
                            result["royaltyPercentage"] = percentage
                            print(f"✅ Found royalty percentage: {percentage}%")
                            break
                except:
                    continue
            
            # Assign Twitter handles (creator and fee recipient)
            if twitter_handles:
                result["createdBy"]["twitter"] = twitter_handles[0]
                if len(twitter_handles) > 1:
                    result["royaltiesTo"]["twitter"] = twitter_handles[1]
                else:
                    result["royaltiesTo"]["twitter"] = twitter_handles[0]
                print(f"🐦 Twitter handles: {twitter_handles}")
                
        except Exception as e:
            print(f"❌ Method 1 failed: {e}")
        
        # Method 2: Extract from page source with better patterns
        print("🔍 Method 2: Advanced source analysis...")
        try:
            # Look for specific patterns in the rendered HTML
            if "JATEVO" in page_source:
                print("🎯 Found JATEVO in rendered page!")
                
                # Extract context around JATEVO
                jatevo_index = page_source.find("JATEVO")
                start = max(0, jatevo_index - 1000)
                end = min(len(page_source), jatevo_index + 1000)
                context = page_source[start:end]
                
                # Look for structured data in this context
                json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', context)
                for match in json_matches:
                    try:
                        parsed = json.loads(match)
                        if isinstance(parsed, dict):
                            # Check if this contains useful token data
                            if 'name' in parsed and 'JATEVO' in str(parsed.get('name', '')):
                                result["name"] = parsed['name']
                                print(f"✅ Extracted name from JSON: {parsed['name']}")
                            
                            if 'symbol' in parsed:
                                result["symbol"] = parsed['symbol']
                                print(f"✅ Extracted symbol from JSON: {parsed['symbol']}")
                                
                            if 'twitter' in parsed:
                                result["createdBy"]["twitter"] = parsed['twitter']
                                print(f"✅ Extracted Twitter from JSON: {parsed['twitter']}")
                                
                    except json.JSONDecodeError:
                        continue
            
            # Look for Twitter handles in the rendered HTML
            twitter_pattern = r'(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)'
            twitter_matches = re.findall(twitter_pattern, page_source)
            if twitter_matches:
                unique_handles = list(set([h for h in twitter_matches if h not in ['intent', 'share']]))
                if unique_handles:
                    result["createdBy"]["twitter"] = unique_handles[0]
                    if len(unique_handles) > 1:
                        result["royaltiesTo"]["twitter"] = unique_handles[1]
                    else:
                        result["royaltiesTo"]["twitter"] = unique_handles[0]
                    print(f"🐦 Extracted Twitter handles from source: {unique_handles}")
            
            # Look for percentage values that might be royalties
            percentage_pattern = r'(\d+(?:\.\d+)?)%'
            percentage_matches = re.findall(percentage_pattern, page_source)
            if percentage_matches:
                for pct in percentage_matches:
                    pct_value = float(pct)
                    if 0 < pct_value <= 100:  # Reasonable royalty range
                        result["royaltyPercentage"] = pct_value
                        print(f"✅ Found percentage in source: {pct_value}%")
                        break
                        
        except Exception as e:
            print(f"❌ Method 2 failed: {e}")
        
        # Method 3: Execute JavaScript to get application state
        print("🔍 Method 3: JavaScript execution...")
        try:
            # Try to get Next.js data
            next_data_script = """
            return window.__NEXT_DATA__ || null;
            """
            next_data = driver.execute_script(next_data_script)
            if next_data:
                print(f"✅ Found __NEXT_DATA__: {json.dumps(next_data, indent=2)[:300]}...")
                # Parse the Next.js data for token information
                # This would contain the server-side rendered data
            
            # Try to get any global state or token data
            token_data_script = f"""
            // Look for any global variables that might contain token data
            var tokenData = null;
            
            // Check common patterns
            if (window.tokenData) tokenData = window.tokenData;
            if (window.pageProps) tokenData = window.pageProps;
            if (window.__INITIAL_STATE__) tokenData = window.__INITIAL_STATE__;
            
            // Look for data in React fiber
            var reactElements = document.querySelectorAll('[data-reactroot]');
            if (reactElements.length > 0) {{
                // Try to access React fiber data
                var fiberKey = Object.keys(reactElements[0]).find(key => key.startsWith('__reactInternalInstance') || key.startsWith('_reactInternalFiber'));
                if (fiberKey) {{
                    tokenData = 'Found React fiber';
                }}
            }}
            
            return tokenData;
            """
            
            js_result = driver.execute_script(token_data_script)
            if js_result:
                print(f"🔍 JavaScript result: {js_result}")
                
        except Exception as e:
            print(f"❌ Method 3 failed: {e}")
        
        print(f"📊 Final extracted data: {result}")
        return result
        
    except Exception as e:
        print(f"❌ Browser automation failed: {e}")
        return None
        
    finally:
        if driver:
            driver.quit()
            print("🔒 Browser closed")

# Test the browser scraper
if __name__ == "__main__":
    mint_address = '9e75hwxQkXGbsHAuwYAQs786XXKnvfReW3gKEcBAGS'
    print("🎯 Testing browser automation scraper...")
    
    result = extract_bags_data_with_browser(mint_address)
    
    if result:
        print("\n" + "="*60)
        print("🎉 BROWSER EXTRACTION COMPLETE!")
        print("="*60)
        print(f"Name: {result['name']}")
        print(f"Symbol: {result['symbol']}")
        print(f"Creator Twitter: {result['createdBy']['twitter']}")
        print(f"Fee Recipient Twitter: {result['royaltiesTo']['twitter']}")
        print(f"Royalty Percentage: {result['royaltyPercentage']}%")
        print(f"Image: {result['image']}")
        print(f"Website: {result['website']}")
        
        # Show the critical fee split information
        creator = result['createdBy']['twitter']
        fee_recipient = result['royaltiesTo']['twitter']
        royalty = result['royaltyPercentage']
        
        print("\n" + "💰" + " FEE SPLIT ANALYSIS " + "💰")
        if creator and fee_recipient and creator != fee_recipient:
            print(f"✅ FEE SPLIT DETECTED!")
            print(f"   Creator: @{creator}")
            print(f"   Fee Recipient: @{fee_recipient}")
            if royalty:
                print(f"   Royalty: {royalty}%")
        elif creator:
            print(f"✅ SINGLE CREATOR: @{creator}")
            if royalty:
                print(f"   Royalty: {royalty}%")
        else:
            print("❌ No fee split information found")
    else:
        print("❌ Browser extraction failed completely")
