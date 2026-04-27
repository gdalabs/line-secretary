# Line Secretary — AI Secretary Agent for LINE

A LINE Bot that acts as your AI-powered secretary agent. It manages tasks across multiple projects, looks up project details on demand, and holds natural conversations — all through LINE messages.

## How It Works

```
You (LINE message) → "Add a task to web-app: fix the login redirect bug"
Secretary Agent    → "✅ Done! Added 'fix the login redirect bug' to web-app 🔧 Anything else?"
```

Unlike simple chatbots, Line Secretary is a **tool-use agent** — it autonomously decides when to create tasks, look up project info, or just chat naturally. Powered by Claude's tool use API.

## Architecture

```
LINE Bot → Webhook (FastAPI) → Claude Agent (Haiku 4.5 + tool use)
                                    ↓
                              Tool execution loop
                              ├─ create_task
                              ├─ list_tasks
                              ├─ complete_task
                              ├─ get_project_info
                              └─ get_pending_summary
                                    ↓
                              Final response → LINE push message
```

## Agent Tools

| Tool | Description |
|---|---|
| `list_tasks` | List tasks filtered by project/status |
| `create_task` | Create a new task in a project |
| `complete_task` | Mark a task as done |
| `get_project_info` | Read project details (CLAUDE.md) |
| `get_pending_summary` | Overview of all pending tasks |

The agent runs a loop: it calls tools as needed, processes results, and continues until it has a final text response for the user.

## Conversation Examples

### Task management — natural language in, action out

```
You:   "Fix the auth token refresh on mobile-api"
Agent: "✅ Got it! Added 'fix auth token refresh' to mobile-api 🔧 Need anything else?"

You:   "What tasks are still open?"
Agent: "📋 Here's what's pending:
        web-app: 2 tasks
        data-pipeline: 1 task
        Want to see details for any of these?"

You:   "Mark #7 as done"
Agent: "🎉 Nice! Task #7 is done! You're crushing it 💪"
```

### Project lookup — the agent reads your docs on demand

```
You:   "What does data-pipeline do again?"
Agent: "📖 Here's what data-pipeline is about:
        It handles ETL jobs, syncs data to the warehouse,
        and generates daily analytics reports.
        Built with Python + Airflow 🛠️"
```

### Casual chat — not everything is a task

```
You:   "Good morning!"
Agent: "Morning! ☀️ Ready to get things done — what's on the agenda today?"

You:   "Ugh, long day..."
Agent: "Hang in there 😮‍💨 You've been putting in solid work. Take a breather!"
```

## Why an Agent, Not Just an API Call?

| | Regular Bot | Direct API call | **Line Secretary (Agent)** |
|---|---|---|---|
| Task management | Keyword matching (`/add`, `/list`) | Single prompt → single response | Autonomous — understands intent, picks the right tool |
| Multi-step actions | Not possible | Manual chaining by developer | Agent loop handles it (e.g., "add task then show summary") |
| Project awareness | None | Only what's in the prompt | Reads project docs on demand via tools |
| Conversation | Rigid commands | Stateless (no memory) | Remembers last 10 messages, natural dialogue |
| Personality | Robotic | Depends on prompt, but dry | Friendly, encouraging, team-member feel |
| Extensibility | Rewrite code for each feature | Rewrite prompt | Just add a tool definition + handler |

### The key difference: tool use

A regular API call is **one-shot** — you send a prompt, get a response, done.

An agent with tool use is a **loop** — the model can decide to call tools (create a task, look something up), see the results, and then respond. This means it can handle requests like _"add a task to web-app and then show me the full pending summary"_ in a single conversation turn, autonomously chaining multiple actions.

```
Regular API:    prompt → response (that's it)
Agent:          prompt → [tool call → result → tool call → result → ...] → response
```

## Tech Stack

- **Runtime**: Python 3 + FastAPI + uvicorn
- **Database**: SQLite (aiosqlite)
- **AI**: Anthropic Claude API (Haiku 4.5 with tool use)
- **Messaging**: LINE Messaging API
- **Hosting**: Any server (systemd service included)

## Setup

### Prerequisites

- Python 3.11+
- [Anthropic API key](https://console.anthropic.com/settings/keys)
- [LINE Developers account](https://developers.line.biz/console/)

### 1. Clone & Install

```bash
git clone https://github.com/gdalabs/line-secretary.git
cd line-secretary
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your keys:
#   LINE_CHANNEL_SECRET=...
#   LINE_CHANNEL_ACCESS_TOKEN=...
#   ANTHROPIC_API_KEY=...
```

### 3. Initialize Database

```bash
mkdir -p data
python3 -c "import asyncio; from db import init_db; asyncio.run(init_db())"
```

### 4. Run

```bash
# Development
uvicorn main:app --host 127.0.0.1 --port 3939 --reload

# Production (systemd)
sudo cp secretary-hub.service /etc/systemd/system/
sudo systemctl enable --now secretary-hub
```

### 5. Configure LINE Webhook

Expose your server via tunnel (cloudflared, ngrok, etc.) and set the webhook URL in LINE Developers Console.

## Customization

### Add Projects

Edit `config.py` to add your own projects:

```python
PROJECTS = {
    "my-project": "Description of your project",
    # ...
}
```

### Add Tools

Add new tools in `agent.py`:
1. Define the tool schema in `TOOLS` list
2. Add handler in `_execute_tool()`

### Adjust Personality

Edit the `SYSTEM_PROMPT` in `agent.py` to change the agent's personality and behavior.

## Cost

Uses Claude Haiku 4.5 — extremely cost-effective:

| Usage | Messages/day | Monthly cost |
|---|---|---|
| Light | 10-20 | ~$3-5 |
| Normal | 30-50 | ~$5-15 |
| Heavy | 100+ | ~$15-30 |

## License

MIT

## Author

[GDA Labs](https://gdalabs.github.io/website/)
