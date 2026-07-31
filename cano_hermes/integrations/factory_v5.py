from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FactoryRequest:
    action: str
    channel: str
    payload: dict[str, Any]
    approval_required: bool = True


class FactoryV5Adapter:
    """Contract-only adapter. The external Factory V5 repository stays independent."""

    ALLOWED_ACTIONS = {
        "analyze_reference",
        "generate_storyboard",
        "render_preview",
        "request_approval",
        "sync_analytics",
    }

    def prepare(self, request: FactoryRequest) -> dict[str, Any]:
        if request.action not in self.ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported Factory V5 action: {request.action}")
        return {
            "contract": "factory-v5/1.0",
            "mode": "dry_run",
            "action": request.action,
            "channel": request.channel,
            "payload": request.payload,
            "approval_required": request.approval_required,
        }
