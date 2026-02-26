"""
LLM prompt templates for first-pass refinement and PM feedback processing.

Includes both structured-output prompts (original) and agent-mode prompts
that instruct the LLM to use MCP tools.
"""

from app.models.domain import DomainConfig

# ── System prompts (agent mode) ────────────────────────

AGENT_SYSTEM_FIRST_PASS = """\
You are a senior product analyst AI assistant that helps product managers \
refine rough Jira tickets into sprint-ready specifications.

## Your tools
You have access to Jira tools (via MCP) to read and write issue data. \
Use them to gather context and post your refinement output.

## Your workflow (first_pass mode)
1. **Read the issue** — use `jira_get_issue` to fetch the ticket data.
2. **Search for similar tickets** — use `jira_search` with a JQL query \
   to find related or similar issues in the same project for style reference.
3. **Analyze** — identify what information is missing or ambiguous.
4. **Post your analysis** — use `jira_add_comment` to post a comment on the \
   issue with:
   - 3–7 focused, numbered clarifying questions for the PM
   - A draft specification following the required ticket structure
   - Proposed acceptance criteria
   - (Optional) suggested subtasks if the ticket is large
5. **Update refinement state** — if a custom field for refinement state exists, \
   use `jira_update_issue` to set it to "WAITING_FOR_PM".

## Rules
- Keep questions specific and actionable — don't ask vague questions.
- The draft spec should be as complete as possible given the information. \
  Mark uncertain parts with "[TBD — see question N]".
- Acceptance criteria should be concrete and testable.
- Write in clear, professional language.
- Format the comment in markdown for readability.

After you have completed ALL steps, respond with a brief summary of what you did.
"""

AGENT_SYSTEM_FEEDBACK = """\
You are a senior product analyst AI assistant. The PM has answered your \
clarifying questions and may have requested wording changes.

## Your tools
You have access to Jira tools (via MCP) to read and write issue data.

## Your workflow (pm_feedback mode)
1. **Read the issue** — use `jira_get_issue` to fetch the current ticket and comments.
2. **Incorporate PM feedback** — use the PM's comment to refine the specification:
   - Remove all "[TBD]" placeholders.
   - Apply any wording changes the PM requested.
   - Produce the final, complete specification.
3. **Update the issue description** — use `jira_update_issue` to replace the description \
   with the final specification including acceptance criteria.
4. **Create subtasks** — if the ticket warrants breakdown, use `jira_create_issue` to \
   create sub-tasks linked to the parent issue.
5. **Post a summary comment** — use `jira_add_comment` to post a comment summarizing \
   what was updated. If anything is still unclear, include follow-up questions.
6. **Update refinement state** — use `jira_update_issue` to set the refinement state: \
   "COMPLETE" if done, or "WAITING_FOR_PM" if follow-up questions remain.

## Rules
- Be concise but thorough.
- Keep the same ticket structure template.
- Format all content in markdown.

After you have completed ALL steps, respond with a brief summary of what you did.
"""


# ── Structured output prompts (kept for backward compat) ──

SYSTEM_FIRST_PASS = """\
You are a senior product analyst AI assistant that helps product managers \
refine rough Jira tickets into sprint-ready specifications.

## Your task
Given a rough ticket and project context, you must:
1. Identify what information is missing or ambiguous.
2. Generate 3–7 focused, numbered clarifying questions for the PM.
3. Draft a complete specification following the required ticket structure.
4. Suggest acceptance criteria.
5. Optionally suggest subtasks if the ticket is large.

## Rules
- Keep questions specific and actionable — don't ask vague questions.
- The draft spec should be as complete as possible given the information available. \
  Mark uncertain parts with "[TBD — see question N]".
- Acceptance criteria should be concrete and testable.
- Write in clear, professional language.
- Output ONLY valid JSON matching the schema below.
"""

SYSTEM_FEEDBACK = """\
You are a senior product analyst AI assistant. The PM has answered your \
clarifying questions and may have requested wording changes.

## Your task
1. Incorporate the PM's answers into the specification.
2. Apply any wording changes the PM requested.
3. Produce the final, complete specification following the required ticket structure.
4. Produce final acceptance criteria.
5. Decide whether subtasks should be created (set create_subtasks=true if so).
6. If anything is still unclear, include follow-up questions. \
   If everything is clear, leave followup_questions empty.

## Rules
- Remove all "[TBD]" placeholders — fill them in using the PM's answers.
- Keep the same ticket structure template.
- Be concise but thorough.
- Output ONLY valid JSON matching the schema below.
"""


# ── Agent-mode prompt builders ─────────────────────────


def build_agent_prompt(
    issue_key: str,
    mode: str,
    pm_comment: str | None,
    domain_config: DomainConfig,
) -> list[dict]:
    """Build the messages array for the agent-mode LLM call.

    The LLM will use MCP tools to interact with Jira directly.
    """
    if mode == "first_pass":
        system = AGENT_SYSTEM_FIRST_PASS + _domain_context(domain_config)
        user_content = (
            f"Please refine Jira issue **{issue_key}**.\n\n"
            f"Start by reading the issue with the `jira_get_issue` tool, "
            f"then follow the workflow described in your instructions."
        )
    else:  # pm_feedback
        system = AGENT_SYSTEM_FEEDBACK + _domain_context(domain_config)
        user_content = (
            f"The PM has replied to the refinement of **{issue_key}**.\n\n"
            f"**PM's comment:**\n{pm_comment or '(no comment provided)'}\n\n"
            f"Start by reading the issue with `jira_get_issue` to see the "
            f"current state, then incorporate the PM's feedback."
        )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


# ── Structured output prompt builders (original) ──────


def build_first_pass_prompt(
    ticket_fields: dict,
    similar_tickets: list[dict],
    domain_config: DomainConfig,
) -> list[dict]:
    """Build the messages array for the first-pass LLM call."""
    system = SYSTEM_FIRST_PASS + _domain_context(domain_config) + _json_schema_hint("first_pass")

    user_content = f"""## Ticket to refine

**Summary:** {ticket_fields.get("summary", "N/A")}

**Description:**
{ticket_fields.get("description", "(no description provided)")}

**Type:** {ticket_fields.get("issuetype", {}).get("name", "N/A")}
**Priority:** {ticket_fields.get("priority", {}).get("name", "N/A")}
**Labels:** {", ".join(ticket_fields.get("labels", [])) or "none"}
"""

    # Add similar tickets for context if available
    if similar_tickets:
        user_content += "\n## Similar past tickets (for style reference)\n\n"
        for i, t in enumerate(similar_tickets[:3], 1):
            user_content += (
                f"### Example {i}: {t.get('summary', '')}\n"
                f"{t.get('description', '')}\n\n"
            )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def build_feedback_prompt(
    original_description: str,
    previous_spec: str,
    pm_comment: str,
    similar_tickets: list[dict],
    domain_config: DomainConfig,
) -> list[dict]:
    """Build the messages array for the PM-feedback LLM call."""
    system = SYSTEM_FEEDBACK + _domain_context(domain_config) + _json_schema_hint("feedback")

    user_content = f"""## Original rough description
{original_description or "(none)"}

## Previously proposed specification
{previous_spec}

## PM's response
{pm_comment}
"""

    if similar_tickets:
        user_content += "\n## Similar past tickets (for style reference)\n\n"
        for i, t in enumerate(similar_tickets[:3], 1):
            user_content += (
                f"### Example {i}: {t.get('summary', '')}\n"
                f"{t.get('description', '')}\n\n"
            )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


# ── Internal helpers ────────────────────────────────────


def _domain_context(config: DomainConfig) -> str:
    """Format domain config into a prompt section."""
    sections = "\n".join(f"  - {s}" for s in config.ticket_structure)
    personas = "\n".join(
        f"  - **{p.name}**: {p.description}" for p in config.user_personas
    )
    platforms = ", ".join(config.platforms) if config.platforms else "N/A"
    standards = "\n".join(
        f"  - **{k}**: {v}" for k, v in config.standards.items()
    )

    context = f"""

## Project context: {config.project_name}
"""

    # Repo context (if configured)
    if config.repo_url:
        context += f"\n### Repository: {config.repo_url}\n"

    if config.tech_stack:
        tech = "\n".join(f"  - {t}" for t in config.tech_stack)
        context += f"\n### Tech stack:\n{tech}\n"

    if config.architecture_notes:
        context += f"\n### Architecture:\n{config.architecture_notes}\n"

    if config.key_modules:
        modules = "\n".join(
            f"  - **{m.name}** (`{m.path}`): {m.description}"
            for m in config.key_modules
        )
        context += f"\n### Key modules:\n{modules}\n"

    context += f"""
### Required ticket structure (use these as markdown headings):
{sections}

### Known user personas:
{personas or "  (none defined)"}

### Target platforms: {platforms}

### Non-functional standards:
{standards or "  (none defined)"}

### Acceptance criteria style: {config.acceptance_criteria_style}
"""

    return context


def _json_schema_hint(mode: str) -> str:
    """Append the expected JSON output schema to the system prompt."""
    if mode == "first_pass":
        return """

## Required JSON output format
```json
{
  "questions": ["Question 1", "Question 2", "..."],
  "proposed_description": "Full markdown description...",
  "proposed_acceptance_criteria": ["AC 1", "AC 2", "..."],
  "proposed_subtasks": [
    {"summary": "Subtask title", "description": "Details"}
  ]
}
```
"""
    return """

## Required JSON output format
```json
{
  "final_description_markdown": "Full markdown description...",
  "final_acceptance_criteria": ["AC 1", "AC 2", "..."],
  "create_subtasks": true,
  "subtasks": [
    {"summary": "Subtask title", "description": "Details"}
  ],
  "followup_questions": ["Any remaining question, or empty list"]
}
```
"""
