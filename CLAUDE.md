# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when collaborating on this repository.

## High-Level Architecture

```
┌───────────────────┐     ┌─────────────────────┐     ┌────────────────────┐
│ realtime_monitor  │──▶──│ monitoring/storage │──▶──│ monitoring/digest  │
│ (Slack API + heur.)│     │  (SQLite alerts)    │     │  (periodic summary) │
└───────────────────┘     └─────────────────────┘     └────────────────────┘
           │                         │                          │
           │                         │                          │
           ▼                         ▼                          ▼
      Slack SDK               Alert analytics             Notifications
   (poll or Socket)         recurrence checks           (Slack, WhatsApp)
```

### Key Modules

- `monitoring/configuration.py` – loads `config.yaml`, supports both the new schema and a compatibility shim for the legacy config.
- `monitoring/models.py` – shared dataclasses (severity levels, channel rules, runtime config, alert records).
- `monitoring/storage.py` – SQLite wrapper responsible for schema creation, dedupe lookups, cursor tracking, and statistics.
- `monitoring/slack_client.py` – async wrapper around `slack_sdk.WebClient` for history queries and posting messages directly.
- `monitoring/classifier.py` – deterministic classifier (channel severity hints, keyword boosts, recurrence window).
- `monitoring/llm.py` – optional thin HTTP client for calling cheaper LLM endpoints when heuristics need backup.
- `monitoring/notifications.py` – Slack webhook/chat posting and WhatsApp delivery via Twilio.
- `monitoring/realtime.py` – realtime worker that polls Slack, classifies messages, persists decisions, and triggers critical notifications.
- `monitoring/digest.py` – periodic digest builder that reads from SQLite and posts summaries (optionally refined by an LLM).
- `smart_monitor_cli.py` – unified CLI entry point (`--mode realtime|digest|both`, `--once`, `--stats`, etc.).

### Runtime Flow

1. **Realtime Monitor**
   - Polls Slack channels defined in `config.yaml` (`slack.channels` list).
   - Uses `HeuristicClassifier` to label severity (IGNORE/NORMAL/IMPORTANT/CRITICAL).
   - Recurrence detection performed via `AlertStore.count_recent_occurrences` with per-channel thresholds.
   - Optional LLM call (`realtime_monitor.llm`) can override borderline decisions if enabled.
   - Persists every decision in SQLite (`alerts`, `decision_log`) and triggers notifications when severity ≥ configured threshold.

2. **Digest Generator**
   - Runs ad-hoc or scheduled (external scheduler/cron).
   - Pulls recent alerts from SQLite (`lookback_minutes`).
   - Builds Markdown digest highlighting counts and recent high-severity events.
   - Optionally sends digest through a secondary LLM for nicer prose (`digest.llm`).

3. **Notifications**
   - Slack: either incoming webhook (`notifications.slack_webhook`) or Web API via bot token.
   - WhatsApp: Twilio credentials from `notifications.whatsapp` or `whatsapp.txt` helper; automatically normalised.
   - Email hooks are stubbed for future use (config preserved but no sender built yet).

## Configuration Cheatsheet (`config.yaml`)

```yaml
slack:
  bot_token_env: SLACK_BOT_TOKEN
  summary_channel: cslog-alertas-resumo
  summary_channel_id: C09KQ5L2SF2
  critical_channel: cslog-alertas-grave

channels:
  - id: C09AR0R9DG9
    label: cslog-alertas-mc
    severity_hint: NORMAL    # default severity when no other signals
    recurrence_threshold: 5   # promote to CRITICAL after N hits in window
    critical_keywords: ["urgent", "indisponível", "timeout"]
    ignore_patterns: []

notifications:
  slack_webhook: null        # set to use webhook instead of chat.postMessage
  whatsapp:
    enabled: true
    service_file: whatsapp.txt
    auth_token_env: TWILIO_AUTH_TOKEN

realtime_monitor:
  enabled: true
  check_interval_seconds: 30
  severity_threshold: IMPORTANT
  duplicate_window_minutes: 60
  lookback_minutes: 120      # window used when counting duplicates
  llm:
    enabled: false

digest:
  enabled: true
  interval_minutes: 30
  lookback_minutes: 30
  include_filtered: true
  llm:
    enabled: false

database: smart_alerts.db
prompt_log_path: logs/claude_prompts.log
```

### Legacy Compatibility

`monitoring/configuration.load_runtime_config` transparently converts the old schema (with `smart_filtering`, `smart_summary`, etc.) into the new runtime dataclasses. This allows gradual migration while the new realtime pipeline coexists with remaining scripts (`slack_monitor.py`, `slack_chat.py`).

## Development Workflow

```bash
./setup.sh                    # create venv, install deps (slack_sdk, httpx, etc.)
source venv/bin/activate

# Run realtime loop continuously
./run_smart_monitor.sh --mode realtime

# Dry-run realtime single poll
./run_smart_monitor.sh --mode realtime --once

# Generate a single digest
./run_smart_monitor.sh --mode digest

# Get quick stats
./run_smart_monitor.sh --stats --hours 12
```

SQLite file lives at `smart_alerts.db` by default, shared by both monitors. `monitoring/storage.py` exposes helper methods for pruning (`AlertStore.purge_old_alerts`).

## Coding Guidelines

- Keep new logic inside the `monitoring/` package to maintain modularity.
- Prefer deterministic heuristics for realtime classification; only call LLMs when strictly necessary.
- For new notification targets, extend `NotificationManager` rather than inlining network calls elsewhere.
- Always update `requirements.txt` when introducing third-party dependencies (currently `slack_sdk`, `httpx`, `pyyaml`, `python-dotenv`).
- Tests: integrate simple unit tests under `tests/` (future improvement) that exercise classifier and storage methods with in-memory SQLite (`:memory:`).

## Deprecation Notes

- Legacy `smart_slack_monitor.py` has been removed in favour of the new split architecture.
- `config_loader.py` remains for backwards compatibility but should be phased out once remaining scripts switch to `monitoring.configuration`.
- Documentation in `docs/SMART_MONITOR.md` still references the previous design; update as new features stabilise.

Happy monitoring! 🚀
