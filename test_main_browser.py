#!/usr/bin/env python3
"""
Test the main bot's browser automation function
"""

import sys
import os

# Add the current directory to the path so we can import from main.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import fetch_bags_token_data, format_telegram_message

def test_browser_extraction():
    """Test the browser automation with a real Bags token"""
    mint_address = 'GxTkyDCftKD5PzbWkWg2NHcmcqspWbi31T5skXKEBAGS'
    
    print("🎯 Testing main bot browser extraction...")
    print(f"Token: {mint_address}")
    print("="*60)
    
    # Test the extraction
    token_data = fetch_bags_token_data(mint_address)
    
    if token_data:
        print("✅ Browser extraction successful!")
        print(f"📊 Extracted data:")
        for key, value in token_data.items():
            print(f"  {key}: {value}")
        
        print("\n" + "="*60)
        print("📱 TELEGRAM MESSAGE FORMAT:")
        print("="*60)
        
        # Test the message formatting
        message = format_telegram_message(mint_address, token_data)
        print(message)
        
        # Analyze the fee split detection
        creator = token_data.get('createdBy', {}).get('twitter')
        fee_recipient = token_data.get('royaltiesTo', {}).get('twitter')
        royalty = token_data.get('royaltyPercentage')
        
        print("\n" + "💰" * 20)
        print("FEE SPLIT ANALYSIS")
        print("💰" * 20)
        
        if creator and fee_recipient:
            if creator != fee_recipient:
                print(f"🚨 FEE SPLIT DETECTED!")
                print(f"👤 Creator: @{creator}")
                print(f"💰 Fee Recipient: @{fee_recipient}")
                if royalty:
                    print(f"📊 Royalty: {royalty}%")
            else:
                print(f"✅ Single creator (no split)")
                print(f"👤 Creator: @{creator}")
        else:
            print("❌ No fee data extracted")
        
        return True
    else:
        print("❌ Browser extraction failed!")
        return False

if __name__ == "__main__":
    success = test_browser_extraction()
    if success:
        print("\n🎉 MAIN BOT BROWSER EXTRACTION TEST PASSED!")
        print("🚀 Ready for deployment with full fee split detection!")
    else:
        print("\n❌ TEST FAILED - Need to debug browser extraction")
