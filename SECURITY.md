# 🔒 Security Guidelines

## For Public GitHub Repositories

This bot is designed to be deployed from a **public GitHub repository** to Railway. Follow these security practices:

### ✅ What's Safe to Commit

- Source code (all `.py` files)
- Configuration files (`requirements.txt`, `Procfile`, etc.)
- Documentation (`README.md`, etc.)
- Example environment files (`env.example`)

### ❌ NEVER Commit These

- **Bot tokens** (`TELEGRAM_TOKEN`)
- **API keys or secrets**
- **`.env` files** with real values
- **Private keys** (`.key`, `.pem` files)
- **Database credentials**
- **Any sensitive configuration**

### 🛡️ Security Measures in Place

1. **`.gitignore`** - Prevents accidental commits of sensitive files
2. **Environment variables** - All secrets loaded from Railway environment
3. **Example files** - Template files show format without real values
4. **No hardcoded secrets** - All sensitive data comes from `os.getenv()`

### 🚀 Railway Deployment Security

1. **Fork the repository** to your own GitHub account
2. **Set environment variables** in Railway dashboard only
3. **Never put secrets in code** - Railway will inject them at runtime
4. **Monitor access** - Only you have access to your Railway project variables

### 🔍 Pre-Deployment Checklist

Before making your repository public or deploying:

- [ ] No bot tokens in any files
- [ ] No hardcoded secrets in code
- [ ] `.gitignore` includes `.env` and sensitive files
- [ ] All secrets use `os.getenv()` 
- [ ] Example files don't contain real values
- [ ] Railway environment variables are set

### 🚨 If You Accidentally Commit Secrets

1. **Immediately regenerate** the compromised token/key
2. **Update** Railway environment variables with new values
3. **Force push** to remove from git history (if recent)
4. **Consider** making repository private temporarily

### 📱 Telegram Bot Security

- **Regenerate token** if ever compromised
- **Use channel username** instead of numeric ID when possible
- **Make bot admin** of channel only (not owner)
- **Regular monitoring** of bot activity in logs

### 🔐 Best Practices

1. **Principle of least privilege** - Bot only needs channel posting permissions
2. **Regular token rotation** - Consider regenerating tokens periodically  
3. **Monitor logs** - Watch for unusual activity
4. **Separate environments** - Use different bots for testing vs production
5. **Access control** - Limit who has access to Railway project

Remember: **When in doubt, don't commit it!** It's always better to use environment variables for any configuration that could be considered sensitive.