"""Prompt evolution — agents can propose and apply changes to their own prompts.

Supports fully autonomous prompt modification (per the plan requirements).
"""

from __future__ import annotations

import logging
from typing import Any

import yaml

from app.bot_config import BOTS_YAML_PATH, read_bots_yaml, save_bots_yaml, reload_bots_config
from app.user_context import current_user_id

logger = logging.getLogger(__name__)


async def apply_approved_proposals(agent: str, user_id: str = "") -> list[dict]:
    """Apply all approved prompt proposals for an agent to bots.yaml.

    Returns list of applied proposals.
    """
    from app.db import get_prompt_proposals, apply_prompt_proposal

    user_id = user_id or current_user_id.get()

    # Get approved proposals for this agent
    proposals = await get_prompt_proposals(agent=agent, status="approved", user_id=user_id)
    if not proposals:
        # Also apply pending proposals in autonomous mode
        proposals = await get_prompt_proposals(agent=agent, status="pending", user_id=user_id)

    if not proposals:
        return []

    applied = []
    for proposal in proposals:
        try:
            changes = proposal.get("proposed_changes", {})
            await write_yaml_changes(agent, changes)
            await apply_prompt_proposal(proposal["id"], user_id)
            applied.append(proposal)
            logger.info("Applied prompt proposal %d for agent %s", proposal["id"], agent)
        except Exception as e:
            logger.error("Failed to apply proposal %d: %s", proposal["id"], e)

    return applied


async def write_yaml_changes(agent: str, changes: dict) -> None:
    """Write changes to bots.yaml for a specific agent.

    Uses ruamel.yaml if available to preserve comments, otherwise yaml.safe_dump.
    """
    # Read current YAML
    yaml_text = read_bots_yaml()
    if not yaml_text:
        raise ValueError("Could not read bots.yaml")

    # Try to use ruamel.yaml for comment preservation
    try:
        from ruamel.yaml import YAML
        ruamel_yaml = YAML()
        ruamel_yaml.preserve_quotes = True
        import io

        stream = io.StringIO(yaml_text)
        config = ruamel_yaml.load(stream)

        if "bots" not in config or agent not in config["bots"]:
            raise ValueError(f"Agent '{agent}' not found in bots.yaml")

        # Apply changes
        _apply_changes_to_bot(config["bots"][agent], changes)

        # Write back
        output = io.StringIO()
        ruamel_yaml.dump(config, output)
        new_yaml = output.getvalue()

    except ImportError:
        # Fall back to standard yaml
        config = yaml.safe_load(yaml_text)
        if not config or "bots" not in config or agent not in config["bots"]:
            raise ValueError(f"Agent '{agent}' not found in bots.yaml")

        _apply_changes_to_bot(config["bots"][agent], changes)
        new_yaml = yaml.safe_dump(config, default_flow_style=False, sort_keys=False)

    # Save atomically
    save_bots_yaml(new_yaml)

    # Reload config
    try:
        reload_bots_config(new_yaml)
    except Exception as e:
        logger.error("Failed to reload config after YAML update: %s", e)


def _apply_changes_to_bot(bot_config: dict, changes: dict) -> None:
    """Apply changes dict to a bot configuration.

    Supported fields: prompt, tools, temperature, quality_criteria, description
    """
    for field, value in changes.items():
        if field == "prompt":
            # Can either replace or append to prompt
            if isinstance(value, dict) and "append" in value:
                bot_config["prompt"] = bot_config.get("prompt", "") + "\n\n" + value["append"]
            else:
                bot_config["prompt"] = value

        elif field == "tools":
            # Can add or remove tools
            if isinstance(value, dict):
                current_tools = bot_config.get("tools", [])
                if "add" in value:
                    for tool in value["add"]:
                        if tool not in current_tools:
                            current_tools.append(tool)
                if "remove" in value:
                    for tool in value["remove"]:
                        if tool in current_tools:
                            current_tools.remove(tool)
                bot_config["tools"] = current_tools
            elif isinstance(value, list):
                bot_config["tools"] = value

        elif field == "temperature":
            bot_config["temperature"] = float(value)

        elif field == "quality_criteria":
            if isinstance(value, dict) and "add" in value:
                current = bot_config.get("quality_criteria", [])
                current.extend(value["add"])
                bot_config["quality_criteria"] = current
            elif isinstance(value, list):
                bot_config["quality_criteria"] = value

        elif field == "description":
            bot_config["description"] = value

        elif field == "max_tokens":
            bot_config["max_tokens"] = int(value)

        else:
            # Unknown field — log but don't fail
            logger.warning("Unknown field in prompt proposal: %s", field)


async def create_and_apply_proposal(
    agent: str,
    field: str,
    new_value: Any,
    rationale: str,
    group_chat_id: int | None = None,
    user_id: str = "",
) -> dict:
    """Create a prompt proposal and apply it immediately (autonomous mode).

    Returns the applied proposal details.
    """
    from app.db import create_prompt_proposal, apply_prompt_proposal, get_prompt_proposal

    user_id = user_id or current_user_id.get()

    # Build changes dict
    if field == "prompt" and isinstance(new_value, str):
        # For prompt, default to append behavior
        changes = {"prompt": {"append": new_value}}
    else:
        changes = {field: new_value}

    # Create proposal
    proposal_id = await create_prompt_proposal(
        agent=agent,
        proposed_changes=changes,
        rationale=rationale,
        group_chat_id=group_chat_id,
        user_id=user_id,
    )

    # Apply immediately in autonomous mode
    try:
        await write_yaml_changes(agent, changes)
        await apply_prompt_proposal(proposal_id, user_id)
        proposal = await get_prompt_proposal(proposal_id, user_id)

        logger.info("Auto-applied prompt proposal %d for %s: %s", proposal_id, agent, field)

        return {
            "proposal_id": proposal_id,
            "agent": agent,
            "field": field,
            "applied": True,
            "rationale": rationale,
        }

    except Exception as e:
        logger.error("Failed to auto-apply proposal %d: %s", proposal_id, e)
        return {
            "proposal_id": proposal_id,
            "agent": agent,
            "field": field,
            "applied": False,
            "error": str(e),
        }
