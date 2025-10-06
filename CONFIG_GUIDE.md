# Configuration Guide

## 📝 Unified Configuration

All monitors now use **ONE configuration file**: `config.yaml`

### ✅ What Changed

**Before (Confusing!):**
- ❌ `config.py` - Python config for standard monitor
- ❌ `config.yaml` - YAML config for YAML monitor
- ❌ `smart_config.yaml` - YAML config for smart monitor
- ❌ Duplicate settings everywhere!

**After (Simple!):**
- ✅ `config.yaml` - **ONE** config file for everything
- ✅ `config.py` - Now loads from `config.yaml` (backwards compatible)

### 📁 Configuration File

**Edit only:** `config.yaml`

```yaml
# Channels to monitor
channels:
  - "cslog-alertas*"

# Where to send filtered alerts
summary_channel: "cslog-alertas-resumo"

# Keywords (Portuguese + English)
keywords:
  - "urgente"
  - "crítico"
  - "erro"
  # ... (full list in config.yaml)

# How often to check (seconds)
check_interval: 60  # 1 minute

# Smart Monitor Settings (for intelligent filtering)
smart_filtering:
  min_urgency_level: "IMPORTANT"
  duplicate_window_hours: 24
  recurrence_threshold: 3

# Advanced features
advanced:
  send_startup_notification: true
  smart_database: "smart_alerts.db"
```

## 🚀 Usage

### Standard Monitor
```bash
# Uses config.yaml automatically
./run_with_oauth.sh slack_monitor.py
```

### Smart Monitor (Recommended)
```bash
# Uses config.yaml automatically
./run_smart_monitor.sh

# Or with options
./run_smart_monitor.sh --once
./run_smart_monitor.sh --stats
```

### Custom Config
```bash
# Use a different config file
./run_smart_monitor.sh --config my_config.yaml
```

## 📊 Configuration Sections

### Base Settings (Used by all monitors)
- `channels`: Which channels to monitor
- `summary_channel`: Where to send alerts
- `keywords`: Alert keywords
- `check_interval`: How often to check
- `importance_rules`: Custom rules for Claude

### Smart Filtering (Used only by Smart Monitor)
```yaml
smart_filtering:
  min_urgency_level: "IMPORTANT"    # or "CRITICAL"
  duplicate_window_hours: 24        # Don't resend within 24h
  recurrence_threshold: 3           # Alert after 3 occurrences
```

### Advanced Options
```yaml
advanced:
  send_startup_notification: true   # Send "Monitor started" message
  smart_database: "smart_alerts.db" # Database for smart monitor
  database: "slack_messages.db"     # Database for standard monitor
  verbose: true                     # Detailed logging
```

## 🔄 Migration

If you had custom settings in old config files:

1. **All settings are now in `config.yaml`** ✅
2. **`config.py` now loads from `config.yaml`** (backwards compatible)
3. **Old files backed up** (not deleted, just not used)

## 📝 Editing Configuration

```bash
# Edit the main config
nano config.yaml

# Test your changes
./run_smart_monitor.sh --once

# Run continuously
./run_smart_monitor.sh
```

## ❓ FAQ

**Q: Do I need multiple config files?**
A: No! Just edit `config.yaml`

**Q: What about config.py?**
A: It still works (loads from config.yaml automatically)

**Q: What about smart_config.yaml?**
A: No longer needed - settings are in `config.yaml` under `smart_filtering` section

**Q: Can I use different settings for standard vs smart monitor?**
A: Both use the same base settings. Smart monitor has additional `smart_filtering` options.

## 🎯 Quick Reference

| File | Purpose | Edit? |
|------|---------|-------|
| `config.yaml` | **Main config** | ✅ Yes! |
| `config.py` | Loads from config.yaml | ❌ No |
| `smart_config.yaml` | Old (deprecated) | ❌ No |
| `config_example.py` | Old example | ❌ No |

**Bottom line:** Edit `config.yaml` for all configuration! 🎉
