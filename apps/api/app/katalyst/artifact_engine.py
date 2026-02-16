"""Artifact CRUD with versioning.

When an artifact is updated, the old version gets status SUPERSEDED
and a new version is created. This preserves full history.
"""

from __future__ import annotations

import logging

from app.katalyst import db as kat_db
from app.event_bus import event_bus

logger = logging.getLogger(__name__)


async def create_artifact(
    reaction_id: int,
    title: str,
    content: str,
    artifact_type: str = "document",
    agent: str = "",
    workstream_id: int | None = None,
    metadata: dict | None = None,
    user_id: str = "",
) -> dict:
    """Create a new artifact and emit event."""
    artifact = await kat_db.create_artifact(
        reaction_id=reaction_id,
        title=title,
        artifact_type=artifact_type,
        content=content,
        agent=agent,
        workstream_id=workstream_id,
        metadata=metadata,
        user_id=user_id,
    )

    await kat_db.create_event(
        reaction_id=reaction_id,
        event_type="artifact_created",
        agent=agent,
        message=f"Created artifact: {title}",
        data={"artifact_id": artifact["id"], "type": artifact_type},
        user_id=user_id,
    )

    await event_bus.publish({
        "type": "katalyst_artifact_created",
        "reaction_id": reaction_id,
        "artifact_id": artifact["id"],
        "title": title,
    })

    return artifact


async def update_artifact_content(
    artifact_id: int,
    new_content: str,
    agent: str = "",
    user_id: str = "",
) -> dict | None:
    """Update an artifact by creating a new version.

    The old version gets SUPERSEDED status. A new row is created
    with incremented version number.
    """
    current = await kat_db.get_artifact(artifact_id, user_id)
    if not current:
        return None

    # Supersede old version
    await kat_db.update_artifact(artifact_id, user_id, status="superseded")

    # Create new version
    new_artifact = await kat_db.create_artifact(
        reaction_id=current["reaction_id"],
        title=current["title"],
        artifact_type=current.get("artifact_type", "document"),
        content=new_content,
        agent=agent or current.get("agent", ""),
        workstream_id=current.get("workstream_id"),
        metadata={
            **(current.get("metadata") or {}),
            "previous_version_id": artifact_id,
        },
        user_id=user_id,
    )

    # Update version number
    new_version = current.get("version", 1) + 1
    await kat_db.update_artifact(new_artifact["id"], user_id, version=new_version)

    await kat_db.create_event(
        reaction_id=current["reaction_id"],
        event_type="artifact_updated",
        agent=agent,
        message=f"Updated artifact: {current['title']} (v{new_version})",
        data={"artifact_id": new_artifact["id"], "version": new_version,
              "previous_id": artifact_id},
        user_id=user_id,
    )

    await event_bus.publish({
        "type": "katalyst_artifact_updated",
        "reaction_id": current["reaction_id"],
        "artifact_id": new_artifact["id"],
        "version": new_version,
    })

    return await kat_db.get_artifact(new_artifact["id"], user_id)
