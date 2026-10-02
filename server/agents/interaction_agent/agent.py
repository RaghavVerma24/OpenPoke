"""Interaction agent helpers for prompt construction."""

from html import escape
from pathlib import Path
from typing import Dict, List

from ...services.execution import get_agent_roster, get_execution_agent_logs
from ...services.execution.router import AgentRouter, profiles_from_roster

_prompt_path = Path(__file__).parent / "system_prompt.md"
SYSTEM_PROMPT = _prompt_path.read_text(encoding="utf-8").strip()


# Load and return the pre-defined system prompt from markdown file
def build_system_prompt() -> str:
    """Return the static system prompt for the interaction agent."""
    return SYSTEM_PROMPT


# Build structured message with conversation history, active agents, and current turn
def prepare_message_with_history(
    latest_text: str,
    transcript: str,
    message_type: str = "user",
) -> List[Dict[str, str]]:
    """Compose a message that bundles history, roster, and the latest turn."""
    sections: List[str] = []

    sections.append(_render_conversation_history(transcript))
    sections.append(f"<active_agents>\n{_render_active_agents(latest_text)}\n</active_agents>")
    sections.append(_render_current_turn(latest_text, message_type))

    content = "\n\n".join(sections)
    return [{"role": "user", "content": content}]


# Format conversation transcript into XML tags for LLM context
def _render_conversation_history(transcript: str) -> str:
    history = transcript.strip()
    if not history:
        history = "None"
    return f"<conversation_history>\n{history}\n</conversation_history>"


# Format currently active execution agents into XML tags for LLM awareness
def _render_active_agents(query: str) -> str:
    roster = get_agent_roster()
    roster.load()
    agents = roster.get_agents()

    if not agents:
        return "None"

    # Read a compact request summary per agent and expose only a fixed-size candidate set.
    import os
    try:
        top_k = min(5, max(1, int(os.getenv("OPENPOKE_AGENT_ROUTER_TOP_K", "4"))))
        threshold = min(1.0, max(0.0, float(os.getenv("OPENPOKE_AGENT_ROUTER_THRESHOLD", "0.29"))))
    except ValueError:
        top_k, threshold = 4, 0.29
    candidates = AgentRouter(top_k=top_k, threshold=threshold).route(
        query, profiles_from_roster(agents, get_execution_agent_logs())
    ).candidates
    if not candidates:
        return "No existing agent appears relevant. Create a new agent for a genuinely new task; do not reuse an unrelated one."

    rendered: List[str] = []
    for profile in candidates:
        name = escape(profile.name or "agent", quote=True)
        description = escape(profile.description[:240], quote=True)
        rendered.append(f'<agent name="{name}" description="{description}" />')

    return "\n".join(rendered)


# Wrap the current message in appropriate XML tags based on sender type
def _render_current_turn(latest_text: str, message_type: str) -> str:
    tag = "new_agent_message" if message_type == "agent" else "new_user_message"
    body = latest_text.strip()
    return f"<{tag}>\n{body}\n</{tag}>"
