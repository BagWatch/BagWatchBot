import requests
from bs4 import BeautifulSoup
import re
import json

def extract_bags_token_data(mint_address):
    """Enhanced scraper to extract token data from Bags.fm"""
    url = f'https://bags.fm/{mint_address}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    print(f"🔍 Scraping: {url}")
    response = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Initialize result
    result = {
        "name": "Unknown Token",
        "symbol": "UNKNOWN", 
        "image": None,
        "website": None,
        "createdBy": {"twitter": None},
        "royaltiesTo": {"twitter": None},
        "royaltyPercentage": None
    }
    
    print("📄 Analyzing page content...")
    
    # 1. Check page title and meta tags
    title = soup.find('title')
    if title and title.text:
        title_text = title.text.strip()
        print(f"📋 Title: {title_text}")
        
        # Extract token name from title
        if "on Bags" in title_text:
            token_name = title_text.replace("on Bags", "").replace("Token", "").strip()
            if token_name and token_name != "":
                result["name"] = token_name
                print(f"✅ Extracted name from title: {token_name}")
    
    # 2. Look for Open Graph and meta tags
    for meta in soup.find_all('meta'):
        property_name = meta.get('property') or meta.get('name')
        content = meta.get('content')
        
        if property_name and content:
            if property_name == 'og:title':
                result["name"] = content
                print(f"✅ Found OG title: {content}")
            elif property_name == 'og:image':
                result["image"] = content
                print(f"✅ Found OG image: {content}")
            elif property_name == 'description':
                print(f"📝 Description: {content}")
    
    # 3. Enhanced script analysis
    scripts = soup.find_all('script')
    print(f"🔍 Analyzing {len(scripts)} scripts...")
    
    for i, script in enumerate(scripts):
        if not script.string:
            continue
            
        script_content = script.string
        
        # Look for Next.js data that contains our mint address
        if mint_address in script_content:
            print(f"🎯 Script {i} contains mint address!")
            
            # Try to extract structured data around the mint address
            # Look for JSON-like structures
            mint_index = script_content.find(mint_address)
            
            # Get context around the mint address
            start = max(0, mint_index - 500)
            end = min(len(script_content), mint_index + 500)
            context = script_content[start:end]
            
            print(f"🔍 Context around mint: ...{context[:200]}...")
            
            # Look for patterns that might indicate token data
            patterns_to_check = [
                r'"name"\s*:\s*"([^"]+)"',
                r'"symbol"\s*:\s*"([^"]+)"', 
                r'"twitter"\s*:\s*"([^"]+)"',
                r'"image"\s*:\s*"([^"]+)"',
                r'"royalt[^"]*"\s*:\s*([^,}]+)',
                r'"percentage"\s*:\s*([^,}]+)'
            ]
            
            for pattern in patterns_to_check:
                matches = re.findall(pattern, context, re.IGNORECASE)
                if matches:
                    print(f"🔍 Pattern '{pattern}' found: {matches}")
        
        # Look for any script that might contain "JATEVO" or other token-specific data
        token_keywords = ['JATEVO', 'AI FOUNDATION', 'WEB3_XO', 'twitter', 'royalt']
        
        for keyword in token_keywords:
            if keyword.lower() in script_content.lower():
                print(f"🎯 Found keyword '{keyword}' in script {i}")
                
                # Get context around the keyword
                keyword_index = script_content.lower().find(keyword.lower())
                start = max(0, keyword_index - 200)
                end = min(len(script_content), keyword_index + 200)
                keyword_context = script_content[start:end]
                print(f"📝 Context: ...{keyword_context}...")
                
                # Try to extract structured data from this context
                json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', keyword_context)
                for match in json_matches:
                    try:
                        parsed = json.loads(match)
                        if isinstance(parsed, dict):
                            print(f"📊 Found JSON near '{keyword}': {parsed}")
                            
                            # Extract relevant fields
                            if 'name' in parsed:
                                result["name"] = parsed['name']
                            if 'symbol' in parsed:
                                result["symbol"] = parsed['symbol']
                            if 'twitter' in parsed:
                                result["createdBy"]["twitter"] = parsed['twitter']
                                
                    except json.JSONDecodeError:
                        continue
    
    # 4. Look for Twitter/X links in the HTML
    twitter_links = []
    for link in soup.find_all('a', href=re.compile(r'(twitter\.com|x\.com)')):
        href = link.get('href', '')
        twitter_links.append(href)
        print(f"🐦 Found Twitter link: {href}")
    
    # Extract Twitter handles
    twitter_handles = []
    for link in twitter_links:
        match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', link)
        if match:
            handle = match.group(1)
            if handle not in ['intent', 'share'] and not handle.startswith('intent'):
                twitter_handles.append(handle)
    
    # Assign Twitter handles
    if twitter_handles:
        result["createdBy"]["twitter"] = twitter_handles[0]
        if len(twitter_handles) > 1:
            result["royaltiesTo"]["twitter"] = twitter_handles[1]
        else:
            result["royaltiesTo"]["twitter"] = twitter_handles[0]
        
        print(f"✅ Extracted Twitter handles: {twitter_handles}")
    
    print(f"📊 Final result: {result}")
    return result

# Test the enhanced scraper
if __name__ == "__main__":
    mint_address = '9e75hwxQkXGbsHAuwYAQs786XXKnvfReW3gKEcBAGS'
    result = extract_bags_token_data(mint_address)
    
    print("\n" + "="*50)
    print("🎉 EXTRACTION COMPLETE!")
    print("="*50)
    for key, value in result.items():
        print(f"{key}: {value}")
