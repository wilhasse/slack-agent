# Slack Webhook Setup Guide

## Why Use Webhooks?

Webhooks are **more reliable** than MCP for sending messages because:
- ✅ **No channel lookup needed** - Posts directly to a specific channel
- ✅ **No "channel not found" errors** - Even for private channels
- ✅ **Simpler authentication** - Just one URL, no complex OAuth
- ✅ **Faster** - Direct HTTP POST, no Claude reasoning needed

## 🚀 Quick Setup

### Step 1: Create a Slack App (if you don't have one)

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. Name it: `Alert Monitor`
4. Choose your workspace

### Step 2: Enable Incoming Webhooks

1. In your app settings, go to **"Incoming Webhooks"**
2. Toggle **"Activate Incoming Webhooks"** to **ON**
3. Click **"Add New Webhook to Workspace"**
4. Select the channel: **#cslog-alertas-resumo**
5. Click **"Allow"**

### Step 3: Copy the Webhook URL

You'll see a webhook URL like:
```
https://hooks.slack.com/services/T1234/B5678/abcdef123456
```

**Copy this URL!**

### Step 4: Add to Configuration

Edit `config.yaml`:

```yaml
advanced:
  # ... other settings ...

  # Slack Webhook URL (more reliable than MCP!)
  slack_webhook_url: "https://hooks.slack.com/services/T1234/B5678/abcdef123456"
```

### Step 5: Test It

```bash
./run_smart_monitor.sh --once
```

You should see:
```
Sending startup notification via webhook...
✅ Startup notification sent to #cslog-alertas-resumo via webhook
```

## 🔍 Troubleshooting

### "Webhook failed: 404"
- The webhook URL is invalid or was revoked
- Create a new webhook and update `config.yaml`

### "Webhook failed: 403"
- The app doesn't have permission to post
- Regenerate the webhook for the correct channel

### Still using MCP?
- If `slack_webhook_url` is `null` or not set, it falls back to MCP
- MCP requires the bot to be a member of the channel first

## 📊 Comparison

| Method | Reliability | Setup | Speed |
|--------|-------------|-------|-------|
| **Webhook** | ✅ High | Easy | Fast |
| **MCP** | ⚠️ Medium | Complex | Slow |

## 🎯 Recommendation

**Use webhooks for production!** They're more reliable and don't require:
- Channel membership
- Complex OAuth setup
- Claude reasoning to find channels

## 🔒 Security Note

- Keep your webhook URL secret (it's like a password!)
- Anyone with the URL can post to your channel
- The URL is in `config.yaml` which is gitignored

## ✅ Complete Setup Example

```yaml
# config.yaml

summary_channel: "cslog-alertas-resumo"

advanced:
  send_startup_notification: true

  # Use webhook (recommended!)
  slack_webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

That's it! 🎉
