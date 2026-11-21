import os
import re
import time
import json
import uuid
import secrets
import threading
import copy
import socket
import urllib.parse
import ipaddress
import requests


# Default provider constants
DEFAULT_PROVIDER = os.environ.get("DEFAULT_AI_PROVIDER", "ollama")
DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = os.environ.get("DEFAULT_OLLAMA_MODEL", "qwen2.5:1.5b")

DEFAULT_OPENAI_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
DEFAULT_OPENAI_MODEL = os.environ.get("DEFAULT_OPENAI_MODEL", "gpt-4o-mini")

# Environment configuration for local loopback development endpoints
# Default is FALSE for production safety.
# In production, loopback (localhost, 127.0.0.1, ::1) is rejected to prevent SSRF against host services.
# For local developer testing with local Ollama or local model runners (vLLM, LM Studio), set:
#     export ALLOW_LOCAL_CUSTOM_API=true
def is_local_api_allowed() -> bool:
    """
    Check if local inference endpoints (loopback destinations: localhost, 127.0.0.1, ::1)
    are permitted. Default is False for production safety.
    To enable local development inference (e.g. local Ollama or vLLM), set:
        export ALLOW_LOCAL_CUSTOM_API=true
    """
    return os.environ.get("ALLOW_LOCAL_CUSTOM_API", "false").strip().lower() in ("true", "1", "yes")

ALLOW_LOCAL_CUSTOM_API = is_local_api_allowed()

# Known cloud metadata hostnames and IP addresses to block unconditionally
CLOUD_METADATA_HOSTNAMES = frozenset({
    "metadata.google.internal",
    "metadata.goog",
    "metadata",
    "instance-data",
    "169.254.169.254",
})

CLOUD_METADATA_IPS = frozenset({
    "169.254.169.254",
    "fd00:ec2::254",
})

# Re-entrant lock for thread-safe concurrent session dictionary access
_SESSION_LOCK = threading.RLock()

# Connection test rate limiting tracking:
# key -> list of request timestamps within current sliding window
_TEST_RATE_LIMITS: dict[str, list[float]] = {}
_TEST_RATE_LIMIT_LOCK = threading.RLock()


def check_connection_test_rate_limit(
    identifier: str,
    max_requests: int = 10,
    window_seconds: int = 60
) -> bool:
    """
    Sliding window rate limiter for connection tests.
    Default limit: 10 tests per 60 seconds per identifier.
    Returns True if permitted, False if limit exceeded.
    """
    if not identifier:
        return False

    now = time.time()
    with _TEST_RATE_LIMIT_LOCK:
        timestamps = _TEST_RATE_LIMITS.setdefault(identifier, [])
        cutoff = now - window_seconds
        valid_timestamps = [ts for ts in timestamps if ts > cutoff]
        if len(valid_timestamps) >= max_requests:
            _TEST_RATE_LIMITS[identifier] = valid_timestamps
            return False

        valid_timestamps.append(now)
        _TEST_RATE_LIMITS[identifier] = valid_timestamps
        return True


def reset_connection_test_rate_limits() -> None:
    """Clear all connection test rate limit counters (used for test isolation)."""
    with _TEST_RATE_LIMIT_LOCK:
        _TEST_RATE_LIMITS.clear()

# --------------------------------------------------------------------------
# Multi-User Session Architecture & Concurrency Model:
#
# InsightForge utilizes an in-memory, thread-safe session registry guarded by
# an RLock (_SESSION_LOCK):
# - _ISSUED_SESSIONS: Authoritative server-issued session tokens with TTL metadata.
# - _USER_SESSIONS: Active user-configured provider credentials and parameters.
#
# Architectural Scope & Limitations:
# 1. Single-Worker Model: This in-memory design is authoritative when running
#    a single Uvicorn process/worker (standard for local analytics and development).
# 2. Multi-Worker & Distributed Deployments: In a production cluster running
#    multiple Uvicorn workers or distributed container replicas, in-memory state
#    is isolated per process. In such environments, this session registry should
#    be backed by a shared distributed cache (e.g., Redis or a dedicated database)
#    with identical TTL-based expiration and token verification semantics.
# 3. Anonymous Session Issuance Considerations:
#    In production environments where /config/session is publicly reachable,
#    unauthenticated session creation should be fronted by an API gateway, CDN
#    rate limiting (e.g. Cloudflare Turnstile/WAF), or IP-based issuance throttling
#    to prevent memory exhaustion from anonymous session allocation.
# --------------------------------------------------------------------------

# Authoritative registry of session tokens issued by the server:
# session_id -> { "created_at": float, "last_active": float, "ttl": int }
_ISSUED_SESSIONS: dict[str, dict] = {}

# In-memory session configuration registry:
# session_id -> { provider, api_key, model, base_url, created_at, last_active }
_USER_SESSIONS: dict[str, dict] = {}

# Session ID format constraints: 8-64 alphanumeric, hyphen, or underscore characters
SESSION_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")
RESERVED_SESSION_IDS = frozenset({
    "admin",
    "administrator",
    "root",
    "default",
    "system",
    "test",
    "guest",
    "null",
    "undefined",
    "user",
    "anonymous",
})


def generate_session_id() -> str:
    """Generate a cryptographically random 256-bit session token."""
    return secrets.token_hex(32)


def issue_session_token(ttl_seconds: int = 3600) -> str:
    """
    Generate, register, and return an authoritative cryptographically secure session token.
    Uses 256 bits of entropy via secrets.token_hex(32).
    """
    token = secrets.token_hex(32)
    now = time.time()
    with _SESSION_LOCK:
        _ISSUED_SESSIONS[token] = {
            "created_at": now,
            "last_active": now,
            "ttl": ttl_seconds
        }
    return token


def register_session_token(session_id: str, ttl_seconds: int = 3600) -> str:
    """
    Register a specific valid session token into the authoritative registry.
    Useful for internal registration or testing fixtures.
    """
    valid_id = validate_session_id(session_id)
    now = time.time()
    with _SESSION_LOCK:
        _ISSUED_SESSIONS[valid_id] = {
            "created_at": now,
            "last_active": now,
            "ttl": ttl_seconds
        }
    return valid_id


def verify_session_token(session_id: str | None, max_age_seconds: int = 3600) -> str:
    """
    Verify that a session token is well-formed, exists in the authoritative registry,
    and has not expired. Updates the last_active timestamp on successful verification.
    Raises ValueError with a clear message if unissued, invalid, or expired.
    """
    if not session_id or not isinstance(session_id, str):
        raise ValueError("session_id is required and must be a non-empty string.")

    valid_id = validate_session_id(session_id)

    with _SESSION_LOCK:
        if valid_id not in _ISSUED_SESSIONS:
            raise ValueError(
                "Invalid or unissued session token. Please obtain a valid session from /config/session."
            )

        meta = _ISSUED_SESSIONS[valid_id]
        now = time.time()
        ttl = meta.get("ttl", max_age_seconds)

        if now - meta.get("last_active", now) > ttl:
            # Purge expired session from both registries
            _ISSUED_SESSIONS.pop(valid_id, None)
            _USER_SESSIONS.pop(valid_id, None)
            raise ValueError("Session token has expired. Please obtain a new session.")

        meta["last_active"] = now
        return valid_id


def is_session_issued(session_id: str | None, max_age_seconds: int = 3600) -> bool:
    """Check if session is currently valid, registered, and active without raising."""
    if not session_id:
        return False
    try:
        verify_session_token(session_id, max_age_seconds=max_age_seconds)
        return True
    except ValueError:
        return False


def validate_session_id(session_id: str | None) -> str:
    """
    Validate that a session ID meets cryptographic safety requirements:
    - Must be a non-empty string of 8-64 alphanumeric, hyphen, or underscore characters
    - Must not match common reserved or predictable names
    - Prevents path traversal and parameter injection attacks
    """
    if not session_id or not isinstance(session_id, str):
        raise ValueError("session_id must be a non-empty string.")

    cleaned = session_id.strip()
    if not SESSION_ID_REGEX.match(cleaned):
        raise ValueError(
            "Invalid session_id format: must be 8-64 characters (alphanumeric, hyphens, underscores)."
        )

    if cleaned.lower() in RESERVED_SESSION_IDS:
        raise ValueError(f"Invalid session_id: '{cleaned}' is a reserved identifier.")

    return cleaned


def is_ip_private_or_restricted(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """
    Check if an IPv4 or IPv6 address is private, loopback, link-local, multicast,
    reserved, or belongs to a known cloud metadata address.
    """
    ip_str = str(ip_obj).lower()
    if ip_str in CLOUD_METADATA_IPS:
        return True
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def validate_custom_api_url(url: str | None, allow_local: bool | None = None) -> str:
    """
    Validate and sanitize a Base URL (Custom API, Ollama, OpenAI) with strict SSRF protection:
    - Parses with urllib.parse.urlsplit
    - Permits HTTPS for remote endpoints
    - Permits HTTP only for loopback endpoints when allow_local is True
    - Rejects malformed URLs, unsupported schemes, embedded credentials, and invalid ports
    - Blocks private, multicast, link-local, reserved, and cloud metadata IPv4/IPv6 destinations
    - Performs DNS resolution checks against resolved addresses
    - Returns stripped and normalized URL without trailing slash

    Residual Security Limitation Notice (DNS Rebinding):
    Pre-flight DNS validation prevents connecting to static internal names and private IPs.
    However, there remains a theoretical Time-of-Check to Time-of-Use (TOCTOU) DNS rebinding
    window between this resolution check and the subsequent requests call if a malicious DNS
    server dynamically alters its response. Complete protection against DNS rebinding would
    require a custom HTTP transport adapter with IP pinning.
    """
    if not url or not isinstance(url, str):
        raise ValueError("A valid Base URL starting with http:// or https:// is required.")

    cleaned = url.strip()
    if not cleaned:
        raise ValueError("A valid Base URL starting with http:// or https:// is required.")

    if allow_local is None:
        allow_local = is_local_api_allowed()

    try:
        parsed = urllib.parse.urlsplit(cleaned)
    except Exception as e:
        raise ValueError(f"Malformed URL: {e}")

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(
            f"A valid Base URL starting with http:// or https:// is required. Unsupported URL scheme '{scheme}'."
        )

    if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
        raise ValueError("Base URL must not contain embedded user credentials.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Base URL must contain a valid host.")

    try:
        port = parsed.port
    except ValueError:
        raise ValueError("URL contains an invalid port number.")

    if port is not None and not (1 <= port <= 65535):
        raise ValueError(f"Port {port} is out of valid range (1-65535).")

    lowered_host = hostname.lower().strip("[]")

    if lowered_host in CLOUD_METADATA_HOSTNAMES:
        raise ValueError(f"Destination '{hostname}' is a blocked cloud metadata service.")

    # Check if host is an IP literal
    is_ip_literal = False
    ip_literal_obj = None
    try:
        ip_literal_obj = ipaddress.ip_address(lowered_host)
        is_ip_literal = True
    except ValueError:
        is_ip_literal = False

    if is_ip_literal:
        if ip_literal_obj.is_loopback:
            if not allow_local:
                raise ValueError(
                    "Localhost/loopback destinations are disabled by policy. Set ALLOW_LOCAL_CUSTOM_API=true in environment for local development."
                )
            return cleaned.rstrip("/")

        if scheme != "https":
            raise ValueError("Provider endpoints for remote destinations must use HTTPS.")

        if is_ip_private_or_restricted(ip_literal_obj):
            raise ValueError(
                f"Destination IP '{ip_literal_obj}' is in a private, link-local, or restricted range."
            )
        return cleaned.rstrip("/")

    # Hostname (not an IP literal)
    is_loopback_host = (lowered_host == "localhost" or lowered_host.endswith(".localhost"))
    if is_loopback_host:
        if not allow_local:
            raise ValueError(
                "Localhost/loopback destinations are disabled by policy. Set ALLOW_LOCAL_CUSTOM_API=true in environment for local development."
            )
        return cleaned.rstrip("/")

    if scheme != "https":
        raise ValueError("Provider endpoints for remote destinations must use HTTPS.")

    # DNS resolution check for non-loopback hostnames
    try:
        addr_info = socket.getaddrinfo(hostname, port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve host '{hostname}': {e}")
    except Exception as e:
        raise ValueError(f"DNS resolution failed for '{hostname}': {e}")

    if not addr_info:
        raise ValueError(f"No IP addresses resolved for host '{hostname}'.")

    for entry in addr_info:
        ip_str = entry[4][0]
        try:
            resolved_ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if is_ip_private_or_restricted(resolved_ip):
            raise ValueError(
                f"Host '{hostname}' resolves to restricted IP address '{resolved_ip}'."
            )

    return cleaned.rstrip("/")


def scrub_secrets(text: str, secret: str | None = None) -> str:
    """
    Remove API keys, Bearer tokens, URL credentials, and sensitive credentials
    from logs and error messages.
    """
    if not text:
        return ""

    sanitized = str(text)

    # Redact explicit secret if provided
    if secret:
        s = str(secret).strip()
        if len(s) >= 4:
            sanitized = sanitized.replace(s, "[REDACTED]")

    # Redact embedded URL credentials (e.g., https://user:pass@host)
    sanitized = re.sub(
        r"://([^:\s]+):([^@\s]+)@",
        "://[REDACTED_USER]:[REDACTED_PASSWORD]@",
        sanitized
    )

    # Redact Authorization header & Bearer tokens
    sanitized = re.sub(
        r"(?i)(authorization\s*:\s*)Bearer\s+[^\s\"',]+",
        r"\1Bearer [REDACTED]",
        sanitized
    )
    sanitized = re.sub(
        r"(?i)\bBearer\s+[A-Za-z0-9_\-\.]{6,}",
        "Bearer [REDACTED]",
        sanitized
    )

    # Redact api-key headers and key=value pairs
    sanitized = re.sub(
        r"(?i)(?:x-api-key|api[-_]?key|auth[-_]?token|access[-_]?token|secret[-_]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{6,}['\"]?",
        "api_key=[REDACTED]",
        sanitized
    )

    # Redact sensitive query parameters in URLs
    sanitized = re.sub(
        r"(?i)([?&](?:api_key|key|token|secret)=)[^&\s]+",
        r"\1[REDACTED]",
        sanitized
    )

    # Redact common AI vendor key prefixes (OpenAI, Groq, OpenRouter, Anthropic, GitHub)
    sanitized = re.sub(
        r"\b(?:sk-[a-zA-Z0-9_\-\.]{8,}|gsk_[a-zA-Z0-9_\-\.]{8,}|sk-or-v1-[a-zA-Z0-9_\-\.]{8,})\b",
        "[REDACTED_API_KEY]",
        sanitized
    )

    return sanitized


def mask_api_key(key: str | None) -> str:
    """Mask API key showing only the last 4 characters."""
    if not key:
        return ""
    key_str = str(key).strip()
    if len(key_str) <= 4:
        return "••••"
    return f"••••••••{key_str[-4:]}"


def set_session_config(
    session_id: str,
    provider: str,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None
) -> dict:
    """
    Save user AI configuration in isolated memory for the current session.
    Never persists keys to disk or returns raw keys.
    Requires an already-issued, unexpired server session token.
    Thread-safe, cryptographically validated, and SSRF protected.
    """
    with _SESSION_LOCK:
        # Proactively clean up expired sessions
        cleanup_expired_sessions()

        if not session_id or not isinstance(session_id, str):
            raise ValueError("A valid server-issued session token is required to save configuration.")

        # verify_session_token ensures token is issued, unexpired, and valid.
        # Unknown or expired session IDs raise ValueError and are NEVER silently registered or revived.
        target_id = verify_session_token(session_id)

        provider_clean = (provider or "ollama").strip().lower()
        api_key_clean = api_key.strip() if api_key else None
        model_clean = model.strip() if model else None
        base_url_clean = base_url.strip() if base_url else None

        # Provider defaults and validation
        if provider_clean in ["custom", "custom_api"]:
            provider_clean = "custom"
            if not base_url_clean:
                raise ValueError("A valid Base URL starting with http:// or https:// is required for Custom API.")
            base_url_clean = validate_custom_api_url(base_url_clean)
            if not model_clean:
                raise ValueError("Model name is required for Custom API.")
        elif provider_clean in ["openai", "openai_compatible", "groq", "openrouter"]:
            if not api_key_clean:
                raise ValueError(f"API Key is required for provider '{provider}'.")

            if provider_clean == "groq":
                base_url_clean = base_url_clean or "https://api.groq.com/openai/v1"
                model_clean = model_clean or "llama-3.3-70b-versatile"
            elif provider_clean == "openrouter":
                base_url_clean = base_url_clean or "https://openrouter.ai/api/v1"
                model_clean = model_clean or "meta-llama/llama-3.3-70b-instruct"
            else:
                base_url_clean = base_url_clean or DEFAULT_OPENAI_URL
                model_clean = model_clean or DEFAULT_OPENAI_MODEL

            # Validate base_url for cloud/custom OpenAI endpoints
            base_url_clean = validate_custom_api_url(base_url_clean)
        else:
            # Default: Ollama
            provider_clean = "ollama"
            raw_url = base_url_clean or DEFAULT_OLLAMA_URL
            base_url_clean = validate_custom_api_url(raw_url)
            model_clean = model_clean or DEFAULT_OLLAMA_MODEL

        now = time.time()
        _USER_SESSIONS[target_id] = {
            "provider": provider_clean,
            "api_key": api_key_clean,
            "model": model_clean,
            "base_url": base_url_clean.rstrip("/"),
            "created_at": now,
            "last_active": now
        }
        if target_id in _ISSUED_SESSIONS:
            _ISSUED_SESSIONS[target_id]["last_active"] = now

        return {
            "session_id": target_id,
            "provider": provider_clean,
            "model": model_clean,
            "base_url": base_url_clean.rstrip("/"),
            "has_api_key": bool(api_key_clean),
            "masked_key": mask_api_key(api_key_clean)
        }


def get_session_config(session_id: str | None, max_age_seconds: int = 3600) -> dict:
    """
    Retrieve active configuration for a session or return safe default.
    Thread-safe, lazy-purges expired sessions, and returns a deep copy.
    """
    with _SESSION_LOCK:
        if session_id:
            try:
                valid_id = validate_session_id(session_id)
            except ValueError:
                valid_id = None

            if valid_id and valid_id in _USER_SESSIONS:
                session = _USER_SESSIONS[valid_id]
                now = time.time()
                # Check expiration immediately on access
                if now - session.get("last_active", now) > max_age_seconds:
                    del _USER_SESSIONS[valid_id]
                    _ISSUED_SESSIONS.pop(valid_id, None)
                else:
                    session["last_active"] = now
                    if valid_id in _ISSUED_SESSIONS:
                        _ISSUED_SESSIONS[valid_id]["last_active"] = now
                    return copy.deepcopy(session)

        # Fallback to default local Ollama
        return {
            "provider": DEFAULT_PROVIDER,
            "api_key": None,
            "model": DEFAULT_OLLAMA_MODEL,
            "base_url": DEFAULT_OLLAMA_URL.rstrip("/"),
            "created_at": time.time(),
            "last_active": time.time()
        }


def clear_session_config(session_id: str) -> bool:
    """Wipe credentials and configuration for a session immediately and invalidate session."""
    with _SESSION_LOCK:
        try:
            valid_id = validate_session_id(session_id)
        except ValueError:
            return False

        cleared_user = _USER_SESSIONS.pop(valid_id, None) is not None
        cleared_issued = _ISSUED_SESSIONS.pop(valid_id, None) is not None
        return cleared_user or cleared_issued


def cleanup_expired_sessions(max_age_seconds: int = 3600) -> int:
    """Purge sessions inactive for longer than max_age_seconds. Thread-safe."""
    with _SESSION_LOCK:
        now = time.time()
        expired_user = [
            s_id for s_id, s in list(_USER_SESSIONS.items())
            if now - s.get("last_active", now) > max_age_seconds
        ]
        for s_id in expired_user:
            _USER_SESSIONS.pop(s_id, None)

        expired_issued = [
            s_id for s_id, s in list(_ISSUED_SESSIONS.items())
            if now - s.get("last_active", now) > s.get("ttl", max_age_seconds)
        ]
        for s_id in expired_issued:
            _ISSUED_SESSIONS.pop(s_id, None)

        return len(expired_user) + len(expired_issued)


def clear_all_sessions() -> int:
    """Clear all user sessions, issued session tokens, and rate limits (used for test isolation). Thread-safe."""
    with _SESSION_LOCK:
        count = len(_USER_SESSIONS) + len(_ISSUED_SESSIONS)
        _USER_SESSIONS.clear()
        _ISSUED_SESSIONS.clear()
        reset_connection_test_rate_limits()
        return count


def verify_provider_connection(
    provider: str,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None
) -> dict:
    """
    Test connection to selected AI provider without exposing keys in error messages.
    Enforces SSRF validation, disallows redirects, and sets connect/read timeouts.
    Never returns raw upstream response bodies (res.text).
    """
    prov = (provider or "ollama").strip().lower()
    key = api_key.strip() if api_key else None
    target_model = model.strip() if model else None

    if prov in ["custom", "custom_api"]:
        if not target_model:
            return {
                "success": False,
                "detail": "Model name is required for Custom API."
            }
        try:
            url = validate_custom_api_url(base_url)
        except ValueError as e:
            return {
                "success": False,
                "detail": str(e)
            }

        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        # 1. Try GET /models first
        try:
            res = requests.get(
                f"{url}/models",
                headers=headers,
                allow_redirects=False,
                timeout=(5, 10)
            )
            if 300 <= res.status_code < 400 or getattr(res, "is_redirect", False):
                return {
                    "success": False,
                    "detail": "Redirects are not permitted for AI provider endpoints."
                }
            if res.status_code == 200:
                return {
                    "success": True,
                    "message": f"Successfully connected to Custom API at {url} (model: {target_model})."
                }
            elif res.status_code == 401:
                return {
                    "success": False,
                    "detail": "Authentication failed with Custom API: Invalid API key."
                }
            elif res.status_code == 404:
                # Many custom OpenAI-compatible proxies omit /models. Fallback probe /chat/completions
                try:
                    chat_res = requests.post(
                        f"{url}/chat/completions",
                        json={
                            "model": target_model,
                            "messages": [{"role": "user", "content": "ping"}],
                            "max_tokens": 1
                        },
                        headers=headers,
                        allow_redirects=False,
                        timeout=(5, 10)
                    )
                    if 300 <= chat_res.status_code < 400 or getattr(chat_res, "is_redirect", False):
                        return {
                            "success": False,
                            "detail": "Redirects are not permitted for AI provider endpoints."
                        }
                    if chat_res.status_code in [200, 400]:
                        return {
                            "success": True,
                            "message": f"Successfully connected to Custom API at {url} (model: {target_model})."
                        }
                    elif chat_res.status_code == 401:
                        return {
                            "success": False,
                            "detail": "Authentication failed with Custom API: Invalid API key."
                        }
                    else:
                        return {
                            "success": False,
                            "detail": f"Custom API returned HTTP status {chat_res.status_code}."
                        }
                except requests.exceptions.Timeout:
                    return {
                        "success": False,
                        "detail": f"Connection timed out while reaching Custom API endpoint at {url}."
                    }
                except requests.exceptions.RequestException as e:
                    return {
                        "success": False,
                        "detail": f"Models endpoint not found at {url} and probe failed: {scrub_secrets(str(e), key)}"
                    }
            else:
                return {
                    "success": False,
                    "detail": f"Custom API returned HTTP status {res.status_code}."
                }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "detail": f"Connection timed out while reaching Custom API at {url}."
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "detail": f"Could not reach Custom API at {url}: {scrub_secrets(str(e), key)}"
            }

    elif prov in ["openai", "openai_compatible", "groq", "openrouter"]:
        if not key:
            return {
                "success": False,
                "detail": "API key is required for cloud AI providers. Please enter your personal API key."
            }

        if prov == "groq":
            raw_url = base_url.strip() if base_url else "https://api.groq.com/openai/v1"
            target_model = target_model or "llama-3.3-70b-versatile"
        elif prov == "openrouter":
            raw_url = base_url.strip() if base_url else "https://openrouter.ai/api/v1"
            target_model = target_model or "meta-llama/llama-3.3-70b-instruct"
        else:
            raw_url = base_url.strip() if base_url else DEFAULT_OPENAI_URL
            target_model = target_model or DEFAULT_OPENAI_MODEL

        try:
            url = validate_custom_api_url(raw_url)
        except ValueError as e:
            return {
                "success": False,
                "detail": str(e)
            }

        test_endpoint = f"{url}/models"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }

        try:
            res = requests.get(
                test_endpoint,
                headers=headers,
                allow_redirects=False,
                timeout=(5, 10)
            )
            if 300 <= res.status_code < 400 or getattr(res, "is_redirect", False):
                return {
                    "success": False,
                    "detail": "Redirects are not permitted for AI provider endpoints."
                }
            if res.status_code == 200:
                return {
                    "success": True,
                    "message": f"Successfully connected and authenticated with {prov} at {url} (target model: {target_model})."
                }
            elif res.status_code == 401:
                return {
                    "success": False,
                    "detail": "Authentication failed: Invalid API key. Please check your credentials."
                }
            elif res.status_code == 404:
                return {
                    "success": False,
                    "detail": f"Models endpoint not found at {url}. Please verify the Base URL."
                }
            else:
                return {
                    "success": False,
                    "detail": f"Provider returned HTTP status {res.status_code}."
                }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "detail": f"Connection timed out while reaching provider endpoint at {url}."
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "detail": f"Connection error: {scrub_secrets(str(e), key)}"
            }

    else:
        # Ollama check with strict Base URL SSRF validation, timeouts, and redirect protection
        raw_url = (base_url.strip() if base_url else DEFAULT_OLLAMA_URL).rstrip("/")
        try:
            url = validate_custom_api_url(raw_url)
        except ValueError as e:
            return {
                "success": False,
                "detail": str(e)
            }

        target_model = target_model or DEFAULT_OLLAMA_MODEL
        tags_endpoint = f"{url}/api/tags"

        try:
            res = requests.get(tags_endpoint, timeout=(5, 10), allow_redirects=False)
            if 300 <= res.status_code < 400 or getattr(res, "is_redirect", False):
                return {
                    "success": False,
                    "detail": "Redirects are not permitted for AI provider endpoints."
                }
            if res.status_code == 200:
                return {
                    "success": True,
                    "message": f"Successfully connected to Ollama at {url} (model: {target_model})."
                }
            return {
                "success": False,
                "detail": f"Ollama service at {url} returned HTTP status {res.status_code}."
            }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "detail": f"Connection timed out while reaching Ollama endpoint at {url}."
            }
        except requests.exceptions.RequestException as e:
            safe_detail = scrub_secrets(str(e))
            return {
                "success": False,
                "detail": f"Could not reach Ollama at {url}: {safe_detail}"
            }


def chat_completion(
    messages: list[dict],
    tools: list[dict] | None = None,
    format_json: bool = False,
    temperature: float = 0.0,
    session_config: dict | None = None,
    timeout: int = 120
) -> dict:
    """
    Unified chat completion interface supporting both local Ollama and OpenAI-compatible providers.
    Normalizes response message structure and tool calls.
    SSRF validation, redirect protection, and secret scrubbing applied.
    """
    cfg = session_config or get_session_config(None)
    provider = cfg.get("provider", "ollama")
    model = cfg.get("model", DEFAULT_OLLAMA_MODEL)
    base_url = cfg.get("base_url", DEFAULT_OLLAMA_URL).rstrip("/")
    api_key = cfg.get("api_key")

    # 1. OpenAI-Compatible Execution (OpenAI, Groq, OpenRouter, Custom API)
    if provider in ["openai", "openai_compatible", "groq", "openrouter", "custom", "custom_api"]:
        if provider not in ["custom", "custom_api"] and not api_key:
            raise ValueError(
                "No API key provided. Please configure your personal API key in Settings -> AI Provider."
            )

        # Validate base_url for Custom API or OpenAI-compatible endpoint
        try:
            validated_base_url = validate_custom_api_url(base_url)
        except ValueError as e:
            raise ValueError(f"Invalid API Base URL: {e}")

        endpoint = f"{validated_base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }

        if tools:
            payload["tools"] = tools

        if format_json:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                allow_redirects=False,
                timeout=(5, timeout)
            )
            if 300 <= response.status_code < 400 or getattr(response, "is_redirect", False):
                raise RuntimeError("Redirects are not permitted for AI provider endpoints.")

            if response.status_code == 401:
                raise RuntimeError(
                    "Authentication failed with AI provider: Invalid API key. Please update your credentials in Settings."
                )
            if response.status_code == 404:
                raise RuntimeError(
                    f"Model '{model}' or endpoint '{endpoint}' not found. Please verify model name and Base URL."
                )
            response.raise_for_status()

            data = response.json()
            choice = data["choices"][0]["message"]

            # Normalize tool calls: parse string arguments into dict if needed
            raw_tools = choice.get("tool_calls")
            norm_tools = None
            if raw_tools:
                norm_tools = []
                for tc in raw_tools:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name")
                    fn_args = fn.get("arguments", {})
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            pass
                    norm_tools.append({
                        "id": tc.get("id"),
                        "type": "function",
                        "function": {
                            "name": fn_name,
                            "arguments": fn_args
                        }
                    })
            elif choice.get("function_call"):
                fc = choice["function_call"]
                fn_name = fc.get("name")
                fn_args = fc.get("arguments", {})
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        pass
                norm_tools = [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "arguments": fn_args
                    }
                }]

            return {
                "role": "assistant",
                "content": choice.get("content"),
                "tool_calls": norm_tools
            }

        except requests.exceptions.RequestException as e:
            safe_error = scrub_secrets(str(e), api_key)
            raise RuntimeError(f"Could not communicate with AI provider ({provider}): {safe_error}")

    # 2. Local Ollama Execution
    else:
        try:
            validated_base_url = validate_custom_api_url(base_url)
        except ValueError as e:
            raise RuntimeError(f"Invalid Ollama Base URL: {e}")

        endpoint = f"{validated_base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        if tools:
            payload["tools"] = tools

        if format_json:
            payload["format"] = "json"

        try:
            response = requests.post(
                endpoint,
                json=payload,
                allow_redirects=False,
                timeout=(5, timeout)
            )
            if 300 <= response.status_code < 400 or getattr(response, "is_redirect", False):
                raise RuntimeError("Redirects are not permitted for AI provider endpoints.")

            response.raise_for_status()
            msg = response.json()["message"]

            # Normalize arguments if string
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    args = fn.get("arguments")
                    if isinstance(args, str):
                        try:
                            fn["arguments"] = json.loads(args)
                        except Exception:
                            pass

            return msg

        except requests.exceptions.RequestException as e:
            safe_error = scrub_secrets(str(e))
            raise RuntimeError(f"Could not communicate with Ollama at {endpoint}: {safe_error}")
