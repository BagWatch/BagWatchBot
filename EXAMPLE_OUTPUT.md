# Example Bot Output

## Example 1: Token with Different Creator and Fee Recipient

```
🚀 New Coin Launched on Bags!

Name: JATEVO AI FOUNDATION
Ticker: JTVF
Mint: HUQT5qnag1RQ7dmVWVgkSNaBpbm7qGnrfRm76eYJCPYB
Solscan: https://solscan.io/token/HUQT5qnag1RQ7dmVWVgkSNaBpbm7qGnrfRm76eYJCPYB

Creator: @WEB3_XO
Fee Recipient: @JATEVOID
Royalty: 5%
Website: https://bags.fm/HUQT5qnag1RQ7dmVWVgkSNaBpbm7qGnrfRm76eYJCPYB
```

## Example 2: Token with Same Creator and Fee Recipient

```
🚀 New Coin Launched on Bags!

Name: SOMEDOGE COIN
Ticker: SOME
Mint: 8zF3Vx1N2jF4kL9mN5qR7tY6wE2pS4dH8xC1vB3nM6qK
Solscan: https://solscan.io/token/8zF3Vx1N2jF4kL9mN5qR7tY6wE2pS4dH8xC1vB3nM6qK

Twitter: @SOMEDOGE
Royalty: 3%
Website: https://bags.fm/8zF3Vx1N2jF4kL9mN5qR7tY6wE2pS4dH8xC1vB3nM6qK
```

## Example 3: Token with No Royalty Info

```
🚀 New Coin Launched on Bags!

Name: MINIMALIST TOKEN
Ticker: MIN
Mint: 4pL6tR9vN8dK2mF7wE5sQ1xH3zY6cB9jT8vM4nL7kP2Q
Solscan: https://solscan.io/token/4pL6tR9vN8dK2mF7wE5sQ1xH3zY6cB9jT8vM4nL7kP2Q

Creator: @MINIMALIST_DEV
Website: https://bags.fm/4pL6tR9vN8dK2mF7wE5sQ1xH3zY6cB9jT8vM4nL7kP2Q
```

## Expected Bags API Response Format

The bot expects this JSON structure from `https://bags.fm/api/token/<mint>`:

```json
{
  "name": "JATEVO AI FOUNDATION",
  "symbol": "JTVF", 
  "image": "https://example.com/token-image.png",
  "website": "https://jatevo.ai",
  "royaltyPercentage": 5,
  "createdBy": {
    "twitter": "WEB3_XO"
  },
  "royaltiesTo": {
    "twitter": "JATEVOID",
    "wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgHU"
  }
}
```

## Bonus: Royalty Data Storage

The bot optionally stores royalty data in memory:

```python
royalty_data = {
  "HUQT5qnag1RQ7dmVWVgkSNaBpbm7qGnrfRm76eYJCPYB": {
    "creator_twitter": "WEB3_XO",
    "royalty_twitter": "JATEVOID", 
    "royalty_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgHU"
  }
}
```
