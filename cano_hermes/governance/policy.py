from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from cano_hermes.domain.enums import RiskLevel

SENSITIVE_ACTIONS={"paid_api","publish","deploy","send_external_message","delete","merge","credential_change","production_write"}
SAFE_DRY_RUN_ACTIONS={"read","plan","search_local","simulate","validate","test"}

@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str

class PermissionEngine:
    def __init__(self, execution_mode: str="dry_run") -> None:
        self.execution_mode=execution_mode
    def evaluate_action(self, action: str, risk: RiskLevel=RiskLevel.LOW) -> PolicyDecision:
        if self.execution_mode=="dry_run" and action not in SAFE_DRY_RUN_ACTIONS:
            return PolicyDecision(False, True, "dry-run blocks side effects")
        if action in SENSITIVE_ACTIONS or risk in {RiskLevel.HIGH,RiskLevel.CRITICAL}:
            return PolicyDecision(False, True, "sensitive action requires human approval")
        return PolicyDecision(True, False, "allowed by current policy")
    def evaluate(self, action: str, risk: RiskLevel=RiskLevel.LOW) -> PolicyDecision:
        return self.evaluate_action(action, risk)
    @staticmethod
    def validate_path(target: Path, allowed_roots: list[Path]) -> bool:
        resolved=target.resolve()
        return any(resolved==root.resolve() or root.resolve() in resolved.parents for root in allowed_roots)
