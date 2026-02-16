"""Prep materials tool: generate and save interview prep materials."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def generate_prep_materials(
    material_type: str,
    title: str,
    content: str,
    company: str = "",
    role: str = "",
    resources: str = "[]",
    scheduled_date: str = "",
    agent_source: str = "",
) -> str:
    """Save structured prep materials (interview prep, system design, LeetCode plans,
    company research) to the database for display on the Prep page.

    Call this tool at the end of your analysis to persist prep materials so the user
    can review them later on the Prep page.

    Args:
        material_type: Type of material — "interview", "system_design", "leetcode", "company_research", or "general".
        title: A descriptive title for the material (e.g. "Amazon SDE2 Interview Prep").
        content: JSON string containing the structured content. Structure depends on type.
        company: Company name if applicable.
        role: Target role if applicable.
        resources: JSON array of resource objects [{title, url, type}].
        scheduled_date: ISO date string for scheduled prep (e.g. "2024-03-15").
        agent_source: Name of the agent that created this material.

    Returns:
        JSON with saved status and material_id.
    """
    valid_types = ("interview", "system_design", "leetcode", "company_research", "general")
    if material_type not in valid_types:
        return json.dumps({"error": f"Invalid material_type. Must be one of: {', '.join(valid_types)}"})

    try:
        # Validate content is valid JSON
        try:
            content_parsed = json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError:
            # If not valid JSON, wrap the string as a content object
            content_parsed = {"text": content}

        # Validate resources
        try:
            resources_parsed = json.loads(resources) if isinstance(resources, str) else resources
            if not isinstance(resources_parsed, list):
                resources_parsed = []
        except json.JSONDecodeError:
            resources_parsed = []

        from app.db import create_prep_material
        material_id = await create_prep_material(
            material_type=material_type,
            title=title[:500],
            content=content_parsed,
            company=company[:200] if company else None,
            role=role[:200] if role else None,
            agent_source=agent_source[:100] if agent_source else None,
            resources=resources_parsed,
            scheduled_date=scheduled_date[:50] if scheduled_date else None,
        )

        return json.dumps({
            "saved": True,
            "material_id": material_id,
            "material_type": material_type,
            "title": title,
            "message": f"Prep material '{title}' saved (id={material_id})",
        })
    except Exception as e:
        logger.error("generate_prep_materials error: %s", e)
        return json.dumps({"error": f"Failed to save prep material: {e}"})
