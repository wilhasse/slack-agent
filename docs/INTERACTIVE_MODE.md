# Interactive Mode

## Overview

Interactive mode allows you to **talk to Claude** directly in your monitoring channel! Ask questions about recent alerts, request more context, or get summaries - all within Slack.

## How It Works

When interactive mode is enabled, Claude monitors the summary channel (`cslog-alertas-resumo`) for:
- Questions about alerts
- Requests for more information
- Commands or queries about system status

Claude responds with context from the last 24 hours of alert history stored in the database.

## Enable Interactive Mode

In `config.yaml`:

```yaml
smart_filtering:
  # Enable interactive mode
  interactive_mode: true
```

Restart the monitor:
```bash
./run_smart_monitor.sh
```

You'll see this in the startup output:
```
💡 Smart Features:
   ✓ Interactive mode - Ask questions in #cslog-alertas-resumo!
```

## Example Interactions

### Ask About Specific Alerts
**You:** "What was that disk space alert about?"

**Claude:** "💬 @wilhasse: Houve um alerta crítico sobre espaço em disco no servidor daserver 172.22.8.5, com apenas 1490M livres na partição /var. Foi detectado há 2 horas no canal #cslog-alertas-bd."

### Request Status Summary
**You:** "Any critical issues in the last hour?"

**Claude:** "💬 @wilhasse: Sim, tivemos 2 alertas críticos na última hora: um sobre espaço em disco crítico no RENAC e outro sobre alta latência na API de produção."

### Ask for Context
**You:** "Why did we get so many database alerts today?"

**Claude:** "💬 @wilhasse: Identificamos um padrão recorrente de lentidão no banco de dados (5 ocorrências hoje). Parece estar relacionado a queries pesadas durante o horário de pico."

### Get Recommendations
**You:** "What should I prioritize right now?"

**Claude:** "💬 @wilhasse: A prioridade máxima é o alerta de espaço em disco crítico no servidor RENAC (1490M livres). Em segundo lugar, resolver a alta latência na API que está afetando clientes."

## How Claude Responds

Claude's responses are:
- ✅ **Contextual** - Uses recent alert history from database
- ✅ **Concise** - 2-3 sentences max
- ✅ **Bilingual** - Responds in Portuguese if you ask in Portuguese
- ✅ **Actionable** - Focuses on what matters

## Technical Details

### Message Detection
Claude checks the summary channel every 60 seconds (same as monitoring interval) for:
- User messages (ignoring its own bot messages)
- Questions or commands
- Any message that looks like it's directed at the monitoring system

### Context Window
- Last 20 alerts from the database
- Up to 24 hours of history
- Includes importance level, channel, and message preview

### Response Format
```
💬 @username: [Claude's response]
```

## Limitations

- Only monitors the **summary channel** (not all channels)
- **24-hour context window** (older alerts not included)
- **60-second polling** (not instant, checks every minute)
- Responses are **text-only** (no images, files, or attachments)

## Privacy & Security

- Claude only sees messages in channels the bot is invited to
- No data is sent to external services beyond Anthropic's Claude API
- Alert history is stored locally in SQLite database
- You can disable interactive mode anytime in config.yaml

## Disable Interactive Mode

Set in `config.yaml`:
```yaml
smart_filtering:
  interactive_mode: false
```

Claude will stop checking for interactions but continue monitoring alerts normally.

## Tips

1. **Be specific**: "What was the disk space alert on server X?" works better than "Tell me about alerts"
2. **Use Portuguese**: Claude responds in the same language you use
3. **Ask follow-ups**: Claude has context from recent alerts, so you can ask clarifying questions
4. **Commands**: You can say things like "Show me all critical alerts from today"

## Example Use Cases

### During Incidents
```
You: "What's the status of the production API?"
Claude: Reports any related critical/important alerts from last 24h
```

### Morning Standup
```
You: "Anything important overnight?"
Claude: Summarizes critical issues that occurred outside working hours
```

### Root Cause Analysis
```
You: "Were there any alerts before the API went down?"
Claude: Shows preceding alerts that might indicate cause
```

### Trend Analysis
```
You: "How many database alerts have we had today?"
Claude: Counts and summarizes database-related issues
```

## Troubleshooting

**Claude doesn't respond:**
- Check `interactive_mode: true` in config.yaml
- Verify bot is invited to the summary channel
- Wait 60 seconds (polling interval)
- Check console logs for errors

**Responses are generic:**
- Claude only has 24h context
- Older alerts aren't included
- Be more specific in your questions

**Bot responds to its own messages:**
- This is prevented by the code
- If it happens, report as a bug

---

**Created**: 2025-10-06
**Feature**: Interactive Mode v1.0
