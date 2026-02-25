# Jira Refinement Agent

AI-powered Jira ticket refinement — turns rough tickets into sprint-ready specs via an agentic LLM loop that interacts with Jira through MCP tools.

## How it works

1. PM creates a rough Jira ticket
2. Jira Automation sends a webhook → this service
3. Service runs an LLM agent loop that autonomously:
   - Reads the ticket via MCP (`jira_get_issue`)
   - Searches for related issues (`jira_search`)
   - Posts clarifying questions + draft spec as a comment (`jira_add_comment`)
4. PM replies → webhook fires again → agent:
   - Reads the PM's feedback
   - Updates the ticket description with final spec (`jira_update_issue`)
   - Creates subtasks (`jira_create_issue`)
5. PM moves to "Ready for Dev"

## Architecture

The service uses the [mcp-atlassian](https://github.com/sooperset/mcp-atlassian) MCP server
as a bridge to Jira. The LLM (via OpenAI function-calling) decides which Jira tools
to invoke at each step, making the refinement flow flexible and context-aware.

```
Jira Automation → Webhook → Agent Loop ↔ LLM (GPT-4o)
                                ↕
                         MCP Client (stdio)
                                ↕
                     mcp-atlassian subprocess
                                ↕
                         Jira REST API
```

## Quick start

```bash
# Install dependencies
uv sync

# Configure
cp .env.example .env
# Edit .env with your Jira + OpenAI credentials

# Run
uv run uvicorn app.main:app --reload --port 8001

# Test
uv sync --extra dev
uv run pytest tests/ -v
```

## Jira Automation setup

### Rule A – On ticket creation / label "Needs Refinement"
- **Trigger:** Issue created OR label = "Needs Refinement"
- **Action:** Send web request
  - URL: `https://your-service.com/jira/refine`
  - Method: POST
  - Headers: `X-Webhook-Secret: <your secret>`
  - Body:
    ```json
    {"issue_key": "{{issue.key}}", "mode": "first_pass"}
    ```

### Rule B – On PM comment (while waiting)
- **Trigger:** Comment added
- **Condition:** `Refinement state = WAITING_FOR_PM` AND commenter ≠ bot
- **Action:** Send web request
  - URL: `https://your-service.com/jira/refine`
  - Method: POST
  - Headers: `X-Webhook-Secret: <your secret>`
  - Body:
    ```json
    {"issue_key": "{{issue.key}}", "mode": "pm_feedback", "pm_comment": "{{comment.body}}"}
    ```

## Project structure

```
jira-refinement-agent/
├── app/
│   ├── api/webhook.py             # POST /jira/refine endpoint
│   ├── core/config.py             # Settings from env vars
│   ├── context/retriever.py       # RAG stub (returns empty list)
│   ├── jira/mcp_client.py         # MCP client — talks to mcp-atlassian
│   ├── llm/
│   │   ├── client.py              # OpenAI LLM caller (JSON + function-calling)
│   │   └── prompts.py             # System prompts (agent + structured)
│   ├── models/
│   │   ├── domain.py              # Domain config model
│   │   └── jira_models.py         # Webhook + LLM response models
│   ├── services/
│   │   └── refinement_service.py  # Agent loop orchestration
│   └── main.py                    # FastAPI app
├── tests/
├── domain_config.yaml             # Customize per project
├── pyproject.toml
├── Dockerfile
└── .env.example
```
