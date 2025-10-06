# How to Get Your Slack Tokens

## 🎯 You Need TWO Tokens

| Cookie Name | Environment Variable | Starts With |
|-------------|---------------------|-------------|
| `d` | `SLACK_MCP_XOXD_TOKEN` | `xoxd-` |
| `d-s` | `SLACK_MCP_XOXC_TOKEN` | `xoxc-` |

## 📋 Step-by-Step Instructions

### 1. Open Slack in Your Browser
Go to: https://app.slack.com

### 2. Open Developer Tools
Press **F12** (or right-click → Inspect)

### 3. Go to Application Tab
Click: **Application** → **Storage** → **Cookies** → `https://app.slack.com`

### 4. Find TWO Cookies:

#### Cookie `d` (XOXD Token)
- Look for cookie named: **`d`**
- Value starts with: `xoxd-`
- Example: `xoxd-VGdnVdPhPmoawM3gH1qH4MilMKwJ...`
- This is your **SLACK_MCP_XOXD_TOKEN**

#### Cookie `d-s` (XOXC Token)
- Look for cookie named: **`d-s`**
- Value starts with: `xoxc-`
- Example: `xoxc-1759719096-12345-...`
- This is your **SLACK_MCP_XOXC_TOKEN**

### 5. Copy Both Values

Click on each cookie and copy the **entire** Value field.

## 🖼️ Visual Guide

```
Application Tab
├── Storage
│   ├── Cookies
│   │   └── https://app.slack.com
│   │       ├── d          ← Copy this value (XOXD)
│   │       ├── d-s        ← Copy this value (XOXC)
│   │       └── ... (other cookies)
```

## ⚠️ Important Notes

### Both tokens are required!
You need **BOTH** tokens for the MCP server to work.

### Format Check:
- **XOXD**: Should be a very long string starting with `xoxd-`
- **XOXC**: Should start with `xoxc-` followed by numbers and dashes

### Common Mistakes:
❌ Only copying the `d` cookie
❌ Copying the cookie name instead of the value
❌ Copying a timestamp (like `1759719096`) instead of the token

## 🔍 What You Currently Have:

✅ **XOXD Token**: `xoxd-VGdnVdPhP...` (Correct!)
❌ **XOXC Token**: Missing or incorrect (`1759719096` is not a valid token)

## 📝 Next Steps

1. Go back to Slack browser cookies
2. Find the **`d-s`** cookie (not just `d`)
3. Copy its **entire value** (should start with `xoxc-`)
4. Then run:

```bash
export SLACK_MCP_XOXD_TOKEN='xoxd-VGdnVdPhPmoawM3gH1qH4MilMKwJ1hP5%2FUTtDgC%2FXYvqrM987RVPE9rIunETYPKtjIs1YflBMwSMoNEbRqdYvtZ0GvxcsEAxic9tSVqAXih6kKhnREirdma9NzvtvYXydjJgWeKiLGlCOJDISCoWI009T42SKkqUUkr6IouK5zNgdhwmlDFBsH9Dh2tDsZeyym7YL6c%3D'

export SLACK_MCP_XOXC_TOKEN='xoxc-your-actual-token-from-d-s-cookie'

# Then setup Claude Code MCP
./setup_claude_code_mcp.sh
```

## 🆘 Still Having Trouble?

### Can't find `d-s` cookie?
- Make sure you're logged into Slack in your browser
- Try refreshing the Slack page
- Check you're looking at cookies for `https://app.slack.com` (not another domain)

### Cookie value too long?
- That's normal! Slack tokens are very long
- Make sure to copy the **entire** value
- Use quotes when setting environment variables

### Want to test tokens first?
```bash
# Test with Python script first
export SLACK_MCP_XOXD_TOKEN='xoxd-...'
export SLACK_MCP_XOXC_TOKEN='xoxc-...'

source venv/bin/activate
python diagnose.py
```

Should show: **Passed: 9/9** ✅
