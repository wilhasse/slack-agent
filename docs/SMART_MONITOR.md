# Smart Slack Monitor (v2)

> **Note:** The project has been refactored to use a hybrid architecture: deterministic heuristics + optional low-cost LLMs (for realtime alerts) and an optional digest generator. This document still references the Claude-only implementation; update sections gradually as the new pipeline stabilises.

## 🎯 The Problem

Standard Slack monitors send **every** alert that matches keywords, leading to:
- 📢 **Channel pollution** with duplicate and redundant alerts
- 😫 **Alert fatigue** from too many notifications
- ⏰ **Noise** that obscures truly urgent issues
- 🔁 **Duplicate alerts** for the same recurring issue

## ✨ The Solution: Smart Filtering

The Smart Slack Monitor adds **intelligence** on top of message analysis:

1. **Deduplication**: Never sends the same alert twice within a time window
2. **Pattern Detection**: Identifies recurring issues and only alerts when threshold is met
3. **Urgency Filtering**: Only sends CRITICAL or IMPORTANT alerts (configurable)
4. **Historical Analysis**: Compares with previous alerts to identify what's new
5. **Claude Decision**: Uses AI to make final calls on borderline cases

### How It Works

```
Slack Messages
    ↓
Claude Analysis (classify importance)
    ↓
Smart Filtering:
  ✓ Is it urgent enough? (CRITICAL/IMPORTANT)
  ✓ Have we seen this before? (dedup)
  ✓ Is it recurring? (pattern detection)
  ✓ Should we send it? (Claude decision)
    ↓
Only Truly Important Alerts → Summary Channel
```

## 🚀 Quick Start

### 1. Setup

```bash
# If you haven't already set up the base system
./setup.sh
source .env.oauth

# Create configuration
cp smart_config_example.yaml smart_config.yaml
nano smart_config.yaml  # Edit with your settings
```

### 2. Configure

Edit `smart_config.yaml`:

```yaml
# Which channels to monitor
channels:
  - "cslog-alertas*"
  - "prod-incidents"

# Where to send filtered alerts
summary_channel: "cslog-alertas-summary"

# Filtering rules
filtering:
  min_urgency_level: "IMPORTANT"    # Only send IMPORTANT or CRITICAL
  duplicate_window_hours: 24        # Don't resend within 24h
  recurrence_threshold: 3           # Alert after 3 occurrences
```

### 3. Run

```bash
# Test run (check once)
./run_smart_monitor.sh --once

# Monitor continuously
./run_smart_monitor.sh

# Show statistics
./run_smart_monitor.sh --stats
```

## 📊 Features

### 1. Deduplication

**Problem**: Same error message appears 50 times in an hour
**Solution**: Only send the first occurrence within configurable window

```yaml
filtering:
  duplicate_window_hours: 24  # Don't resend within 24 hours
```

### 2. Pattern Detection

**Problem**: API timeout happens 100 times but floods the channel
**Solution**: Detect the pattern, alert after N occurrences

```yaml
filtering:
  recurrence_threshold: 3  # Alert after 3 occurrences
```

Example:
- Error #1: Database timeout → Logged, not sent
- Error #2: Database timeout → Logged, not sent
- Error #3: Database timeout → **ALERT SENT** (recurrent issue!)

### 3. Urgency Filtering

**Problem**: Channel gets flooded with NORMAL priority messages
**Solution**: Only send messages above threshold

```yaml
filtering:
  min_urgency_level: "IMPORTANT"  # or "CRITICAL"
```

### 4. Claude Decision Making

For borderline cases, Claude makes the final call based on:
- Is this a real problem requiring human attention?
- Is this routine/automated noise?
- Does this contain actionable information?
- Is this truly new information?

### 5. Historical Analysis

All alerts are stored in SQLite database with:
- Content hash (for deduplication)
- Pattern signature (for recurrence detection)
- Send/skip decisions (for learning)
- Timestamps (for time-based filtering)

## 📋 Configuration Options

### Minimum Configuration

```yaml
channels:
  - "your-channel"

summary_channel: "filtered-alerts"

filtering:
  min_urgency_level: "IMPORTANT"
```

### Full Configuration

```yaml
channels:
  - "cslog-alertas*"
  - "prod-*"
  - "incidents"

keywords:
  - "urgent"
  - "critical"
  - "error"
  - "down"

check_interval: 300  # 5 minutes

summary_channel: "cslog-alertas-summary"

filtering:
  min_urgency_level: "IMPORTANT"      # CRITICAL, IMPORTANT, NORMAL, IGNORE
  duplicate_window_hours: 24          # Don't resend within 24h
  recurrence_threshold: 3             # Alert after 3 occurrences
  use_claude_decision: true           # Ask Claude for borderline cases

database: "smart_alerts.db"

importance_rules: |
  Custom rules for our team:
  - Production database errors are CRITICAL
  - API timeouts are IMPORTANT
  - Test environment errors are NORMAL
  - Bot messages are IGNORE
```

## 🎮 Usage Examples

### Example 1: Check Once

```bash
./run_smart_monitor.sh --once
```

Output:
```
🔍 Fetching and analyzing messages...
📋 Found 45 messages to analyze

✅ [CRITICAL] #prod-alerts - Critical alert - sending immediately
⏭️ [IMPORTANT] #prod-incidents - Duplicate alert within 24h window
⏭️ [IMPORTANT] #dev-alerts - Not recurrent enough (1 occurrences)
✅ [IMPORTANT] #api-errors - Recurrent issue (5 occurrences)
⏭️ [NORMAL] #general - Below minimum urgency (IMPORTANT)

✅ Sent 2 filtered alert(s) to #cslog-alertas-summary
```

### Example 2: Monitor Continuously

```bash
./run_smart_monitor.sh
```

Runs every 5 minutes (or configured interval), continuously filtering.

### Example 3: View Statistics

```bash
./run_smart_monitor.sh --stats
```

Output:
```
📊 Smart Monitor Statistics (Last 24h)
======================================================================

📨 Alert Processing:
   Total alerts analyzed:  127
   Sent to Slack:          8 (6.3%)
   Filtered out:           119 (93.7%)

🎯 By Importance:
   Critical:               5
   Important:              23

🔍 Pattern Detection:
   Active patterns:        12

🔝 Top Patterns:
   1. prod-alerts:api-timeout-error    (34 occurrences)
   2. incidents:database-failed        (18 occurrences)
   3. cslog-alertas-prod:error         (15 occurrences)

✨ Filtering Efficiency:
   93.7% of alerts filtered
   Reduced noise by 119 messages
   Channel pollution avoided! 🎉
======================================================================
```

### Example 4: Clear Old Data

```bash
./run_smart_monitor.sh --clear-old --days 60
```

Removes alerts older than 60 days from the database.

## 🔧 Advanced Usage

### Custom Importance Rules

Guide Claude's decision-making with custom rules in `smart_config.yaml`:

```yaml
importance_rules: |
  For our DevOps team:

  CRITICAL means:
  - Production systems are down or degraded
  - Customer-impacting issues
  - Security incidents
  - Data loss or corruption

  IMPORTANT means:
  - Deployment failures
  - High error rates (>10/min)
  - Performance degradation
  - Recurrent issues (3+ times)

  NORMAL means:
  - Informational updates
  - Successful deployments
  - Low-volume errors

  IGNORE means:
  - Test environment noise
  - Bot spam
  - Social chat
```

### Scenario-Based Configurations

**Production-Only Monitoring** (very strict):
```yaml
filtering:
  min_urgency_level: "CRITICAL"
  duplicate_window_hours: 72
  recurrence_threshold: 1
```

**Development Team** (balanced):
```yaml
filtering:
  min_urgency_level: "IMPORTANT"
  duplicate_window_hours: 24
  recurrence_threshold: 3
```

**High-Noise Environment** (aggressive filtering):
```yaml
filtering:
  min_urgency_level: "CRITICAL"
  duplicate_window_hours: 48
  recurrence_threshold: 5
```

## 📊 Database Schema

The smart monitor uses SQLite to track alerts:

### Tables

**alerts**: All analyzed alerts
- `content_hash`: MD5 of normalized message (deduplication)
- `pattern_signature`: Pattern type (e.g., "prod-alerts:api-timeout")
- `sent_to_slack`: Whether we sent it
- `importance`: CRITICAL, IMPORTANT, NORMAL, IGNORE

**patterns**: Pattern occurrence tracking
- `pattern_signature`: Pattern identifier
- `occurrence_count`: How many times seen
- `last_sent`: When we last alerted on this pattern

**decision_log**: Why we sent or skipped each alert
- `decision`: SEND or SKIP
- `reason`: Why we made this decision

### Querying the Database

```bash
sqlite3 smart_alerts.db

# Show all critical alerts
SELECT channel, text, created_at
FROM alerts
WHERE importance = 'CRITICAL'
ORDER BY created_at DESC;

# Show filtering efficiency
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN sent_to_slack THEN 1 ELSE 0 END) as sent,
  ROUND(100.0 * SUM(CASE WHEN NOT sent_to_slack THEN 1 ELSE 0 END) / COUNT(*), 1) as filter_rate
FROM alerts;

# Top patterns
SELECT pattern_signature, occurrence_count
FROM patterns
ORDER BY occurrence_count DESC
LIMIT 10;
```

## 🎯 Comparison: Standard vs Smart Monitor

| Feature | Standard Monitor | Smart Monitor |
|---------|-----------------|---------------|
| **Alerts sent** | Every match | Only urgent/new |
| **Duplicates** | Sent every time | Filtered out |
| **Recurrence** | All occurrences | Threshold-based |
| **Noise level** | High 📢 | Low 🔇 |
| **Channel pollution** | Yes 😫 | No 😌 |
| **False positives** | Many | Few |
| **Alert fatigue** | High | Low |
| **Actionability** | Mixed | High |

### Example: API Timeout Scenario

**Standard Monitor**:
```
10:01 - API timeout in prod
10:03 - API timeout in prod
10:05 - API timeout in prod
10:07 - API timeout in prod
... (sends all 50 occurrences)
```
Result: 50 messages 📢

**Smart Monitor**:
```
10:01 - API timeout (occurrence 1 - logged, not sent)
10:03 - API timeout (occurrence 2 - logged, not sent)
10:05 - API timeout (occurrence 3 - ALERT: recurrent issue!)
... (subsequent ones filtered as duplicates)
```
Result: 1 meaningful alert ✅

## 🔍 Troubleshooting

### No Alerts Being Sent

**Check 1**: Are messages being analyzed?
```bash
./run_smart_monitor.sh --once
```
Look for "Found X messages to analyze"

**Check 2**: Are they all being filtered?
```bash
./run_smart_monitor.sh --stats
```
If filter_rate is 100%, your thresholds might be too strict

**Solution**: Lower thresholds
```yaml
filtering:
  min_urgency_level: "NORMAL"  # More permissive
  recurrence_threshold: 1      # Alert on first occurrence
```

### Too Many Alerts

**Solution**: Increase filtering
```yaml
filtering:
  min_urgency_level: "CRITICAL"  # Only critical
  duplicate_window_hours: 48     # Longer dedup window
  recurrence_threshold: 5        # Higher threshold
```

### Pattern Not Detected

Patterns are based on keywords in message text. Check:
- Does message contain error keywords?
- Is channel name included in pattern?

Debug:
```python
# In monitoring/classifier.py, adjust ChannelRule.critical_keywords
# or add logging inside HeuristicClassifier.classify()
```

## 📚 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Slack Channels                        │
│            (cslog-alertas*, prod-*, etc.)               │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  Slack MCP Server    │
          │  (fetch messages)    │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │   Claude Analysis    │
          │   (classify urgency) │
          └──────────┬───────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│            SMART FILTERING LAYER                        │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Deduplication│  │   Pattern    │  │   Urgency    │ │
│  │   (hash)     │→ │  Detection   │→ │   Filter     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                           ↓                             │
│                  ┌──────────────────┐                  │
│                  │ Claude Decision  │                  │
│                  │  (borderline)    │                  │
│                  └────────┬─────────┘                  │
└───────────────────────────┼─────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
    ┌─────────────────┐        ┌──────────────────┐
    │ SQLite Database │        │ Summary Channel  │
    │  (history)      │        │ (filtered alerts)│
    └─────────────────┘        └──────────────────┘
```

## 🤝 Integration with Existing Monitor

The smart monitor **extends** the base `SlackMonitor` class, so you can:

1. **Replace** your current monitor:
```bash
# Old
python slack_monitor.py

# New
./run_smart_monitor.sh
```

2. **Run in parallel**:
- Keep standard monitor for logging everything
- Use smart monitor for filtered summary channel

3. **Gradual migration**:
- Start with `--once` to test
- Review statistics to tune thresholds
- Deploy continuously when satisfied

## 💡 Best Practices

1. **Start Conservative**: Begin with `min_urgency_level: "CRITICAL"` and expand
2. **Review Statistics**: Check `--stats` weekly to tune thresholds
3. **Use Separate Channel**: Send filtered alerts to dedicated summary channel
4. **Custom Rules**: Add team-specific importance rules
5. **Monitor the Monitor**: Occasionally check filtered-out alerts to ensure nothing missed
6. **Clean Old Data**: Run `--clear-old` monthly to keep database lean

## 📞 Quick Reference

```bash
# Run continuously
./run_smart_monitor.sh

# Test run
./run_smart_monitor.sh --once

# View statistics
./run_smart_monitor.sh --stats

# Stats for last 7 days
./run_smart_monitor.sh --stats --hours 168

# Clear old data
./run_smart_monitor.sh --clear-old --days 60

# Custom config
./run_smart_monitor.sh --config my_config.yaml
```

## 🎉 Success Metrics

After deploying Smart Monitor, you should see:

- ✅ **90%+ filter rate**: Most noise removed
- ✅ **Zero duplicates**: No repeated alerts
- ✅ **High signal**: Only actionable alerts sent
- ✅ **Low fatigue**: Team actually reads the alerts
- ✅ **Clean channel**: Summary channel stays focused

---

**Ready to reduce alert fatigue?** 🚀

```bash
cp smart_config_example.yaml smart_config.yaml
nano smart_config.yaml  # Edit your settings
./run_smart_monitor.sh --once  # Test it
./run_smart_monitor.sh  # Deploy it
```
