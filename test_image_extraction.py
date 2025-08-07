#!/usr/bin/env python3
"""
Test image extraction from Bags token page
"""

import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def test_image_extraction(mint_address):
    """Test extracting token image from Bags page"""
    print(f"🖼️ Testing image extraction for: https://bags.fm/{mint_address}")
    
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
        
        # Load the page
        driver.get(f"https://bags.fm/{mint_address}")
        time.sleep(15)
        
        # Scroll to load content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
        print("🔍 Analyzing all images on the page...")
        
        # Get all images
        all_images = driver.find_elements(By.CSS_SELECTOR, "img")
        print(f"Found {len(all_images)} total images")
        
        candidate_images = []
        
        for i, img in enumerate(all_images):
            try:
                src = img.get_attribute('src')
                alt = img.get_attribute('alt') or ''
                width = img.get_attribute('width') or ''
                height = img.get_attribute('height') or ''
                
                # Get actual rendered size
                size = img.size
                actual_width = size.get('width', 0)
                actual_height = size.get('height', 0)
                
                if src and src.startswith('http'):
                    print(f"\nImage {i+1}:")
                    print(f"  📎 SRC: {src}")
                    print(f"  🏷️ ALT: {alt}")
                    print(f"  📏 Declared size: {width}x{height}")
                    print(f"  📐 Actual size: {actual_width}x{actual_height}")
                    
                    # Score this image as a potential token image
                    score = 0
                    reasons = []
                    
                    # Content-based scoring
                    if any(keyword in src.lower() for keyword in ['token', 'coin', 'image', 'media', 'cdn']):
                        score += 3
                        reasons.append("URL contains token keywords")
                    
                    if any(keyword in alt.lower() for keyword in ['token', 'coin']):
                        score += 2
                        reasons.append("Alt text contains token keywords")
                    
                    # Size-based scoring
                    if actual_width >= 100 and actual_height >= 100:
                        score += 3
                        reasons.append("Large size (likely token image)")
                    elif actual_width >= 50 and actual_height >= 50:
                        score += 1
                        reasons.append("Medium size")
                    
                    # Avoid obvious non-token images
                    if any(skip in src.lower() for skip in ['icon', 'bg', 'background', 'favicon', 'logo-small']):
                        score -= 2
                        reasons.append("Likely not token image (favicon/bg/icon)")
                    
                    # Square images are more likely to be tokens
                    if actual_width == actual_height and actual_width >= 50:
                        score += 1
                        reasons.append("Square aspect ratio")
                    
                    print(f"  ⭐ Score: {score}")
                    print(f"  📝 Reasons: {', '.join(reasons)}")
                    
                    if score >= 2:  # Minimum threshold
                        candidate_images.append({
                            'src': src,
                            'alt': alt,
                            'score': score,
                            'width': actual_width,
                            'height': actual_height,
                            'reasons': reasons
                        })
                        
            except Exception as e:
                print(f"  ❌ Error analyzing image {i+1}: {e}")
        
        # Sort candidates by score
        candidate_images.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"\n🏆 TOP IMAGE CANDIDATES:")
        print("="*60)
        
        for i, candidate in enumerate(candidate_images[:5]):  # Show top 5
            print(f"\n{i+1}. Score: {candidate['score']} | Size: {candidate['width']}x{candidate['height']}")
            print(f"   📎 URL: {candidate['src']}")
            print(f"   🏷️ Alt: {candidate['alt']}")
            print(f"   📝 Reasons: {', '.join(candidate['reasons'])}")
        
        # Return the best candidate
        if candidate_images:
            best_image = candidate_images[0]
            print(f"\n✅ SELECTED TOKEN IMAGE:")
            print(f"📎 URL: {best_image['src']}")
            print(f"📏 Size: {best_image['width']}x{best_image['height']}")
            print(f"⭐ Score: {best_image['score']}")
            return best_image['src']
        else:
            print("\n❌ No suitable token image found")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    # Test with the real token
    mint_address = 'GxTkyDCftKD5PzbWkWg2NHcmcqspWbi31T5skXKEBAGS'
    image_url = test_image_extraction(mint_address)
    
    if image_url:
        print(f"\n🎉 SUCCESS! Token image URL: {image_url}")
    else:
        print(f"\n❌ FAILED to extract token image")
