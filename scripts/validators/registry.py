"""C1 (plan de conexiones) -- registro único de validadores en vivo.

`VALIDATORS: dict[str, Validator]` es el único punto de registro que usa
`connection_matrix.compute_and_render()`. Cada función documenta en su docstring el
endpoint EXACTO que usa y por qué es gratuito -- ese docstring es la fuente de verdad
que se citó al decidir `live-free` vs `presence-only` vs `policy-skip` en
`config/key_registry.yaml`.

Todas reciben el `env` del VAULT (no de los `.env` de repo -- el vault es la fuente de
verdad de credenciales reales; los `.env` de repo son propagaciones parciales, ese es
justamente el hueco que C2 va a sanear). Ninguna imprime ni registra un valor de
llave: los valores solo se usan para construir headers/URLs de request.
"""
from __future__ import annotations

import base64

from . import (
    STATUS_FAIL,
    STATUS_OK,
    STATUS_UNKNOWN,
    Validator,
    http_get,
    is_usable,
    no_key_result,
    parse_json,
    pick_candidate,
    policy_skip,
    presence_only,
    result,
)


def _classify_http(code, err, latency, *, ok_detail: str) -> dict:
    """Clasificación HTTP estándar para el patrón Bearer -> 200/401/403 que comparten
    la mayoría de estos validadores (OpenAI-compatibles, whoami de un solo GET)."""
    if err:
        return result(STATUS_UNKNOWN, f"error de red: {err}", latency)
    if code == 200:
        return result(STATUS_OK, ok_detail, latency)
    if code in (401, 403):
        return result(STATUS_FAIL, f"llave invalida o sin permiso (HTTP {code})", latency)
    return result(STATUS_UNKNOWN, f"respuesta inesperada HTTP {code}", latency)


# ---------------------------------------------------------------------------------
# Motores LLM / inferencia -- todos "GET /models" estilo OpenAI, o equivalente,
# ninguno genera tokens ni gasta cuota de generación.
# ---------------------------------------------------------------------------------

def validate_openai(env):
    """OpenAI -- GET https://api.openai.com/v1/models (Bearer). Gratis: enumera
    modelos disponibles, no genera tokens."""
    candidate = pick_candidate(env, ["OPENAI_API_KEY"])
    if candidate is None:
        return no_key_result(["OPENAI_API_KEY"])
    code, _body, err, latency = http_get(
        "https://api.openai.com/v1/models",
        {"Authorization": f"Bearer {env[candidate]}"},
    )
    return _classify_http(code, err, latency, ok_detail="200 -- lista de modelos obtenida")


def validate_anthropic(env):
    """Anthropic -- GET https://api.anthropic.com/v1/models (headers `x-api-key` +
    `anthropic-version: 2023-06-01`). Gratis, solo enumera modelos. Hoy
    ANTHROPIC_API_KEY no vive en el vault (solo aparece vacía/comentada en los `.env`
    de repo) -- el validador queda listo para cuando exista."""
    candidate = pick_candidate(env, ["ANTHROPIC_API_KEY"])
    if candidate is None:
        return no_key_result(["ANTHROPIC_API_KEY"])
    code, _body, err, latency = http_get(
        "https://api.anthropic.com/v1/models",
        {"x-api-key": env[candidate], "anthropic-version": "2023-06-01"},
    )
    return _classify_http(code, err, latency, ok_detail="200 -- lista de modelos obtenida")


def validate_kimi_moonshot(env):
    """Kimi / Moonshot -- GET {KIMI_BASE_URL o https://api.moonshot.ai/v1}/models
    (Bearer, API compatible con OpenAI). Crear la llave es gratis y listar modelos no
    consume los créditos prepagados (solo `/chat/completions` factura). Prueba
    KIMI_API_KEY primero, luego MOONSHOT_API_KEY."""
    names = ["KIMI_API_KEY", "MOONSHOT_API_KEY"]
    candidate = pick_candidate(env, names)
    if candidate is None:
        return no_key_result(names)
    base = (env.get("KIMI_BASE_URL") or "https://api.moonshot.ai/v1").rstrip("/")
    code, _body, err, latency = http_get(
        f"{base}/models", {"Authorization": f"Bearer {env[candidate]}"}
    )
    return _classify_http(
        code, err, latency, ok_detail=f"200 -- lista de modelos obtenida (`{candidate}`)"
    )


def validate_openrouter(env):
    """OpenRouter -- GET https://openrouter.ai/api/v1/key (Bearer). Documentado como
    gratis, pensado para monitorear cuota/gasto antes de tocar un límite. Nota: el
    endpoint real vigente es `/api/v1/key` (singular) -- `/api/v1/auth/key` no existe
    en la documentación actual, se corrigió tras verificarlo."""
    candidate = pick_candidate(env, ["OPENROUTER_API_KEY"])
    if candidate is None:
        return no_key_result(["OPENROUTER_API_KEY"])
    code, body, err, latency = http_get(
        "https://openrouter.ai/api/v1/key",
        {"Authorization": f"Bearer {env[candidate]}"},
    )
    if err:
        return result(STATUS_UNKNOWN, f"error de red: {err}", latency)
    if code == 200:
        data = parse_json(body) or {}
        info = data.get("data", data) if isinstance(data, dict) else {}
        quota = None
        if isinstance(info, dict):
            quota = {
                "limit_remaining": info.get("limit_remaining"),
                "is_free_tier": info.get("is_free_tier"),
            }
        return result(STATUS_OK, "200 -- estado de la llave obtenido", latency, quota)
    if code in (401, 403):
        return result(STATUS_FAIL, f"llave invalida (HTTP {code})", latency)
    return result(STATUS_UNKNOWN, f"respuesta inesperada HTTP {code}", latency)


def validate_nvidia_nim(env):
    """NVIDIA NIM -- GET https://integrate.api.nvidia.com/v1/models (Bearer, API
    compatible con OpenAI). Gratis, solo enumera modelos. Estado esperado HOY: 403 --
    la llave del vault está confirmada inválida/rechazada por NVIDIA (ver memoria del
    operador, "NVIDIA key inválida"). Este validador reporta lo que de verdad responde
    el endpoint, sin ocultar el 403 conocido."""
    candidate = pick_candidate(env, ["NVIDIA_NIM_API_KEY"])
    if candidate is None:
        return no_key_result(["NVIDIA_NIM_API_KEY"])
    code, _body, err, latency = http_get(
        "https://integrate.api.nvidia.com/v1/models",
        {"Authorization": f"Bearer {env[candidate]}"},
    )
    if err:
        return result(STATUS_UNKNOWN, f"error de red: {err}", latency)
    if code == 200:
        return result(STATUS_OK, "200 -- lista de modelos obtenida", latency)
    if code in (401, 403):
        return result(
            STATUS_FAIL,
            f"HTTP {code} -- esperado, ver memoria: llave NVIDIA conocida como inválida",
            latency,
        )
    return result(STATUS_UNKNOWN, f"respuesta inesperada HTTP {code}", latency)


def validate_groq(env):
    """Groq -- GET https://api.groq.com/openai/v1/models (Bearer, API compatible con
    OpenAI). Gratis, solo enumera modelos."""
    candidate = pick_candidate(env, ["GROQ_API_KEY"])
    if candidate is None:
        return no_key_result(["GROQ_API_KEY"])
    code, _body, err, latency = http_get(
        "https://api.groq.com/openai/v1/models",
        {"Authorization": f"Bearer {env[candidate]}"},
    )
    return _classify_http(code, err, latency, ok_detail="200 -- lista de modelos obtenida")


def validate_mistral(env):
    """Mistral -- GET https://api.mistral.ai/v1/models (Bearer). Gratis."""
    candidate = pick_candidate(env, ["MISTRAL_API_KEY"])
    if candidate is None:
        return no_key_result(["MISTRAL_API_KEY"])
    code, _body, err, latency = http_get(
        "https://api.mistral.ai/v1/models",
        {"Authorization": f"Bearer {env[candidate]}"},
    )
    return _classify_http(code, err, latency, ok_detail="200 -- lista de modelos obtenida")


def validate_cohere(env):
    """Cohere -- GET https://api.cohere.com/v1/models (Bearer). Gratis. El endpoint
    dedicado `/v1/check-api-key` figura como deprecado en la documentación oficial
    (docs.cohere.com/reference/check-api-key), así que se usa `/v1/models`."""
    candidate = pick_candidate(env, ["COHERE_API_KEY"])
    if candidate is None:
        return no_key_result(["COHERE_API_KEY"])
    code, _body, err, latency = http_get(
        "https://api.cohere.com/v1/models",
        {"Authorization": f"Bearer {env[candidate]}"},
    )
    return _classify_http(code, err, latency, ok_detail="200 -- lista de modelos obtenida")


def validate_gemini(env):
    """Gemini -- GET https://generativelanguage.googleapis.com/v1beta/models?key=<key>.
    Gratis, solo enumera modelos. La llave va en el query string (así lo exige esta API
    de Google) -- nunca se imprime, solo se usa para construir la URL del request."""
    candidate = pick_candidate(env, ["GEMINI_API_KEY"])
    if candidate is None:
        return no_key_result(["GEMINI_API_KEY"])
    code, _body, err, latency = http_get(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={env[candidate]}"
    )
    return _classify_http(code, err, latency, ok_detail="200 -- lista de modelos obtenida")


validate_xai = policy_skip(
    "GET https://api.x.ai/v1/models (Bearer) es el endpoint documentado y en teoría "
    "gratuito, pero el team vinculado a la llave del vault devuelve 403 "
    "'permission-denied' con el mensaje literal 'has either used all available "
    "credits or reached its monthly spending limit... please purchase more credits "
    "or raise your spending limit' -- confirmado en vivo el 2026-08-07, no es llave "
    "invalida (no es 401). xAI exige spending limit/créditos en la cuenta para CUALQUIER "
    "request, incluida esta de solo lectura -- mismo patrón que Replicate a veces exige "
    "(tarjeta en archivo) pero aquí sí bloquea. Resolverlo implica configurar facturación, "
    "fuera de alcance por política de cero gasto -- no es un fallo reparable en el "
    "validador ni una llave para rotar."
)


validate_perplexity = presence_only(
    ["PERPLEXITY_API_KEY", "PERPLEXITY_API_KEY_2"],
    "no existe endpoint documentado de validación sin costo -- verificado en "
    "docs.perplexity.ai: todos los endpoints públicos (Gateway/Agent/Search/chat) son "
    "facturables, no hay whoami/models gratuito",
)


# ---------------------------------------------------------------------------------
# Media / datos -- devuelven cuota cuando el endpoint la trae.
# ---------------------------------------------------------------------------------

def validate_deepl(env):
    """DeepL -- GET /v2/usage. Las llaves free terminan en ':fx' y usan
    api-free.deepl.com; las pro usan api.deepl.com. Documentado en
    developers.deepl.com/docs/api-reference/usage -- consultar el uso no consume
    caracteres de la cuota de traducción."""
    candidate = pick_candidate(env, ["DEEPL_API_KEY"])
    if candidate is None:
        return no_key_result(["DEEPL_API_KEY"])
    key = env[candidate]
    host = "api-free.deepl.com" if key.strip().endswith(":fx") else "api.deepl.com"
    code, body, err, latency = http_get(
        f"https://{host}/v2/usage", {"Authorization": f"DeepL-Auth-Key {key}"}
    )
    if err:
        return result(STATUS_UNKNOWN, f"error de red: {err}", latency)
    if code == 200:
        data = parse_json(body) or {}
        quota = (
            {
                "character_count": data.get("character_count"),
                "character_limit": data.get("character_limit"),
            }
            if isinstance(data, dict)
            else None
        )
        return result(STATUS_OK, "200 -- uso consultado", latency, quota)
    if code in (401, 403):
        return result(STATUS_FAIL, f"llave invalida (HTTP {code})", latency)
    return result(STATUS_UNKNOWN, f"respuesta inesperada HTTP {code}", latency)


def validate_replicate(env):
    """Replicate -- GET https://api.replicate.com/v1/account (Bearer). Gratis, solo
    lectura del perfil."""
    candidate = pick_candidate(env, ["REPLICATE_API_TOKEN"])
    if candidate is None:
        return no_key_result(["REPLICATE_API_TOKEN"])
    code, _body, err, latency = http_get(
        "https://api.replicate.com/v1/account",
        {"Authorization": f"Bearer {env[candidate]}"},
    )
    return _classify_http(code, err, latency, ok_detail="200 -- cuenta obtenida")


def validate_elevenlabs(env):
    """ElevenLabs -- GET https://api.elevenlabs.io/v1/user (header `xi-api-key`).
    Gratis -- consultar el perfil/suscripción no consume créditos de audio."""
    names = ["ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY_2"]
    candidate = pick_candidate(env, names)
    if candidate is None:
        return no_key_result(names)
    code, body, err, latency = http_get(
        "https://api.elevenlabs.io/v1/user", {"xi-api-key": env[candidate]}
    )
    if err:
        return result(STATUS_UNKNOWN, f"error de red: {err}", latency)
    if code == 200:
        data = parse_json(body) or {}
        sub = data.get("subscription", {}) if isinstance(data, dict) else {}
        quota = (
            {
                "character_count": sub.get("character_count"),
                "character_limit": sub.get("character_limit"),
            }
            if sub
            else None
        )
        return result(STATUS_OK, f"200 -- perfil obtenido (`{candidate}`)", latency, quota)
    if code in (401, 403):
        return result(STATUS_FAIL, f"llave invalida (HTTP {code})", latency)
    return result(STATUS_UNKNOWN, f"respuesta inesperada HTTP {code}", latency)


def validate_heygen(env):
    """HeyGen -- GET https://api.heygen.com/v2/user/remaining_quota (header
    `x-api-key`). Documentado en docs.heygen.com/reference/get-remaining-quota-v2;
    consultar la cuota no la consume."""
    candidate = pick_candidate(env, ["HEYGEN_API_KEY"])
    if candidate is None:
        return no_key_result(["HEYGEN_API_KEY"])
    code, body, err, latency = http_get(
        "https://api.heygen.com/v2/user/remaining_quota", {"x-api-key": env[candidate]}
    )
    if err:
        return result(STATUS_UNKNOWN, f"error de red: {err}", latency)
    if code == 200:
        data = parse_json(body) or {}
        payload = data.get("data", data) if isinstance(data, dict) else {}
        quota = (
            {"remaining_quota": payload.get("remaining_quota")}
            if isinstance(payload, dict)
            else None
        )
        return result(STATUS_OK, "200 -- cuota consultada", latency, quota)
    if code in (401, 403):
        return result(STATUS_FAIL, f"llave invalida (HTTP {code})", latency)
    return result(STATUS_UNKNOWN, f"respuesta inesperada HTTP {code}", latency)


def validate_pexels(env):
    """Pexels -- GET https://api.pexels.com/v1/search?query=test&per_page=1 (header
    `Authorization: <key>`, sin prefijo "Bearer"). Gratis, límite generoso (200
    req/hora en el tier gratuito) -- una búsqueda de 1 resultado no lo agota."""
    candidate = pick_candidate(env, ["PEXELS_API_KEY"])
    if candidate is None:
        return no_key_result(["PEXELS_API_KEY"])
    code, _body, err, latency = http_get(
        "https://api.pexels.com/v1/search?query=test&per_page=1",
        {"Authorization": env[candidate]},
    )
    return _classify_http(code, err, latency, ok_detail="200 -- búsqueda de prueba ok")


def validate_pixabay(env):
    """Pixabay -- GET https://pixabay.com/api/?key=<key>&q=test. Gratis, dentro del
    límite generoso del tier gratuito (5000 req/hora)."""
    candidate = pick_candidate(env, ["PIXABAY_API_KEY"])
    if candidate is None:
        return no_key_result(["PIXABAY_API_KEY"])
    code, _body, err, latency = http_get(
        f"https://pixabay.com/api/?key={env[candidate]}&q=test"
    )
    return _classify_http(code, err, latency, ok_detail="200 -- búsqueda de prueba ok")


def validate_cloudinary(env):
    """Cloudinary -- GET https://api.cloudinary.com/v1_1/{cloud_name}/usage (Basic
    auth `api_key:api_secret`). Es el endpoint documentado de consulta de plan/créditos
    -- no ejecuta transformaciones ni consume créditos por sí mismo."""
    names = ["CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET", "CLOUDINARY_CLOUD_NAME"]
    if not all(is_usable(env, n) for n in names):
        return no_key_result(names)
    cloud = env["CLOUDINARY_CLOUD_NAME"]
    basic = base64.b64encode(
        f"{env['CLOUDINARY_API_KEY']}:{env['CLOUDINARY_API_SECRET']}".encode()
    ).decode()
    code, body, err, latency = http_get(
        f"https://api.cloudinary.com/v1_1/{cloud}/usage",
        {"Authorization": f"Basic {basic}"},
    )
    if err:
        return result(STATUS_UNKNOWN, f"error de red: {err}", latency)
    if code == 200:
        data = parse_json(body) or {}
        credits = data.get("credits", {}) if isinstance(data, dict) else {}
        quota = (
            {"used": credits.get("usage"), "limit": credits.get("limit")}
            if credits
            else None
        )
        return result(STATUS_OK, "200 -- uso consultado", latency, quota)
    if code in (401, 403):
        return result(STATUS_FAIL, f"credenciales inválidas (HTTP {code})", latency)
    return result(STATUS_UNKNOWN, f"respuesta inesperada HTTP {code}", latency)


# ---------------------------------------------------------------------------------
# Herramientas / búsqueda / scraping.
# ---------------------------------------------------------------------------------

def validate_firecrawl(env):
    """Firecrawl -- GET https://api.firecrawl.dev/v2/team/credit-usage (Bearer).
    Documentado en docs.firecrawl.dev/api-reference/endpoint/credit-usage; consultar
    créditos restantes NO consume créditos (ese es el propósito del endpoint)."""
    candidate = pick_candidate(env, ["FIRECRAWL_API_KEY"])
    if candidate is None:
        return no_key_result(["FIRECRAWL_API_KEY"])
    code, body, err, latency = http_get(
        "https://api.firecrawl.dev/v2/team/credit-usage",
        {"Authorization": f"Bearer {env[candidate]}"},
    )
    if err:
        return result(STATUS_UNKNOWN, f"error de red: {err}", latency)
    if code == 200:
        data = parse_json(body) or {}
        info = data.get("data", data) if isinstance(data, dict) else {}
        quota = (
            {
                "remaining_credits": info.get("remainingCredits"),
                "plan_credits": info.get("planCredits"),
            }
            if isinstance(info, dict) and "remainingCredits" in info
            else None
        )
        return result(STATUS_OK, "200 -- créditos consultados", latency, quota)
    if code in (401, 403):
        return result(STATUS_FAIL, f"llave invalida (HTTP {code})", latency)
    return result(STATUS_UNKNOWN, f"respuesta inesperada HTTP {code}", latency)


validate_exa = presence_only(
    ["EXA_API_KEY"],
    "el único endpoint de cuenta documentado (\"Get API Key Usage\", "
    "docs.exa.ai/reference/team-management/get-api-key-usage) exige el ID de la llave "
    "-- no solo el secreto -- y vive bajo team-management (scope de owner); sin un "
    "whoami simple confirmado, no se implementa como live-free",
)

validate_rapidapi = presence_only(
    ["RAPIDAPI_KEY"],
    "sin endpoint gratuito y documentado de whoami/perfil confirmado tras revisar "
    "docs.rapidapi.com -- la Subscriptions API real vive bajo el Platform API (GraphQL) "
    "con credenciales de partner distintas a la llave de consumidor X-RapidAPI-Key; "
    "implementarlo a ciegas arriesgaría pegarle a un endpoint de terceros facturable "
    "en vez de uno propio de RapidAPI",
)


def validate_uploadpost(env):
    """Upload-post -- GET https://api.upload-post.com/api/uploadposts/users (header
    `Authorization: Apikey <key>`). Documentado en
    docs.upload-post.com/api/user-profiles/ -- lista perfiles conectados, no publica
    contenido ni consume créditos de posteo."""
    candidate = pick_candidate(env, ["UPLOADPOST_API_KEY"])
    if candidate is None:
        return no_key_result(["UPLOADPOST_API_KEY"])
    code, _body, err, latency = http_get(
        "https://api.upload-post.com/api/uploadposts/users",
        {"Authorization": f"Apikey {env[candidate]}"},
    )
    return _classify_http(code, err, latency, ok_detail="200 -- perfiles listados")


# ---------------------------------------------------------------------------------
# Infraestructura propia / plataformas de datos.
# ---------------------------------------------------------------------------------

def validate_github(env):
    """GitHub -- GET https://api.github.com/user (Bearer). Gratis, cuenta contra el
    límite de tasa (5000/hora) pero no tiene costo."""
    candidate = pick_candidate(env, ["GITHUB_TOKEN"])
    if candidate is None:
        return no_key_result(["GITHUB_TOKEN"])
    code, _body, err, latency = http_get(
        "https://api.github.com/user",
        {"Authorization": f"Bearer {env[candidate]}", "Accept": "application/vnd.github+json"},
    )
    return _classify_http(code, err, latency, ok_detail="200 -- usuario obtenido")


def validate_notion(env):
    """Notion -- GET https://api.notion.com/v1/users/me (Bearer + header
    `Notion-Version: 2022-06-28`). Gratis, solo lectura del bot user."""
    candidate = pick_candidate(env, ["NOTION_TOKEN"])
    if candidate is None:
        return no_key_result(["NOTION_TOKEN"])
    code, _body, err, latency = http_get(
        "https://api.notion.com/v1/users/me",
        {"Authorization": f"Bearer {env[candidate]}", "Notion-Version": "2022-06-28"},
    )
    return _classify_http(code, err, latency, ok_detail="200 -- bot user obtenido")


def validate_telegram(env):
    """Telegram -- GET https://api.telegram.org/bot<token>/getMe. Gratis, ya usado
    toda la sesión. El token va en la URL (Telegram no soporta header de auth) --
    nunca se imprime, solo se usa para construir el request."""
    names = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN_PHOTOREEL"]
    candidate = pick_candidate(env, names)
    if candidate is None:
        return no_key_result(names)
    code, _body, err, latency = http_get(
        f"https://api.telegram.org/bot{env[candidate]}/getMe"
    )
    if err:
        return result(STATUS_UNKNOWN, f"error de red: {err}", latency)
    if code == 200:
        return result(STATUS_OK, f"200 -- getMe ok (`{candidate}`)", latency)
    if code in (401, 403, 404):
        return result(STATUS_FAIL, f"token invalido (HTTP {code})", latency)
    return result(STATUS_UNKNOWN, f"respuesta inesperada HTTP {code}", latency)


def validate_cloudflare(env):
    """Cloudflare -- GET https://api.cloudflare.com/client/v4/user/tokens/verify
    (Bearer). Solo funciona con API Tokens (no con el Global API Key legado, que usa
    `X-Auth-Email`/`X-Auth-Key`) -- se prueban solo los candidatos tipo token."""
    names = [
        "CLOUDFLARE_AUTH_TOKEN", "CLOUDFLARE_TOKEN_DNS", "CLOUDFLARE_TOKEN_WORKERS",
        "CLOUDFLARE_TOKEN_BILLING", "CLOUDFLARE_TOKEN_GTAV", "CLOUDFLARE_TOKEN_WORDPRESS",
    ]
    candidate = pick_candidate(env, names)
    if candidate is None:
        return no_key_result(names)
    code, body, err, latency = http_get(
        "https://api.cloudflare.com/client/v4/user/tokens/verify",
        {"Authorization": f"Bearer {env[candidate]}"},
    )
    if err:
        return result(STATUS_UNKNOWN, f"error de red: {err}", latency)
    if code == 200:
        data = parse_json(body) or {}
        active = (
            isinstance(data, dict)
            and data.get("success")
            and (data.get("result") or {}).get("status") == "active"
        )
        detail = f"200 -- token `{candidate}` " + ("activo" if active else "respuesta sin 'active'")
        return result(STATUS_OK if active else STATUS_UNKNOWN, detail, latency)
    if code in (401, 403):
        return result(STATUS_FAIL, f"token `{candidate}` invalido (HTTP {code})", latency)
    return result(STATUS_UNKNOWN, f"respuesta inesperada HTTP {code}", latency)


def validate_stripe(env):
    """Stripe -- GET https://api.stripe.com/v1/balance (Basic auth, la secret key
    como usuario). Solo lectura, documentado como gratis -- no ejecuta ningún cargo ni
    pago (regla 4 del CLAUDE.md raíz: ningún pago se ejecuta solo). Prueba
    STRIPE_SECRET_KEY (test) antes que STRIPE_SECRET_KEY_LIVE; hoy solo hay llaves
    `*_LIVE` en el vault, se usan igual porque `/v1/balance` es de solo lectura."""
    names = ["STRIPE_SECRET_KEY", "STRIPE_SECRET_KEY_LIVE"]
    candidate = pick_candidate(env, names)
    if candidate is None:
        return no_key_result(names)
    basic = base64.b64encode(f"{env[candidate]}:".encode()).decode()
    code, _body, err, latency = http_get(
        "https://api.stripe.com/v1/balance", {"Authorization": f"Basic {basic}"}
    )
    return _classify_http(code, err, latency, ok_detail=f"200 -- balance obtenido (`{candidate}`)")


def validate_supabase(env):
    """Supabase -- GET {SUPABASE_*_URL}/rest/v1/ con header `apikey`. 200 = llave
    válida (devuelve el spec OpenAPI del proyecto), 401 = llave inválida. Gratis --
    Supabase no cobra por esta lectura de metadatos. Prueba los tres proyectos del
    vault en orden (Orion, Nissan, Worldvibe) y usa el primero con URL+llave
    utilizables."""
    projects = [
        ("orion", "SUPABASE_ORION_URL", "SUPABASE_ORION_ANON_KEY"),
        ("nissan", "SUPABASE_NISSAN_URL", "SUPABASE_NISSAN_KEY"),
        ("worldvibe", "SUPABASE_WORLDVIBE_URL", "SUPABASE_WORLDVIBE_SERVICE_KEY"),
    ]
    for label, url_name, key_name in projects:
        if is_usable(env, url_name) and is_usable(env, key_name):
            base = env[url_name].rstrip("/")
            key = env[key_name]
            code, _body, err, latency = http_get(
                f"{base}/rest/v1/", {"apikey": key, "Authorization": f"Bearer {key}"}
            )
            if err:
                return result(STATUS_UNKNOWN, f"proyecto {label}: error de red: {err}", latency)
            if code == 200:
                return result(
                    STATUS_OK, f"proyecto {label}: REST root respondió 200 (llave válida)", latency
                )
            if code in (401, 403):
                return result(STATUS_FAIL, f"proyecto {label}: llave inválida (HTTP {code})", latency)
            return result(STATUS_UNKNOWN, f"proyecto {label}: respuesta inesperada HTTP {code}", latency)
    return result(
        STATUS_UNKNOWN,
        "sin URL+llave utilizables en ningún proyecto Supabase del vault "
        "(orion/nissan/worldvibe)",
    )


def validate_baserow(env):
    """Baserow (autohospedado) -- los tokens del vault son tokens de la Database API
    (no JWT de usuario), así que no sirven contra `/api/user/`. Se valida listando 1
    fila de una tabla propia ya conocida (`gastos`, id 136 -- ver
    `cano_hermes/monitoring.py:BASEROW_GASTOS_TABLE_ID`). Endpoint: GET
    {BASEROW_API_URL}/api/database/rows/table/136/?size=1 con header
    `Authorization: Token <token>`. Gratis -- instancia propia autohospedada, sin
    costo por request."""
    names = ["BASEROW_TOKEN", "BASEROW_API_TOKEN", "BASEROW_CONTENT_TOKEN", "BASEROW_ACCOUNTING_TOKEN"]
    candidate = pick_candidate(env, names)
    if candidate is None:
        return no_key_result(names)
    base = (env.get("BASEROW_API_URL") or "http://localhost:8085").rstrip("/")
    code, _body, err, latency = http_get(
        f"{base}/api/database/rows/table/136/?size=1",
        {"Authorization": f"Token {env[candidate]}"},
    )
    if err:
        return result(STATUS_UNKNOWN, f"error de red/host no disponible: {err}", latency)
    if code == 200:
        return result(STATUS_OK, f"200 -- token `{candidate}` válido (tabla 136)", latency)
    if code in (401, 403):
        return result(STATUS_FAIL, f"token `{candidate}` inválido (HTTP {code})", latency)
    if code == 404:
        return result(STATUS_UNKNOWN, "host respondió pero tabla 136 no existe aquí (HTTP 404)", latency)
    return result(STATUS_UNKNOWN, f"respuesta inesperada HTTP {code}", latency)


def validate_n8n(env):
    """n8n (autohospedado) -- GET {N8N_HOST}/api/v1/workflows?limit=1 con header
    `X-N8N-API-KEY`. Documentado en docs.n8n.io/api/authentication/. Gratis -- API
    pública incluida en la edición Community autohospedada, sin costo por request."""
    if not is_usable(env, "N8N_API_KEY"):
        return no_key_result(["N8N_API_KEY"])
    host = (env.get("N8N_HOST") or "").rstrip("/")
    if not host:
        return result(STATUS_UNKNOWN, "N8N_API_KEY presente pero N8N_HOST ausente/vacío")
    code, _body, err, latency = http_get(
        f"{host}/api/v1/workflows?limit=1", {"X-N8N-API-KEY": env["N8N_API_KEY"]}
    )
    if err:
        return result(STATUS_UNKNOWN, f"error de red/host no disponible: {err}", latency)
    return _classify_http(code, err, latency, ok_detail="200 -- workflows listados")


def validate_upstash(env):
    """Upstash Redis REST -- GET {UPSTASH_REDIS_REST_URL}/ping (Bearer
    UPSTASH_REDIS_REST_TOKEN). Comando PING sobre la propia base de datos del usuario
    -- gratis dentro de cualquier plan, incluido el free tier."""
    names = ["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"]
    if not all(is_usable(env, n) for n in names):
        return no_key_result(names)
    base = env["UPSTASH_REDIS_REST_URL"].rstrip("/")
    code, body, err, latency = http_get(
        f"{base}/ping", {"Authorization": f"Bearer {env['UPSTASH_REDIS_REST_TOKEN']}"}
    )
    if err:
        return result(STATUS_UNKNOWN, f"error de red: {err}", latency)
    if code == 200:
        data = parse_json(body) or {}
        pong = isinstance(data, dict) and str(data.get("result", "")).upper() == "PONG"
        return result(
            STATUS_OK if pong else STATUS_UNKNOWN,
            "200 -- PING" + (" -> PONG" if pong else " (respuesta inesperada)"),
            latency,
        )
    if code in (401, 403):
        return result(STATUS_FAIL, f"token invalido (HTTP {code})", latency)
    return result(STATUS_UNKNOWN, f"respuesta inesperada HTTP {code}", latency)


def validate_huggingface(env):
    """Hugging Face -- GET https://huggingface.co/api/whoami-v2 (Bearer). Gratis."""
    names = ["HF_TOKEN", "HF_TOKEN_FINEGRAINED"]
    candidate = pick_candidate(env, names)
    if candidate is None:
        return no_key_result(names)
    code, _body, err, latency = http_get(
        "https://huggingface.co/api/whoami-v2",
        {"Authorization": f"Bearer {env[candidate]}"},
    )
    return _classify_http(code, err, latency, ok_detail=f"200 -- whoami ok (`{candidate}`)")


def validate_apify(env):
    """Apify -- GET https://api.apify.com/v2/users/me?token=<key>. Gratis, no
    consume créditos (migrado de `check_apify`, mismo endpoint desde F2)."""
    names = ["APIFY_API_KEY"] + [f"APIFY_KEY_{i}" for i in range(1, 8)]
    candidate = pick_candidate(env, names)
    if candidate is None:
        return no_key_result(names)
    code, _body, err, latency = http_get(
        f"https://api.apify.com/v2/users/me?token={env[candidate]}"
    )
    if err:
        return result(STATUS_UNKNOWN, f"error de red: {err}", latency)
    if code == 200:
        return result(STATUS_OK, f"200 -- perfil de usuario obtenido (`{candidate}`)", latency)
    if code in (401, 403):
        return result(STATUS_FAIL, f"llave invalida (HTTP {code})", latency)
    return result(STATUS_UNKNOWN, f"respuesta inesperada HTTP {code}", latency)


# ---------------------------------------------------------------------------------
# Policy-skip explícito -- ningún chequeo con red es seguro para estos tres.
# ---------------------------------------------------------------------------------

validate_kie = policy_skip(
    "factory/kie_readiness.py (factory-ia-channel-v5) SÍ tiene un chequeo local sin "
    "red (local_readiness()), pero exige un objeto Settings completo, toca ffmpeg y "
    "el CLI de Remotion, y su propio check 'provider_balance' queda BLOCKED sin un "
    "balance_lookup no facturable explícito -- ese es el mismo criterio de política "
    "que aplica aquí. Invocarlo por subprocess desde este repo acoplaría "
    "connection_matrix a las dependencias internas de factory-v5 (settings, node, "
    "ffmpeg) para un beneficio marginal (solo confirmaría presencia de KIE_API_KEY, "
    "que ya reporta la matriz base). Se documenta como policy-skip en vez de duplicar "
    "o acoplar esa lógica."
)

validate_higgsfield = policy_skip(
    "cuenta suspendida (ver memoria del operador) y cualquier endpoint de "
    "balance/consulta es potencialmente facturable -- fuera de alcance por política, "
    "igual que en el gate de Factory V5 (factory/kie_readiness.py marca 'higgsfield' "
    "PASS solo verificando que los flags de habilitación estén en false, sin red)."
)

validate_modal = policy_skip(
    "Modal se administra por CLI (`modal token`/`modal app`), no expone un endpoint "
    "HTTP público de whoami -- verificar el token exigiría invocar el CLI de Modal, "
    "fuera del alcance HTTP-only de este validador."
)


# ---------------------------------------------------------------------------------
# Registro único.
# ---------------------------------------------------------------------------------

VALIDATORS: dict[str, Validator] = {
    "apify": validate_apify,
    "rapidapi": validate_rapidapi,
    "openai": validate_openai,
    "anthropic": validate_anthropic,
    "kimi_moonshot": validate_kimi_moonshot,
    "openrouter": validate_openrouter,
    "nvidia_nim": validate_nvidia_nim,
    "groq": validate_groq,
    "mistral": validate_mistral,
    "cohere": validate_cohere,
    "gemini": validate_gemini,
    "xai": validate_xai,
    "perplexity": validate_perplexity,
    "deepl": validate_deepl,
    "replicate": validate_replicate,
    "elevenlabs": validate_elevenlabs,
    "heygen": validate_heygen,
    "notion": validate_notion,
    "github": validate_github,
    "telegram": validate_telegram,
    "cloudflare": validate_cloudflare,
    "stripe": validate_stripe,
    "supabase": validate_supabase,
    "baserow": validate_baserow,
    "n8n": validate_n8n,
    "firecrawl": validate_firecrawl,
    "exa": validate_exa,
    "pexels": validate_pexels,
    "pixabay": validate_pixabay,
    "cloudinary": validate_cloudinary,
    "upstash": validate_upstash,
    "huggingface": validate_huggingface,
    "uploadpost": validate_uploadpost,
    "kie": validate_kie,
    "higgsfield": validate_higgsfield,
    "modal": validate_modal,
}
