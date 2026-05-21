# 🔥 self-annealing

> Persistent error memory for AI-assisted development.  
> Stop re-debugging the same issues. Every fix is saved, every session starts smarter.

## The Problem
AI coding agents (like Claude Code, Cursor, Windsurf, Aider) have no memory between session boundaries. 
You fix a bug on Monday, hit the same bug on Thursday in a different session, and spend 20 minutes and 2,000 tokens re-diagnosing and re-solving the exact same issue.

`self-annealing` provides a drop-in persistent error memory, health check tool, and secret scanner to keep your project development streamlined and save valuable LLM tokens.

## How It Works
```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  Agent Session  │ ────> │  reads CLAUDE.md │ ────> │ checks error_log│
└─────────────────┘       └─────────────────┘       └────────┬────────┘
                                                             │
                                                  ┌──────────▼──────────┐
                                                  │  0 LLM tokens wasted│
                                                  └─────────────────────┘
```

## Quick Start

1. Install the tool:
```bash
pip install -e .
```

2. Initialize in your project:
```bash
cd your-project
anneal init
```
This creates `CLAUDE.md` and `error_log.md` in your project root using the templates.

3. Run project health checks:
```bash
anneal health
```

4. Search your error memory:
```bash
anneal search "connection refused" --context "database"
```

## Commands

| Command | Usage | Description |
|---------|-------|-------------|
| `init` | `anneal init` | Bootstraps `CLAUDE.md` and `error_log.md` templates in the current directory |
| `search` | `anneal search "<symptom>" [--context "<context>"]` | Searches and ranks error log memory by relevance (`HIGH`, `MEDIUM`, `LOW`) |
| `health` | `anneal health` | Runs 5 project health checks (port binding, `.gitignore`, `.env`, build spec, secret leak) |
| `log` | `anneal log --id <ID> --symptom "<msg>" --cause "<cause>" --fix "<fix>" --context "<context>" --tokens <N>` | Logs a new resolved error entry to your memory |
| `stats` | `anneal stats` | Prints error resolution memory statistics and tokens saved |
| `list` | `anneal list` | Lists all non-template recorded errors |

### Health Checks

- **HC001**: **PORT binding check** - Scans python files for hardcoded ports (3000, 5000, 8000, 8080) without env fallback.
- **HC002**: **`.env` in `.gitignore`** - Ensures `.env` files are not accidentally checked into git.
- **HC003**: **`.env` files check** - Verifies `.env` exists, is not empty, and `.env.example` exists.
- **HC004**: **Build files check** - Checks that `requirements.txt` or `pyproject.toml` exists in the project root.
- **HC005**: **Secret scanner** - Runs regex scanning to identify leaked API keys (Anthropic, OpenAI) or hardcoded credentials.

## CLI Usage Examples

### Log a new error:
```bash
anneal log --id E007 --symptom "Connection refused on :5432" \
           --cause "PostgreSQL not running" \
           --fix "sudo systemctl start postgresql" \
           --context "database" --tokens 450
```

### Search memory:
```bash
anneal search "rc=5" --context "mqtt"
```
Output:
```
E001 | HIGH | [TEMPLATE] MQTT rc=5 auth failure
  → Cause: Invalid credentials provided to the MQTT broker
  → Fix: Check MQTT_USER and MQTT_PASS in .env
```

### Show Statistics:
```bash
anneal stats
```
Output:
```
6 entries | 1,950 tokens saved | Last modified: just now
```

## Built for
- Claude Code users
- Cursor / Windsurf / Aider users
- Anyone using AI agents for coding
- Solo developers managing multiple projects

## 🛠️ MCP Server Integration

`self-annealing` includes a built-in **Model Context Protocol (MCP)** server so you can connect its tools directly to clients like **Claude Desktop**, **Cursor**, or **Antigravity**.

### Tools Exposed via MCP:
- `anneal_init`: Initialize error memory and rules in the project workspace.
- `anneal_search(query_symptom, query_context)`: Query error history.
- `anneal_health`: Run project diagnostics.
- `anneal_log(entry_id, symptom, cause, fix, context, tokens)`: Log a new fix.
- `anneal_stats`: View token-saving and entry statistics.
- `anneal_list`: List logged errors.

### Configuration

#### Claude Desktop
Add this to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "self-annealing": {
      "command": "python",
      "args": [
        "-m",
        "self_annealing.mcp"
      ]
    }
  }
}
```
*(Make sure to run this in the environment where the package is installed, or add its folder to `PYTHONPATH` in the config)*

#### Cursor
Go to **Settings -> Features -> MCP**, click **+ Add New MCP Server**:
- **Name**: `self-annealing`
- **Type**: `command`
- **Command**: `python -m self_annealing.mcp`

---

## License
MIT
