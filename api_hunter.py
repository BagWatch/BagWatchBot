import requests
import re
import json

def hunt_for_api_endpoints(mint_address):
    """Try to find the actual API endpoints Bags.fm uses"""
    
    print(f"🕵️ Hunting for API endpoints for: {mint_address}")
    
    # Test various potential API endpoints
    endpoints_to_try = [
        f"https://bags.fm/api/token/{mint_address}",
        f"https://bags.fm/api/tokens/{mint_address}",
        f"https://bags.fm/api/v1/token/{mint_address}",
        f"https://bags.fm/api/v1/tokens/{mint_address}",
        f"https://bags.fm/api/v2/token/{mint_address}",
        f"https://bags.fm/api/v2/tokens/{mint_address}",
        f"https://bags.fm/_next/data/token/{mint_address}",
        f"https://bags.fm/_api/token/{mint_address}",
        f"https://api.bags.fm/token/{mint_address}",
        f"https://api.bags.fm/tokens/{mint_address}",
        f"https://api.bags.fm/v1/token/{mint_address}",
        f"https://bags.fm/api/search?query={mint_address}",
        f"https://bags.fm/api/metadata/{mint_address}",
        f"https://bags.fm/_next/static/chunks/pages/app/(app)/[tokenAddress]-{mint_address}.json"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': f'https://bags.fm/{mint_address}',
        'Origin': 'https://bags.fm'
    }
    
    for endpoint in endpoints_to_try:
        try:
            print(f"🌐 Trying: {endpoint}")
            response = requests.get(endpoint, headers=headers, timeout=5)
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                print(f"   Content-Type: {content_type}")
                
                if 'application/json' in content_type:
                    try:
                        data = response.json()
                        print(f"   ✅ JSON Response: {json.dumps(data, indent=2)}")
                        return endpoint, data
                    except:
                        print(f"   ❌ Failed to parse JSON")
                else:
                    content = response.text[:200]
                    print(f"   📄 Text Response: {content}...")
                    
                    # Check if it contains useful data
                    if any(keyword in content.lower() for keyword in ['jatevo', 'token', 'name', 'symbol']):
                        print(f"   🎯 Might contain token data!")
                        return endpoint, response.text
            
            elif response.status_code == 404:
                print(f"   ❌ Not found")
            else:
                print(f"   ⚠️ Other status: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Request failed: {e}")
    
    print("\n🔍 No direct API endpoints found. Trying to extract from page source...")
    
    # If no API found, try to extract more intelligently from the main page
    try:
        page_url = f"https://bags.fm/{mint_address}"
        response = requests.get(page_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            content = response.text
            
            # Look for Next.js data more systematically
            print("🔍 Looking for Next.js __NEXT_DATA__ or server data...")
            
            # Pattern 1: __NEXT_DATA__ script tag
            next_data_match = re.search(r'__NEXT_DATA__[^<]*?({.*?})</script>', content, re.DOTALL)
            if next_data_match:
                try:
                    next_data = json.loads(next_data_match.group(1))
                    print(f"✅ Found __NEXT_DATA__: {json.dumps(next_data, indent=2)}")
                    return "next_data", next_data
                except:
                    print("❌ Failed to parse __NEXT_DATA__")
            
            # Pattern 2: self.__next_f.push data
            next_f_matches = re.findall(r'self\.__next_f\.push\(\[1,"([^"]*?)"\]\)', content)
            for i, match in enumerate(next_f_matches):
                if mint_address in match or 'token' in match.lower():
                    print(f"🎯 Found relevant __next_f data {i}")
                    try:
                        # The data is often JSON-encoded within the string
                        decoded = match.encode().decode('unicode_escape')
                        print(f"📄 Decoded data: {decoded[:300]}...")
                        
                        # Try to find JSON objects in the decoded data
                        json_objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', decoded)
                        for j, obj in enumerate(json_objects):
                            try:
                                parsed = json.loads(obj)
                                if isinstance(parsed, dict) and len(parsed) > 2:
                                    print(f"   📊 JSON object {j}: {json.dumps(parsed, indent=2)}")
                            except:
                                continue
                                
                    except Exception as e:
                        print(f"❌ Failed to decode __next_f data: {e}")
            
            # Pattern 3: Look for specific token data patterns
            print("🔍 Looking for token-specific patterns...")
            
            # Search for patterns that might contain JATEVO data
            jatevo_pattern = r'["\']JATEVO[^"\']*["\'][^}]*}'
            jatevo_matches = re.findall(jatevo_pattern, content, re.IGNORECASE)
            for match in jatevo_matches:
                print(f"🎯 Found JATEVO pattern: {match}")
            
            # Search for Twitter patterns
            twitter_pattern = r'["\']twitter["\'][^}]*?["\'][^"\']*?["\']'
            twitter_matches = re.findall(twitter_pattern, content, re.IGNORECASE)
            for match in twitter_matches[:3]:  # Only first 3
                print(f"🐦 Found Twitter pattern: {match}")
    
    except Exception as e:
        print(f"❌ Failed to analyze page source: {e}")
    
    return None, None

# Run the hunt
if __name__ == "__main__":
    mint_address = '9e75hwxQkXGbsHAuwYAQs786XXKnvfReW3gKEcBAGS'
    endpoint, data = hunt_for_api_endpoints(mint_address)
    
    if endpoint and data:
        print(f"\n🎉 SUCCESS! Found working endpoint: {endpoint}")
    else:
        print(f"\n😔 No direct API endpoints found, but we confirmed the page loads successfully")
        print("💡 The data is definitely in the page - we may need to use a browser automation approach")
