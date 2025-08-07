#!/usr/bin/env python3
"""
Test the complete flow: Helius metadata + Fee split detection + Telegram message formatting
"""

import time
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Mock environment variables for testing
HELIUS_API_KEY = "your-helius-key-here"  # Replace with real key if testing
RPC_URL = f"https://rpc.helius.xyz/?api-key={HELIUS_API_KEY}"

def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram Markdown"""
    if not text:
        return ""
    
    # Characters that need escaping in Telegram Markdown
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def get_helius_metadata(mint_address: str):
    """Get complete metadata from Helius API including name, symbol, image, website, social"""
    try:
        # Use Helius getAsset API for metadata
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAsset",
            "params": [mint_address]
        }
        
        print(f"🔍 Calling Helius API for {mint_address}")
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
                    print(f"✅ Helius name: {name}")
                
                # Get token symbol
                symbol = metadata.get("symbol")
                if symbol and symbol.strip():
                    helius_data["symbol"] = symbol.strip()
                    print(f"✅ Helius symbol: {symbol}")
                
                # Get token image
                image = metadata.get("image")
                if image and image.strip():
                    helius_data["image"] = image.strip()
                    print(f"✅ Helius image: {image}")
                
                # Get project website from metadata
                website = metadata.get("external_url") or metadata.get("website")
                if website and website.strip():
                    helius_data["website"] = website.strip()
                    print(f"✅ Helius website: {website}")
                
                return helius_data
        
        print("❌ No valid metadata from Helius")
        return {"name": None, "symbol": None, "image": None, "website": None, "twitter": None}
        
    except Exception as e:
        print(f"❌ Helius metadata lookup failed: {e}")
        return {"name": None, "symbol": None, "image": None, "website": None, "twitter": None}

def get_fee_split_data(mint_address: str):
    """Get fee split data from Bags page"""
    print(f"🔍 Getting fee split from Bags for: {mint_address}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(15)
        driver.get(f"https://bags.fm/{mint_address}")
        
        # Wait for page load
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
        # Find Twitter links and analyze context
        twitter_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='twitter.com'], a[href*='x.com']")
        page_source = driver.page_source
        
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
                    
                    handle_upper = handle.upper()
                    handle_positions = []
                    start = 0
                    while True:
                        pos = page_source.upper().find(handle_upper, start)
                        if pos == -1:
                            break
                        handle_positions.append(pos)
                        start = pos + 1
                    
                    for pos in handle_positions:
                        start_pos = max(0, pos - 300)
                        end_pos = min(len(page_source), pos + 300)
                        context = page_source[start_pos:end_pos].lower()
                        
                        if "created by" in context and handle_upper.lower() in context and not creator_handle:
                            creator_handle = handle
                            print(f"🎯 CREATOR: @{handle}")
                            break
                        elif "royalties to" in context and handle_upper.lower() in context and not fee_handle:
                            fee_handle = handle
                            print(f"💰 FEE RECIPIENT: @{handle}")
                            break
                        elif "earns 100%" in context and handle_upper.lower() in context and not fee_handle:
                            fee_handle = handle
                            print(f"💰 FEE RECIPIENT: @{handle}")
                            break
                        elif "earns 0%" in context and handle_upper.lower() in context and not creator_handle:
                            creator_handle = handle
                            print(f"🎯 CREATOR: @{handle}")
                            break
                            
            except Exception as e:
                continue
        
        driver.quit()
        return {
            "createdBy": {"twitter": creator_handle or ""},
            "royaltiesTo": {"twitter": fee_handle or ""},
            "royaltyPercentage": None
        }
        
    except Exception as e:
        print(f"❌ Fee split extraction failed: {e}")
        return {
            "createdBy": {"twitter": ""},
            "royaltiesTo": {"twitter": ""},
            "royaltyPercentage": None
        }

def clean_twitter_handle(handle: str) -> str:
    """Clean and validate Twitter handle"""
    if not handle:
        return ""
    
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

def format_telegram_message(mint_address: str, token_data: dict) -> str:
    """Format the Telegram message using combined data"""
    try:
        # Extract data
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
        print(f"❌ Error formatting message: {e}")
        return f"🚀 New Coin Launched on Bags!\n\nMint: {mint_address}\nSolscan: https://solscan.io/token/{mint_address}\nWebsite: https://bags.fm/{mint_address}\n\n(Error fetching full details)"

def test_complete_flow(mint_address: str):
    """Test the complete bot flow"""
    print(f"🧪 TESTING COMPLETE BOT FLOW")
    print(f"🪙 Token: {mint_address}")
    print("=" * 60)
    
    # Step 1: Get Helius metadata
    print("\n📊 STEP 1: Getting Helius metadata...")
    helius_data = get_helius_metadata(mint_address)
    
    # Step 2: Get fee split data
    print("\n💰 STEP 2: Getting fee split data...")
    bags_data = get_fee_split_data(mint_address)
    
    # Step 3: Combine data
    print("\n🔄 STEP 3: Combining data sources...")
    combined_data = {
        "name": helius_data.get("name") or "Unknown Token",
        "symbol": helius_data.get("symbol") or "UNKNOWN", 
        "image": helius_data.get("image") or "",
        "website": helius_data.get("website") or "",
        "createdBy": {"twitter": ""},
        "royaltiesTo": {"twitter": ""},
        "royaltyPercentage": None
    }
    
    # Add fee split data if available
    if bags_data:
        creator_twitter = bags_data.get("createdBy", {}).get("twitter", "")
        fee_twitter = bags_data.get("royaltiesTo", {}).get("twitter", "")
        
        if creator_twitter:
            combined_data["createdBy"]["twitter"] = creator_twitter
            print(f"📝 Creator Twitter: @{creator_twitter}")
        
        if fee_twitter:
            combined_data["royaltiesTo"]["twitter"] = fee_twitter  
            print(f"📝 Fee Recipient Twitter: @{fee_twitter}")
    
    # Step 4: Format Telegram message
    print("\n📱 STEP 4: Formatting Telegram message...")
    telegram_message = format_telegram_message(mint_address, combined_data)
    
    # Results
    print("\n" + "=" * 60)
    print("📊 COMBINED DATA:")
    print(f"Name: {combined_data['name']}")
    print(f"Symbol: {combined_data['symbol']}")
    print(f"Image: {combined_data['image'][:60]}..." if combined_data['image'] else "Image: None")
    print(f"Website: {combined_data['website']}")
    print(f"Creator: @{combined_data['createdBy']['twitter']}" if combined_data['createdBy']['twitter'] else "Creator: None")
    print(f"Fee Recipient: @{combined_data['royaltiesTo']['twitter']}" if combined_data['royaltiesTo']['twitter'] else "Fee Recipient: None")
    
    print("\n" + "=" * 60)
    print("📱 FINAL TELEGRAM MESSAGE:")
    print("=" * 60)
    print(telegram_message)
    print("=" * 60)
    
    # Check for issues
    print("\n🔍 VALIDATION:")
    issues = []
    
    if combined_data['name'] == "Unknown Token":
        issues.append("❌ Token name not found")
    else:
        print("✅ Token name found")
    
    if combined_data['symbol'] == "UNKNOWN":
        issues.append("❌ Token symbol not found") 
    else:
        print("✅ Token symbol found")
        
    if not combined_data['image']:
        issues.append("❌ Token image not found")
    else:
        print("✅ Token image found")
        
    if not combined_data['createdBy']['twitter'] and not combined_data['royaltiesTo']['twitter']:
        issues.append("⚠️ No fee split data found")
    else:
        print("✅ Fee split data found")
    
    if issues:
        print("\n🚨 ISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n🎉 ALL GOOD! Message ready for Telegram!")
    
    return combined_data, telegram_message

if __name__ == "__main__":
    # Test with the $BOSS token
    boss_mint = "C5gs44PXUV4QGk7yHu4CYwF2X2f96SLVEL98JFZYBAGS"
    
    combined_data, message = test_complete_flow(boss_mint)
