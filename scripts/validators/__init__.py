"""C1 (plan de conexiones) -- paquete de validadores en vivo.

Contrato común, obligatorio para toda entrada de `registry.VALIDATORS`:

    def validate(env: Mapping[str, str]) -> dict

que SIEMPRE devuelve un dict con exactamente estas claves:

    status: "✓" | "✗" | "—" | "policy-skip"
    detail: str            -- nunca contiene un valor de llave
    latency_ms: int | None -- None si no se hizo red (ausente/placeholder/policy-skip)
    quota: dict | None     -- solo si el endpoint la devuelve gratis (DeepL, ElevenLabs,
                              HeyGen, OpenRouter, Firecrawl...); nunca valores de llave

y que NUNCA levanta una excepción: cualquier error de red, timeout, JSON invalido o
sorpresa del proveedor se captura aquí mismo y se convierte en `status="—"` con el
nombre de la clase de excepción como detalle (nunca el cuerpo crudo de la respuesta,
que podría traer texto reflejado con datos sensibles).

`status="policy-skip"` es una cuarta variante fuera de la terna ✓/✗/— de
`connection_matrix.classify()`: la usan validadores para los que ningún chequeo con
red es seguro (Kie, Higgsfield, Modal -- ver `registry.py`). El reporte los muestra
aparte, nunca como fallo.

`is_placeholder`/`strip_quotes`/`PLACEHOLDER_VALUES` viven aquí -- y no en
`connection_matrix.py` -- para que ambos módulos compartan una sola definición sin
imports circulares: `connection_matrix.py` importa de este paquete, nunca al revés.
"""
from __future__ import annotations

import json as _json
import re
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from urllib import error, request

Result = dict  # {"status": str, "detail": str, "latency_ms": int | None, "quota": dict | None}
Validator = Callable[[Mapping[str, str]], Result]

STATUS_OK = "✓"
STATUS_FAIL = "✗"
STATUS_UNKNOWN = "—"
STATUS_POLICY_SKIP = "policy-skip"

# -- placeholder/blank detection (única definición del repo, ver docstring) ----------
PLACEHOLDER_VALUES = {
    "xxx", "xxxx", "xxxxx", "xxxxxxxx", "todo", "change_me", "changeme",
    "your_key_here", "your_api_key_here", "replace_me", "replaceme",
    "placeholder", "fixme", "example", "dummy", "n/a", "na", "none", "null",
}
ALL_X_RE = re.compile(r"^x+$", re.IGNORECASE)


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def is_placeholder(value: str) -> bool:
    v = value.strip().strip("'\"").lower()
    if not v:
        return False  # vacio se maneja aparte (ver is_usable)
    if v in PLACEHOLDER_VALUES:
        return True
    if ALL_X_RE.match(v):
        return True
    if "your_" in v and "_here" in v:
        return True
    return "changeme" in v or "change_me" in v


def result(status: str, detail: str, latency_ms: int | None = None,
           quota: dict | None = None) -> Result:
    return {"status": status, "detail": detail, "latency_ms": latency_ms, "quota": quota}


def is_usable(env: Mapping[str, str], name: str) -> bool:
    v = env.get(name, "")
    return bool(v.strip()) and not is_placeholder(v)


def pick_candidate(env: Mapping[str, str], names: Sequence[str]) -> str | None:
    """Primer nombre de `names` presente y con pinta de valor real -- mismo patrón
    "primera candidata utilizable" que ya usaba `check_apify`."""
    for n in names:
        if is_usable(env, n):
            return n
    return None


def http_get(url: str, headers: dict | None = None, timeout: int = 5):
    """GET sin levantar jamas. Devuelve (status_code|None, body_bytes|None,
    error_detail|None, latency_ms). `error_detail` solo se llena si no hubo
    respuesta HTTP en absoluto (timeout, DNS, conexion rechazada, etc)."""
    req = request.Request(url, method="GET")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    start = time.monotonic()
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            latency = int((time.monotonic() - start) * 1000)
            return resp.getcode(), body, None, latency
    except error.HTTPError as e:
        latency = int((time.monotonic() - start) * 1000)
        try:
            body = e.read()
        except Exception:  # noqa: BLE001 -- leer el cuerpo de un error nunca debe tumbar el validador
            body = None
        return e.code, body, None, latency
    except (error.URLError, TimeoutError, OSError) as e:
        latency = int((time.monotonic() - start) * 1000)
        return None, None, e.__class__.__name__, latency
    except Exception as e:  # noqa: BLE001 -- contrato del paquete: nunca levanta
        latency = int((time.monotonic() - start) * 1000)
        return None, None, e.__class__.__name__, latency


def parse_json(body: bytes | None) -> Any:
    if not body:
        return None
    try:
        return _json.loads(body.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError):
        return None


def no_key_result(names: Sequence[str]) -> Result:
    label = names[0] if len(names) == 1 else f"ninguna de {', '.join(names)}"
    return result(STATUS_UNKNOWN, f"sin llave utilizable en el vault ({label})")


def policy_skip(reason: str) -> Validator:
    """Fabrica un validador que nunca hace red -- para proveedores donde CUALQUIER
    chequeo posible es facturable o requiere un CLI no-HTTP (Kie, Higgsfield, Modal)."""
    def validate(env: Mapping[str, str]) -> Result:
        return result(STATUS_POLICY_SKIP, reason)
    return validate


def presence_only(names: Sequence[str], reason: str) -> Validator:
    """Fabrica un validador que solo confirma presencia/placeholder -- para
    proveedores sin endpoint gratuito de verificación confirmado."""
    def validate(env: Mapping[str, str]) -> Result:
        candidate = pick_candidate(env, names)
        if candidate is None:
            return no_key_result(names)
        return result(STATUS_OK, f"presente en vault (`{candidate}`), sin verificar en vivo -- {reason}")
    return validate
