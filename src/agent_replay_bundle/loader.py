"""Loader utilities for Agent Replay Bundle."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .ingress import load_json_bounded
from .models import AgentReplayBundle


def load_replay_bundle(path: str | Path) -> AgentReplayBundle:
    """Load an AgentReplayBundle from a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        A validated AgentReplayBundle instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        InputBoundsError: If the file exceeds the byte budget or nesting limit
            (a ValueError subclass).
        ValueError: If the file contains invalid JSON or an object that repeats a member name
            (``DuplicateMemberError``).
        ValueError: If the JSON does not match the AgentReplayBundle schema.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Replay bundle file not found: {path}")

    try:
        payload = load_json_bounded(path)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in replay bundle file '{path}': {exc}") from exc

    return load_replay_bundle_json(payload)


def load_replay_bundle_json(payload: dict) -> AgentReplayBundle:
    """Load an AgentReplayBundle from a parsed JSON dictionary.

    Args:
        payload: A dictionary representing the bundle.

    Returns:
        A validated AgentReplayBundle instance.

    Raises:
        ValueError: If the payload does not match the AgentReplayBundle schema.
    """
    try:
        return AgentReplayBundle.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Replay bundle failed model validation: {exc}") from exc


def dump_replay_bundle(bundle: AgentReplayBundle, path: str | Path) -> Path:
    """Write an AgentReplayBundle to a JSON file.

    Args:
        bundle: The bundle to write.
        path: Destination file path.

    Returns:
        The resolved Path where the bundle was written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(bundle.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path.resolve()
