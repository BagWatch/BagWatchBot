import requests
from bs4 import BeautifulSoup
import re
import json

mint_address = '9e75hwxQkXGbsHAuwYAQs786XXKnvfReW3gKEcBAGS'
url = f'https://bags.fm/{mint_address}'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

print(f"Testing scraper for: {url}")
response = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(response.text, 'html.parser')

print('=== PAGE TITLE ===')
title = soup.find('title')
print(f'Title: {title.text if title else "None"}')

print('\n=== META TAGS ===')
for meta in soup.find_all('meta'):
    name = meta.get('name') or meta.get('property')
    content = meta.get('content')
    if name and content and any(x in name.lower() for x in ['title', 'description', 'image', 'twitter', 'og:']):
        print(f'{name}: {content}')

print('\n=== TWITTER LINKS ===')
for link in soup.find_all('a', href=re.compile(r'(twitter\.com|x\.com)')):
    print(f'Link: {link.get("href")}')

print('\n=== LOOKING FOR TOKEN DATA IN SCRIPTS ===')
scripts = soup.find_all('script')
found_data = False

for i, script in enumerate(scripts):
    if script.string and len(script.string) > 50:
        script_content = script.string
        
        # Look for specific patterns that might contain token data
        if any(pattern in script_content for pattern in [
            'tokenAddress', mint_address, 'JATEVO', 'twitter', 'royalt', 'symbol', 'name'
        ]):
            print(f'\nScript {i} might contain token data:')
            print(f'Length: {len(script_content)}')
            
            # Try to find JSON objects
            json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', script_content)
            for j, match in enumerate(json_matches[:3]):  # Only first 3 matches
                try:
                    parsed = json.loads(match)
                    if isinstance(parsed, dict) and len(parsed) > 1:
                        print(f'  JSON object {j}: {match[:200]}...')
                        found_data = True
                except:
                    pass
            
            # Look for specific keywords
            keywords = ['JATEVO', 'twitter', 'symbol', 'name', mint_address[:20]]
            for keyword in keywords:
                if keyword in script_content:
                    # Find context around the keyword
                    idx = script_content.find(keyword)
                    start = max(0, idx - 100)
                    end = min(len(script_content), idx + 100)
                    context = script_content[start:end]
                    print(f'  Found "{keyword}": ...{context}...')
                    found_data = True

if not found_data:
    print('No obvious token data found in scripts')
    print(f'Total scripts: {len(scripts)}')
    print('Checking if data might be loaded via AJAX...')
