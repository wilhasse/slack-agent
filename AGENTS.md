# Repository Guidelines

## Project Structure & Module Organization
Core Python entry points live in the repo root: `slack_chat.py` (interactive Claude chat), `slack_monitor.py` / `slack_monitor_yaml.py` (legacy Claude monitors), and `smart_monitor_cli.py` (new realtime + digest pipeline). Helper scripts (`setup.sh`, `run_with_oauth.sh`, `run_smart_monitor.sh`) stay nearby for quick launches. The Go transport sits in `slack-mcp-server/`; rebuild its binary whenever that folder changes. Defaults land in `config.yaml`, extended references live in `docs/`, and diagnostics such as `test_slack_tools.py` and `diagnose.py` remain top-level for fast access.

## Build, Test, and Development Commands
```bash
./setup.sh                     # create venv and install Python deps
go build -buildvcs=false -o slack-mcp-server/slack-mcp-server ./slack-mcp-server/cmd/slack-mcp-server
source venv/bin/activate       # enter the virtualenv
./run_with_oauth.sh            # launch interactive agent (OAuth-aware wrapper)
./run_smart_monitor.sh --mode realtime   # start realtime detector
./run_smart_monitor.sh --mode digest     # generate a digest immediately
./run_smart_monitor.sh --stats           # quick DB statistics
python diagnose.py             # verify Slack connectivity and tooling
python test_slack_tools.py     # exercise MCP tools end-to-end (requires tokens)
```
Keep workflows scriptable—add new entry points as small shell helpers when possible.

## Coding Style & Naming Conventions
Follow PEP 8: 4-space indents, snake_case functions, concise docstrings. Prefer pathlib over os.path and await async calls explicitly. Shell scripts should stay POSIX-friendly with lowercase-hyphen names. YAML configs use lowercase keys; comment inline when tweaking thresholds. Reuse the existing CLI emoji style rather than inventing new patterns.

## Testing Guidelines
Activate the venv and export Slack credentials (`.env.oauth` is preferred) before running anything. `python test_slack_tools.py` performs the full MCP round-trip and will prompt for optional channel input. Quicker checks include `python test_sdk.py`, `python config_loader.py`, and `python diagnose.py` to validate SDK wiring, config parsing, and environment health. Place new test scripts beside the current ones and document any manual setup they expect.

## Commit & Pull Request Guidelines
Commit messages stay imperative and capitalized (`Fix duplicate responses`, `Add summary channel support`). Keep changes focused, cite key files in the body, and link issues when relevant. Pull requests should outline behavior changes, flag required config tweaks, and attach before/after CLI output when user-visible. Run the commands above before opening a review.

## Security & Configuration Tips
Never commit secrets—`.env.oauth`, exported tokens, and SQLite databases are already gitignored; extend ignores for any new artifacts. Prefer OAuth tokens to browser cookies and call out manual credential steps in PR notes. When adjusting `config.yaml` or Smart Monitor thresholds, provide safe defaults and a quick rollback path for reviewers.
