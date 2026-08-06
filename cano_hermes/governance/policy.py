from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from cano_hermes.domain.enums import RiskLevel

# K10 (plan HERMES-KICKOFF): "browser_with_session" marca cualquier tarea que
# use el toolset `browser` (agent-browser) contra un dominio con
# sesion/login -- no un simple GET publico como el smoke test a
# example.com. Riesgo MEDIUM como minimo, nunca auto-aprobable (ver
# docs/OPERATIONS.md, seccion "Browser automation"). Por eso vive en
# SENSITIVE_ACTIONS: cualquier accion listada aqui fuerza
# requires_approval=True sin importar el RiskLevel calculado (ver
# evaluate_action abajo). Todavia no hay nada que *detecte*
# automaticamente "esta tarea de browser toca un dominio con sesion" y
# emita esta accion -- ese motor de clasificacion es K12. Por ahora esto
# es solo la anotacion/contrato: cuando K12 exista, ya tiene aqui el
# nombre de accion correcto para enchufarse sin tocar este archivo de nuevo.
SENSITIVE_ACTIONS={"paid_api","publish","deploy","send_external_message","delete","merge","credential_change","production_write","browser_with_session"}
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
