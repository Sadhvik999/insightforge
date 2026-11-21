import pytest
import io
import time
import socket
import concurrent.futures
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.llm_client import (
    set_session_config,
    get_session_config,
    clear_session_config,
    clear_all_sessions,
    scrub_secrets,
    mask_api_key,
    verify_provider_connection,
    chat_completion,
    generate_session_id,
    validate_session_id,
    issue_session_token,
    register_session_token,
    verify_session_token,
    validate_custom_api_url,
    is_session_issued,
)

client = TestClient(app)


def setup_function():
    clear_all_sessions()


def teardown_function():
    clear_all_sessions()


# --------------------------------------------------------------------------
# 1. Application works without a developer-owned API key (defaults to Ollama)
# --------------------------------------------------------------------------
def test_01_default_configuration_requires_no_developer_api_key():
    config = get_session_config(None)
    assert config["provider"] == "ollama"
    assert config["api_key"] is None
    assert config["model"] == "qwen2.5:1.5b"
    assert config["base_url"] == "http://localhost:11434"

    res = client.get("/config/current")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "ollama"
    assert data["has_api_key"] is False
    assert data["masked_key"] == ""


# --------------------------------------------------------------------------
# 2. Missing user credentials for cloud provider produce clear error
# --------------------------------------------------------------------------
def test_02_missing_credentials_produce_clear_error():
    token = issue_session_token()

    # Save attempt with missing API key
    res = client.post(
        "/config/save",
        headers={"X-Session-ID": token},
        json={"provider": "openai_compatible", "api_key": ""}
    )
    assert res.status_code == 400
    assert "API Key is required" in res.json()["detail"]

    # Test connection attempt with missing API key
    test_res = client.post(
        "/config/test",
        headers={"X-Session-ID": token},
        json={"provider": "openai_compatible", "api_key": ""}
    )
    assert test_res.status_code == 400
    assert "API key is required" in test_res.json()["detail"]

    # chat_completion with cloud provider missing api_key
    with pytest.raises(ValueError, match="No API key provided"):
        chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            session_config={"provider": "openai_compatible", "api_key": None}
        )


# --------------------------------------------------------------------------
# 3. Valid user credentials are saved in memory and passed to selected provider
# --------------------------------------------------------------------------
def test_03_valid_user_credentials_saved_and_passed(monkeypatch):
    captured_request = {}

    def mock_post(url, *args, **kwargs):
        captured_request["url"] = url
        captured_request["json"] = kwargs.get("json")
        captured_request["headers"] = kwargs.get("headers")
        captured_request["allow_redirects"] = kwargs.get("allow_redirects")

        class MockResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Hello from custom OpenAI provider!"
                            }
                        }
                    ]
                }

        return MockResponse()

    monkeypatch.setattr("requests.post", mock_post)

    # Register session token first
    register_session_token("session-alice")

    # User saves their own credentials
    user_api_key = "sk-user-custom-secret-key-12345"
    save_res = client.post(
        "/config/save",
        json={
            "session_id": "session-alice",
            "provider": "openai_compatible",
            "api_key": user_api_key,
            "model": "gpt-4o",
            "base_url": "https://93.184.216.34/v1"
        }
    )
    assert save_res.status_code == 200
    save_data = save_res.json()
    assert save_data["success"] is True
    assert save_data["config"]["session_id"] == "session-alice"
    assert save_data["config"]["has_api_key"] is True
    # Verify raw key is NOT returned in response
    assert save_data["config"]["masked_key"] == "••••••••2345"
    assert user_api_key not in str(save_data)

    # Perform chat completion for session-alice
    session_config = get_session_config("session-alice")
    result = chat_completion(
        messages=[{"role": "user", "content": "Hello"}],
        session_config=session_config
    )
    assert result["content"] == "Hello from custom OpenAI provider!"
    assert captured_request["url"] == "https://93.184.216.34/v1/chat/completions"
    assert captured_request["headers"]["Authorization"] == f"Bearer {user_api_key}"
    assert captured_request["json"]["model"] == "gpt-4o"


# --------------------------------------------------------------------------
# 4. Invalid credentials produce clear error
# --------------------------------------------------------------------------
def test_04_invalid_credentials_produce_clear_error(monkeypatch):
    class Mock401Response:
        status_code = 401

        def raise_for_status(self):
            import requests
            raise requests.exceptions.HTTPError("401 Client Error: Unauthorized")

        def json(self):
            return {"error": {"message": "Incorrect API key provided"}}

    monkeypatch.setattr("requests.post", lambda *args, **kwargs: Mock401Response())

    with pytest.raises(RuntimeError, match="Invalid API key"):
        chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            session_config={
                "provider": "openai_compatible",
                "api_key": "sk-invalid-key-9999",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o"
            }
        )


# --------------------------------------------------------------------------
# 5. Different sessions cannot access one another's credentials (isolation)
# --------------------------------------------------------------------------
def test_05_session_isolation_prevents_credential_leakage():
    # Register session tokens for Alice and Bob
    register_session_token("alice-session")
    register_session_token("bob-session")

    # User Alice configures her OpenAI key
    set_session_config(
        session_id="alice-session",
        provider="openai_compatible",
        api_key="sk-alice-secret-key-1111",
        model="gpt-4o",
        base_url="https://api.openai.com/v1"
    )

    # User Bob configures his Groq key
    set_session_config(
        session_id="bob-session",
        provider="groq",
        api_key="gsk-bob-secret-key-2222",
        model="llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1"
    )

    # User Charlie without session gets default Ollama
    alice_cfg = get_session_config("alice-session")
    bob_cfg = get_session_config("bob-session")
    charlie_cfg = get_session_config("charlie-session-unknown")

    assert alice_cfg["api_key"] == "sk-alice-secret-key-1111"
    assert alice_cfg["model"] == "gpt-4o"

    assert bob_cfg["api_key"] == "gsk-bob-secret-key-2222"
    assert bob_cfg["model"] == "llama-3.3-70b-versatile"

    assert charlie_cfg["api_key"] is None
    assert charlie_cfg["provider"] == "ollama"

    # Alice clears her config
    clear_session_config("alice-session")
    assert get_session_config("alice-session")["provider"] == "ollama"
    assert get_session_config("bob-session")["api_key"] == "gsk-bob-secret-key-2222"


# --------------------------------------------------------------------------
# 6. API keys never appear in response JSON
# --------------------------------------------------------------------------
def test_06_api_keys_never_appear_in_response_json():
    secret_key = "sk-super-secret-user-key-77777"
    register_session_token("sec-test-session")
    save_res = client.post(
        "/config/save",
        json={
            "session_id": "sec-test-session",
            "provider": "openai_compatible",
            "api_key": secret_key,
            "model": "gpt-4o-mini"
        }
    )
    assert secret_key not in save_res.text
    assert secret_key not in str(save_res.json())

    curr_res = client.get("/config/current", headers={"X-Session-ID": "sec-test-session"})
    assert curr_res.status_code == 200
    assert secret_key not in curr_res.text
    assert secret_key not in str(curr_res.json())
    assert curr_res.json()["masked_key"] == "••••••••7777"


# --------------------------------------------------------------------------
# 7. API keys never appear in application logs or scrubbed error text
# --------------------------------------------------------------------------
def test_07_api_keys_scrubbed_from_error_messages():
    secret_key = "sk-confidential-user-token-99999"
    raw_error = f"Error connecting to https://api.openai.com/v1 with Bearer {secret_key}"

    scrubbed = scrub_secrets(raw_error, secret_key)
    assert secret_key not in scrubbed
    assert "[REDACTED]" in scrubbed

    # Test masking helper
    assert mask_api_key(secret_key) == "••••••••9999"
    assert mask_api_key(None) == ""
    assert mask_api_key("123") == "••••"


# --------------------------------------------------------------------------
# 8. Provider and model selection work correctly
# --------------------------------------------------------------------------
def test_08_provider_and_model_selection():
    register_session_token("groq-test")
    register_session_token("ollama-test")
    # Groq provider auto sets default base_url and model if omitted
    groq_res = client.post(
        "/config/save",
        json={
            "session_id": "groq-test",
            "provider": "groq",
            "api_key": "gsk-mock-key-1234"
        }
    )
    assert groq_res.status_code == 200
    cfg = groq_res.json()["config"]
    assert cfg["provider"] == "groq"
    assert cfg["model"] == "llama-3.3-70b-versatile"
    assert cfg["base_url"] == "https://api.groq.com/openai/v1"

    # Ollama provider allows custom model
    ollama_res = client.post(
        "/config/save",
        json={
            "session_id": "ollama-test",
            "provider": "ollama",
            "model": "mistral:7b"
        }
    )
    assert ollama_res.status_code == 200
    o_cfg = ollama_res.json()["config"]
    assert o_cfg["provider"] == "ollama"
    assert o_cfg["model"] == "mistral:7b"


# --------------------------------------------------------------------------
# 9. Session ID validation rejects insecure and arbitrary identifiers
# --------------------------------------------------------------------------
def test_09_session_id_validation_rejects_insecure_arbitrary_ids():
    # Reserved and trivial IDs must be rejected
    insecure_ids = [
        "admin",
        "root",
        "default",
        "system",
        "test",
        "guest",
        "null",
        "undefined",
        "short",  # < 8 chars
        "../traversal",
        "id;rm -rf",
        "session<script>",
        "a" * 65  # > 64 chars
    ]

    for bad_id in insecure_ids:
        # Rejection in validate_session_id
        with pytest.raises(ValueError):
            validate_session_id(bad_id)

        # Rejection in POST /config/save
        save_res = client.post(
            "/config/save",
            json={
                "session_id": bad_id,
                "provider": "ollama",
                "model": "qwen2.5:1.5b"
            }
        )
        assert save_res.status_code == 400
        assert "Invalid session_id" in save_res.json()["detail"]

        # Rejection in POST /config/clear
        clear_res = client.post(
            "/config/clear",
            json={"session_id": bad_id}
        )
        assert clear_res.status_code == 400
        assert "Invalid session_id" in clear_res.json()["detail"]

        # Rejection in GET /config/current
        curr_res = client.get(f"/config/current?session_id={bad_id}")
        assert curr_res.status_code == 400
        assert "Invalid session_id" in curr_res.json()["detail"]


# --------------------------------------------------------------------------
# 10. Cryptographically random session issuance
# --------------------------------------------------------------------------
def test_10_cryptographically_random_session_issuance():
    # Endpoint /config/session issues valid, high-entropy tokens
    issued = set()
    for _ in range(5):
        res = client.post("/config/session")
        assert res.status_code == 200
        s_id = res.json()["session_id"]
        # Must be 64-char hex string (256-bit CSPRNG)
        assert len(s_id) == 64
        assert validate_session_id(s_id) == s_id
        issued.add(s_id)

    # All issued tokens must be distinct
    assert len(issued) == 5

    # POST /config/save requires a valid server-issued session token
    missing_token_res = client.post(
        "/config/save",
        json={"provider": "ollama", "model": "qwen2.5:1.5b"}
    )
    assert missing_token_res.status_code == 400
    assert "session token is required" in missing_token_res.json()["detail"].lower()


# --------------------------------------------------------------------------
# 11. Lazy session expiration purges credentials from memory
# --------------------------------------------------------------------------
def test_11_lazy_session_expiration_purges_credentials():
    session_id = issue_session_token()
    set_session_config(
        session_id=session_id,
        provider="openai_compatible",
        api_key="sk-ephemeral-key-9999",
        model="gpt-4o"
    )

    # Active session returns credentials
    active = get_session_config(session_id, max_age_seconds=10)
    assert active["api_key"] == "sk-ephemeral-key-9999"

    # Simulated expiration: query with max_age_seconds=0
    expired = get_session_config(session_id, max_age_seconds=0)
    # Must immediately purge credentials and return safe default Ollama
    assert expired["provider"] == "ollama"
    assert expired["api_key"] is None

    # Subsequent check confirms expired session returns HTTP 400 Bad Request
    curr = client.get("/config/current", headers={"X-Session-ID": session_id})
    assert curr.status_code == 400
    assert "expired" in curr.json()["detail"].lower() or "unissued" in curr.json()["detail"].lower()


# --------------------------------------------------------------------------
# 12. Thread-safety under concurrent requests
# --------------------------------------------------------------------------
def test_12_concurrent_requests_thread_safety():
    errors = []

    def worker_task(idx):
        try:
            s_id = f"worker-session-{idx:04d}"
            register_session_token(s_id)
            # Write
            set_session_config(
                session_id=s_id,
                provider="openai_compatible",
                api_key=f"sk-test-{idx:04d}",
                model="gpt-4o"
            )
            # Read
            cfg = get_session_config(s_id)
            assert cfg["api_key"] == f"sk-test-{idx:04d}"
            # Clear half
            if idx % 2 == 0:
                clear_session_config(s_id)
        except Exception as e:
            errors.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker_task, i) for i in range(25)]
        concurrent.futures.wait(futures)

    # No concurrent modification or lock errors
    assert len(errors) == 0


# --------------------------------------------------------------------------
# 13. Deep copy prevents in-place mutation of session store
# --------------------------------------------------------------------------
def test_13_deep_copy_prevents_in_place_credential_mutation():
    session_id = issue_session_token()
    set_session_config(
        session_id=session_id,
        provider="openai_compatible",
        api_key="sk-original-key-1111"
    )

    # Caller receives copy and attempts in-place mutation
    retrieved = get_session_config(session_id)
    retrieved["api_key"] = "sk-hacked-mutated-key"

    # Internal store must remain untouched
    fresh = get_session_config(session_id)
    assert fresh["api_key"] == "sk-original-key-1111"


# --------------------------------------------------------------------------
# 14. Enhanced secret scrubbing redacts headers, tokens, and URLs
# --------------------------------------------------------------------------
def test_14_enhanced_secret_scrubbing_redacts_headers_tokens_and_urls():
    # Authorization header with Bearer token
    assert "Bearer [REDACTED]" in scrub_secrets("Authorization: Bearer sk-1234567890abcdef")

    # API key query parameters
    assert "api_key=[REDACTED]" in scrub_secrets("https://api.openai.com/v1/models?api_key=sk-1234567890abcdef")

    # OpenRouter and Groq key prefixes
    assert "[REDACTED_API_KEY]" in scrub_secrets("Error: sk-or-v1-abcdef1234567890 failed")
    assert "[REDACTED_API_KEY]" in scrub_secrets("Error: gsk_abcdef1234567890123 failed")

    # Explicit secret passed directly
    assert "[REDACTED]" in scrub_secrets("Custom error containing my_secret_token_123", "my_secret_token_123")


# --------------------------------------------------------------------------
# 15. Localhost Ollama documented as local-server and CORS configurable
# --------------------------------------------------------------------------
def test_15_cors_and_deployment_configuration():
    # Localhost development origins are allowed
    res = client.options(
        "/config/session",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST"
        }
    )
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"


# --------------------------------------------------------------------------
# 16. Custom API provider configuration and chat completion
# --------------------------------------------------------------------------
def test_16_custom_api_configuration_save_and_chat(monkeypatch):
    captured_request = {}

    def mock_post(url, *args, **kwargs):
        captured_request["url"] = url
        captured_request["json"] = kwargs.get("json")
        captured_request["headers"] = kwargs.get("headers")
        captured_request["allow_redirects"] = kwargs.get("allow_redirects")

        class MockResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Hello from custom API endpoint!"
                            }
                        }
                    ]
                }

        return MockResponse()

    monkeypatch.setattr("requests.post", mock_post)

    user_api_key = "custom-api-token-98765"
    register_session_token("session-custom-user")
    save_res = client.post(
        "/config/save",
        json={
            "session_id": "session-custom-user",
            "provider": "custom",
            "api_key": user_api_key,
            "model": "deepseek-coder-v2",
            "base_url": "https://93.184.216.34/v1"
        }
    )
    assert save_res.status_code == 200
    save_data = save_res.json()
    assert save_data["success"] is True
    assert save_data["config"]["provider"] == "custom"
    assert save_data["config"]["model"] == "deepseek-coder-v2"
    assert save_data["config"]["base_url"] == "https://93.184.216.34/v1"
    assert save_data["config"]["has_api_key"] is True
    assert save_data["config"]["masked_key"] == "••••••••8765"
    assert user_api_key not in str(save_data)

    # Perform chat completion for session-custom-user
    session_config = get_session_config("session-custom-user")
    result = chat_completion(
        messages=[{"role": "user", "content": "ping"}],
        session_config=session_config
    )
    assert result["content"] == "Hello from custom API endpoint!"
    assert captured_request["url"] == "https://93.184.216.34/v1/chat/completions"
    assert captured_request["headers"]["Authorization"] == f"Bearer {user_api_key}"
    assert captured_request["json"]["model"] == "deepseek-coder-v2"


# --------------------------------------------------------------------------
# 17. Custom API provider without API key (local proxy e.g. vLLM / LM Studio)
# --------------------------------------------------------------------------
def test_17_custom_api_without_api_key_for_local_proxy(monkeypatch):
    monkeypatch.setenv("ALLOW_LOCAL_CUSTOM_API", "true")
    captured_request = {}

    def mock_post(url, json=None, headers=None, timeout=None, allow_redirects=None):
        captured_request["url"] = url
        captured_request["headers"] = headers

        class MockResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Local proxy answer"
                            }
                        }
                    ]
                }

        return MockResponse()

    monkeypatch.setattr("requests.post", mock_post)

    register_session_token("session-local-proxy")
    save_res = client.post(
        "/config/save",
        json={
            "session_id": "session-local-proxy",
            "provider": "custom",
            "api_key": "",
            "model": "local-mistral-7b",
            "base_url": "http://localhost:8000/v1"
        }
    )
    assert save_res.status_code == 200
    cfg = save_res.json()["config"]
    assert cfg["provider"] == "custom"
    assert cfg["has_api_key"] is False

    session_config = get_session_config("session-local-proxy")
    result = chat_completion(
        messages=[{"role": "user", "content": "hello"}],
        session_config=session_config
    )
    assert result["content"] == "Local proxy answer"
    assert "Authorization" not in captured_request["headers"]


# --------------------------------------------------------------------------
# 18. Custom API validation rejects invalid base_url and missing model
# --------------------------------------------------------------------------
def test_18_custom_api_validation_rejects_invalid_inputs():
    register_session_token("invalid-url-sess")
    # Invalid base URL (missing http:// or https://)
    with pytest.raises(ValueError, match="valid Base URL"):
        set_session_config(
            session_id="invalid-url-sess",
            provider="custom",
            base_url="ftp://invalid.com/v1",
            model="llama-3"
        )

    register_session_token("empty-url-sess")
    # Empty base URL
    with pytest.raises(ValueError, match="valid Base URL"):
        set_session_config(
            session_id="empty-url-sess",
            provider="custom",
            base_url="",
            model="llama-3"
        )

    register_session_token("missing-model-sess")
    # Missing model
    with pytest.raises(ValueError, match="Model name is required"):
        set_session_config(
            session_id="missing-model-sess",
            provider="custom",
            base_url="https://93.184.216.34/v1",
            model=""
        )


# --------------------------------------------------------------------------
# 19. Custom API connection verification test endpoint
# --------------------------------------------------------------------------
def test_19_custom_api_connection_verification(monkeypatch):
    token = issue_session_token()

    # Test valid connection via GET /models
    def mock_get_models(url, headers=None, timeout=None, allow_redirects=None):
        class MockRes:
            status_code = 200
        return MockRes()

    monkeypatch.setattr("requests.get", mock_get_models)

    res = client.post(
        "/config/test",
        headers={"X-Session-ID": token},
        json={
            "provider": "custom",
            "base_url": "https://93.184.216.34/v1",
            "model": "custom-model",
            "api_key": "custom-key-123"
        }
    )
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Test invalid base_url returns 400
    bad_res = client.post(
        "/config/test",
        headers={"X-Session-ID": token},
        json={
            "provider": "custom",
            "base_url": "not-a-valid-url",
            "model": "custom-model"
        }
    )
    assert bad_res.status_code == 400
    assert "valid Base URL" in bad_res.json()["detail"]


# --------------------------------------------------------------------------
# 20. Custom API configuration reset to Ollama
# --------------------------------------------------------------------------
def test_20_custom_api_reset_to_ollama():
    register_session_token("reset-test-session")
    set_session_config(
        session_id="reset-test-session",
        provider="custom",
        base_url="https://93.184.216.34/v1",
        model="custom-m",
        api_key="secret-key"
    )
    assert get_session_config("reset-test-session")["provider"] == "custom"

    res = client.post(
        "/config/clear",
        json={"session_id": "reset-test-session"}
    )
    assert res.status_code == 200
    after_cfg = get_session_config("reset-test-session")
    assert after_cfg["provider"] == "ollama"
    assert after_cfg["api_key"] is None


# --------------------------------------------------------------------------
# 21. Custom API URL SSRF protection and strict validation
# --------------------------------------------------------------------------
def test_21_custom_api_url_ssrf_protection(monkeypatch):
    # 1. Valid public HTTPS endpoints accepted
    assert validate_custom_api_url("https://93.184.216.34/v1") == "https://93.184.216.34/v1"
    assert validate_custom_api_url("https://api.openai.com/v1") == "https://api.openai.com/v1"

    # 2. Malformed URLs rejected
    with pytest.raises(ValueError, match="valid host|Malformed|valid Base URL"):
        validate_custom_api_url("http://")
    with pytest.raises(ValueError, match="valid Base URL"):
        validate_custom_api_url("")

    # 3. Unsupported schemes rejected
    for bad_scheme in ["ftp://example.com/v1", "file:///etc/passwd", "gopher://evil.com"]:
        with pytest.raises(ValueError, match="Unsupported URL scheme|valid Base URL"):
            validate_custom_api_url(bad_scheme)

    # 4. Embedded credentials rejected
    with pytest.raises(ValueError, match="embedded user credentials"):
        validate_custom_api_url("https://user:pass@93.184.216.34/v1")

    # 5. Invalid ports rejected
    with pytest.raises(ValueError, match="out of valid range|invalid port number"):
        validate_custom_api_url("https://93.184.216.34:0/v1")
    with pytest.raises(ValueError, match="out of valid range|invalid port number"):
        validate_custom_api_url("https://93.184.216.34:70000/v1")

    # 6. Loopback HTTP allowed only when allow_local is True
    assert validate_custom_api_url("http://localhost:8000/v1", allow_local=True) == "http://localhost:8000/v1"
    assert validate_custom_api_url("http://127.0.0.1:8000/v1", allow_local=True) == "http://127.0.0.1:8000/v1"
    assert validate_custom_api_url("http://[::1]:8000/v1", allow_local=True) == "http://[::1]:8000/v1"

    # Loopback HTTP rejected when allow_local is False
    with pytest.raises(ValueError, match="disabled by policy"):
        validate_custom_api_url("http://localhost:8000/v1", allow_local=False)
    with pytest.raises(ValueError, match="disabled by policy"):
        validate_custom_api_url("http://127.0.0.1:8000/v1", allow_local=False)

    # 7. Private IPv4 addresses blocked
    for priv_ip in ["https://10.0.0.1/v1", "https://192.168.1.1/v1", "https://172.16.0.1/v1"]:
        with pytest.raises(ValueError, match="restricted range"):
            validate_custom_api_url(priv_ip)

    # 8. Cloud metadata destinations blocked
    with pytest.raises(ValueError, match="cloud metadata service|restricted range"):
        validate_custom_api_url("http://169.254.169.254/latest/meta-data")
    with pytest.raises(ValueError, match="cloud metadata service"):
        validate_custom_api_url("http://metadata.google.internal/computeMetadata/v1")
    with pytest.raises(ValueError, match="cloud metadata service"):
        validate_custom_api_url("http://metadata/computeMetadata/v1")

    # 9. IPv6 restricted addresses blocked
    for priv_v6 in ["https://[fc00::1]/v1", "https://[fe80::1]/v1", "https://[fd00:ec2::254]/v1"]:
        with pytest.raises(ValueError, match="cloud metadata service|restricted range"):
            validate_custom_api_url(priv_v6)

    # 10. DNS resolution to private IP rejected
    def mock_private_dns(host, port, proto=None):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.0.0.99', port))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_private_dns)
    with pytest.raises(ValueError, match="resolves to restricted IP address"):
        validate_custom_api_url("https://malicious-internal-domain.org/v1")


# --------------------------------------------------------------------------
# 22. Outbound redirect protection and credential safety
# --------------------------------------------------------------------------
def test_22_redirect_and_credential_protection(monkeypatch):
    class MockRedirectResponse:
        status_code = 302
        is_redirect = True
        headers = {"Location": "http://evil-attacker.com/steal-credentials"}

        def raise_for_status(self):
            pass

    # 1. Connection verification GET /models rejects redirect
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockRedirectResponse())
    verify_res = verify_provider_connection(
        provider="custom",
        base_url="https://93.184.216.34/v1",
        model="custom-m",
        api_key="secret-credential"
    )
    assert verify_res["success"] is False
    assert "Redirects are not permitted" in verify_res["detail"]

    # 2. Connection verification fallback POST /chat/completions rejects redirect
    class Mock404Response:
        status_code = 404
        is_redirect = False

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: Mock404Response())
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: MockRedirectResponse())

    fallback_res = verify_provider_connection(
        provider="custom",
        base_url="https://93.184.216.34/v1",
        model="custom-m",
        api_key="secret-credential"
    )
    assert fallback_res["success"] is False
    assert "Redirects are not permitted" in fallback_res["detail"]

    # 3. Chat completion rejects redirect with safe error
    with pytest.raises(RuntimeError, match="Redirects are not permitted"):
        chat_completion(
            messages=[{"role": "user", "content": "hello"}],
            session_config={
                "provider": "custom",
                "base_url": "https://93.184.216.34/v1",
                "model": "custom-m",
                "api_key": "confidential-bearer-token"
            }
        )


# --------------------------------------------------------------------------
# 23. Authoritative server-side session registry lifecycle
# --------------------------------------------------------------------------
def test_23_authoritative_session_registry_lifecycle():
    # 1. Server issues authoritative token
    sess_res = client.post("/config/session")
    assert sess_res.status_code == 200
    issued_id = sess_res.json()["session_id"]
    assert is_session_issued(issued_id) is True

    # 2. Unissued arbitrary session ID rejected on POST /config/save
    unissued_save = client.post(
        "/config/save",
        json={
            "session_id": "unissued-arbitrary-token-12345678",
            "provider": "ollama",
            "model": "qwen2.5:1.5b"
        }
    )
    assert unissued_save.status_code == 400
    assert "Invalid or unissued session token" in unissued_save.json()["detail"]

    # 3. Saving with issued token succeeds
    valid_save = client.post(
        "/config/save",
        json={
            "session_id": issued_id,
            "provider": "groq",
            "api_key": "gsk-mock-key-12345",
            "model": "llama-3.3-70b-versatile"
        }
    )
    assert valid_save.status_code == 200
    assert valid_save.json()["config"]["session_id"] == issued_id

    # 4. Unissued session ID rejected on GET /config/current
    unissued_curr = client.get("/config/current", headers={"X-Session-ID": "unissued-token-99999999"})
    assert unissued_curr.status_code == 400

    # 5. Issued active session returns configuration
    valid_curr = client.get("/config/current", headers={"X-Session-ID": issued_id})
    assert valid_curr.status_code == 200
    assert valid_curr.json()["provider"] == "groq"
    assert valid_curr.json()["has_api_key"] is True

    # 6. Clearing invalidates session token from registry
    clear_res = client.post("/config/clear", headers={"X-Session-ID": issued_id})
    assert clear_res.status_code == 200
    assert clear_res.json()["cleared"] is True

    # 7. Cleared session token is now unissued and rejected
    post_clear_res = client.get("/config/current", headers={"X-Session-ID": issued_id})
    assert post_clear_res.status_code == 400
    assert "Invalid or unissued" in post_clear_res.json()["detail"]


# --------------------------------------------------------------------------
# 24. API session transport via X-Session-ID header
# --------------------------------------------------------------------------
def test_24_session_transport_via_header():
    # Issue session
    token = client.post("/config/session").json()["session_id"]

    # 1. Save config using X-Session-ID header without body session_id
    save_res = client.post(
        "/config/save",
        headers={"X-Session-ID": token},
        json={
            "provider": "groq",
            "api_key": "gsk-header-token-1111",
            "model": "llama-3.3-70b-versatile"
        }
    )
    assert save_res.status_code == 200
    assert save_res.json()["config"]["session_id"] == token

    # 2. Get current config using X-Session-ID header without query params
    curr_res = client.get("/config/current", headers={"X-Session-ID": token})
    assert curr_res.status_code == 200
    assert curr_res.json()["session_id"] == token
    assert curr_res.json()["provider"] == "groq"

    # 3. Analyze endpoint accepts X-Session-ID header
    csv_content = b"col1,col2\n10,20\n30,40"
    analyze_res = client.post(
        "/analyze",
        headers={"X-Session-ID": token},
        data={"question": "What is the summary of this data?"},
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    )
    # The analyze endpoint processes the request with the session
    assert analyze_res.status_code in [200, 503]  # 503 if provider mock not active, but auth passed

    # 3b. Analyze endpoint gracefully falls back to default engine if session is unissued
    unissued_analyze = client.post(
        "/analyze",
        headers={"X-Session-ID": "unissued-stale-session-token-9999"},
        data={"question": "What is the summary of this data?"},
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    )
    # Must NOT fail with 400 "Invalid or unissued session token"
    assert unissued_analyze.status_code != 400
    assert unissued_analyze.status_code in [200, 503]

    # 4. Clear config using X-Session-ID header without body session_id
    clear_res = client.post("/config/clear", headers={"X-Session-ID": token})
    assert clear_res.status_code == 200
    assert clear_res.json()["cleared"] is True


# --------------------------------------------------------------------------
# 25. Secrets absent from logs, error messages, and API responses
# --------------------------------------------------------------------------
def test_25_scrub_secrets_comprehensive():
    # 1. Bearer tokens in exception messages
    raw_exc = "HTTPConnectionPool(host='93.184.216.34', port=443): Max retries exceeded with url: /chat/completions (Caused by NewConnectionError: Authorization: Bearer sk-secret-token-abcdef123456)"
    scrubbed = scrub_secrets(raw_exc, "sk-secret-token-abcdef123456")
    assert "sk-secret-token-abcdef123456" not in scrubbed
    assert "[REDACTED]" in scrubbed

    # 2. Key in failed verification probe
    token = issue_session_token()
    bad_res = client.post(
        "/config/test",
        headers={"X-Session-ID": token},
        json={
            "provider": "openai_compatible",
            "api_key": "sk-super-secret-probe-key-12345",
            "base_url": "https://93.184.216.34/v1",
            "model": "gpt-4o"
        }
    )
    # The connection to 93.184.216.34 will fail or time out
    assert bad_res.status_code == 400
    assert "sk-super-secret-probe-key-12345" not in bad_res.text
    assert "sk-super-secret-probe-key-12345" not in str(bad_res.json())


# --------------------------------------------------------------------------
# 26. Ollama Base URL targeting private IPs is rejected
# --------------------------------------------------------------------------
def test_26_ollama_url_targeting_private_ips_rejected():
    token = issue_session_token()
    private_endpoints = [
        "http://10.0.0.1:11434",
        "http://192.168.1.1:11434",
        "http://172.16.0.1:11434",
    ]

    for endpoint in private_endpoints:
        # 1. Direct function check
        res = verify_provider_connection(
            provider="ollama",
            base_url=endpoint,
            model="qwen2.5:1.5b"
        )
        assert res["success"] is False
        assert "restricted range" in res["detail"] or "must use HTTPS" in res["detail"]

        # 2. Endpoint POST /config/test check
        api_res = client.post(
            "/config/test",
            headers={"X-Session-ID": token},
            json={
                "provider": "ollama",
                "base_url": endpoint,
                "model": "qwen2.5:1.5b"
            }
        )
        assert api_res.status_code == 400
        assert "restricted range" in api_res.json()["detail"] or "must use HTTPS" in api_res.json()["detail"]

        # 3. Direct set_session_config rejection
        with pytest.raises(ValueError, match="restricted range|must use HTTPS"):
            set_session_config(
                session_id=token,
                provider="ollama",
                base_url=endpoint,
                model="qwen2.5:1.5b"
            )


# --------------------------------------------------------------------------
# 27. Ollama Base URL targeting cloud metadata services is rejected
# --------------------------------------------------------------------------
def test_27_ollama_url_targeting_cloud_metadata_rejected():
    token = issue_session_token()
    metadata_endpoints = [
        "http://169.254.169.254/latest/meta-data",
        "http://metadata.google.internal/computeMetadata/v1",
        "http://metadata/computeMetadata/v1",
    ]

    for endpoint in metadata_endpoints:
        # 1. verify_provider_connection rejection
        res = verify_provider_connection(
            provider="ollama",
            base_url=endpoint,
            model="qwen2.5:1.5b"
        )
        assert res["success"] is False
        assert "cloud metadata service" in res["detail"] or "must use HTTPS" in res["detail"]

        # 2. POST /config/test rejection
        api_res = client.post(
            "/config/test",
            headers={"X-Session-ID": token},
            json={
                "provider": "ollama",
                "base_url": endpoint,
                "model": "qwen2.5:1.5b"
            }
        )
        assert api_res.status_code == 400
        assert "cloud metadata service" in api_res.json()["detail"] or "must use HTTPS" in api_res.json()["detail"]


# --------------------------------------------------------------------------
# 28. Remote provider endpoints require HTTPS (no plaintext HTTP)
# --------------------------------------------------------------------------
def test_28_remote_provider_endpoints_require_https():
    token = issue_session_token()
    remote_http_urls = [
        ("ollama", "http://remote-ollama-node.org:11434"),
        ("custom", "http://remote-openai-proxy.org/v1"),
    ]

    for provider, remote_url in remote_http_urls:
        res = verify_provider_connection(
            provider=provider,
            base_url=remote_url,
            model="test-model"
        )
        assert res["success"] is False
        assert "Provider endpoints for remote destinations must use HTTPS." in res["detail"]

        api_res = client.post(
            "/config/test",
            headers={"X-Session-ID": token},
            json={
                "provider": provider,
                "base_url": remote_url,
                "model": "test-model"
            }
        )
        assert api_res.status_code == 400
        assert "Provider endpoints for remote destinations must use HTTPS." in api_res.json()["detail"]


# --------------------------------------------------------------------------
# 29. Ollama connection test rejects HTTP redirects
# --------------------------------------------------------------------------
def test_29_ollama_rejects_http_redirects(monkeypatch):
    class MockRedirectResponse:
        status_code = 302
        is_redirect = True

        def raise_for_status(self):
            pass

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockRedirectResponse())

    token = issue_session_token()
    # Permit loopback so we test redirect behavior
    monkeypatch.setenv("ALLOW_LOCAL_CUSTOM_API", "true")

    res = verify_provider_connection(
        provider="ollama",
        base_url="http://localhost:11434",
        model="qwen2.5:1.5b"
    )
    assert res["success"] is False
    assert "Redirects are not permitted" in res["detail"]

    api_res = client.post(
        "/config/test",
        headers={"X-Session-ID": token},
        json={
            "provider": "ollama",
            "base_url": "http://localhost:11434",
            "model": "qwen2.5:1.5b"
        }
    )
    assert api_res.status_code == 400
    assert "Redirects are not permitted" in api_res.json()["detail"]


# --------------------------------------------------------------------------
# 30. POST /config/test session token enforcement
# --------------------------------------------------------------------------
def test_30_config_test_session_token_enforcement():
    # 1. Missing token
    res_missing = client.post(
        "/config/test",
        json={"provider": "ollama", "model": "qwen2.5:1.5b"}
    )
    assert res_missing.status_code == 400
    assert "session token is required" in res_missing.json()["detail"].lower()

    # 2. Invalid format token
    res_bad_format = client.post(
        "/config/test",
        headers={"X-Session-ID": "bad"},
        json={"provider": "ollama", "model": "qwen2.5:1.5b"}
    )
    assert res_bad_format.status_code == 400
    assert "Invalid session_id format" in res_bad_format.json()["detail"]

    # 3. Unissued valid format token
    res_unissued = client.post(
        "/config/test",
        headers={"X-Session-ID": "unissued-token-abcdef12345678"},
        json={"provider": "ollama", "model": "qwen2.5:1.5b"}
    )
    assert res_unissued.status_code == 400
    assert "Invalid or unissued session token" in res_unissued.json()["detail"]

    # 4. Expired token
    expired_token = register_session_token("expired-session-token-1111", ttl_seconds=0)
    time.sleep(0.01)
    res_expired = client.post(
        "/config/test",
        headers={"X-Session-ID": expired_token},
        json={"provider": "ollama", "model": "qwen2.5:1.5b"}
    )
    assert res_expired.status_code == 400
    assert "expired" in res_expired.json()["detail"].lower()


# --------------------------------------------------------------------------
# 31. POST /config/save session token enforcement
# --------------------------------------------------------------------------
def test_31_config_save_session_token_enforcement():
    # 1. Missing token
    res_missing = client.post(
        "/config/save",
        json={"provider": "ollama", "model": "qwen2.5:1.5b"}
    )
    assert res_missing.status_code == 400
    assert "session token is required" in res_missing.json()["detail"].lower()

    # 2. Invalid format token
    res_bad_format = client.post(
        "/config/save",
        headers={"X-Session-ID": "bad"},
        json={"provider": "ollama", "model": "qwen2.5:1.5b"}
    )
    assert res_bad_format.status_code == 400
    assert "Invalid session_id format" in res_bad_format.json()["detail"]

    # 3. Unissued valid format token
    res_unissued = client.post(
        "/config/save",
        headers={"X-Session-ID": "unissued-token-abcdef12345678"},
        json={"provider": "ollama", "model": "qwen2.5:1.5b"}
    )
    assert res_unissued.status_code == 400
    assert "Invalid or unissued session token" in res_unissued.json()["detail"]

    # 4. Expired token
    expired_token = register_session_token("expired-save-token-2222", ttl_seconds=0)
    time.sleep(0.01)
    res_expired = client.post(
        "/config/save",
        headers={"X-Session-ID": expired_token},
        json={"provider": "ollama", "model": "qwen2.5:1.5b"}
    )
    assert res_expired.status_code == 400
    assert "expired" in res_expired.json()["detail"].lower()


# --------------------------------------------------------------------------
# 32. Sliding window rate limiting on POST /config/test per session
# --------------------------------------------------------------------------
def test_32_config_test_rate_limiting_per_session(monkeypatch):
    class MockSuccess:
        status_code = 200
        is_redirect = False

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockSuccess())

    token = issue_session_token()

    # First 10 requests within window must succeed
    for i in range(10):
        res = client.post(
            "/config/test",
            headers={"X-Session-ID": token},
            json={
                "provider": "custom",
                "base_url": "https://93.184.216.34/v1",
                "model": "model-1",
                "api_key": "test-key"
            }
        )
        assert res.status_code == 200, f"Request {i+1} failed with {res.status_code}: {res.text}"

    # 11th request must be rejected with HTTP 429
    res_11 = client.post(
        "/config/test",
        headers={"X-Session-ID": token},
        json={
            "provider": "custom",
            "base_url": "https://93.184.216.34/v1",
            "model": "model-1",
            "api_key": "test-key"
        }
    )
    assert res_11.status_code == 429
    assert "Too many connection test requests for this session" in res_11.json()["detail"]


# --------------------------------------------------------------------------
# 33. Sliding window rate limiting on POST /config/test per client IP
# --------------------------------------------------------------------------
def test_33_config_test_rate_limiting_per_ip(monkeypatch):
    class MockSuccess:
        status_code = 200
        is_redirect = False

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockSuccess())

    # Send 20 requests using distinct sessions from the same IP (testclient host: 'testclient')
    for i in range(20):
        token = issue_session_token()
        res = client.post(
            "/config/test",
            headers={"X-Session-ID": token},
            json={
                "provider": "custom",
                "base_url": "https://93.184.216.34/v1",
                "model": "model-1",
                "api_key": "test-key"
            }
        )
        assert res.status_code == 200, f"Request {i+1} failed with {res.status_code}: {res.text}"

    # 21st request from same IP must be rejected with HTTP 429
    new_token = issue_session_token()
    res_21 = client.post(
        "/config/test",
        headers={"X-Session-ID": new_token},
        json={
            "provider": "custom",
            "base_url": "https://93.184.216.34/v1",
            "model": "model-1",
            "api_key": "test-key"
        }
    )
    assert res_21.status_code == 429
    assert "Too many connection test requests from this IP address" in res_21.json()["detail"]


# --------------------------------------------------------------------------
# 34. set_session_config() rejects unknown and expired session IDs directly
# --------------------------------------------------------------------------
def test_34_set_session_config_rejects_unknown_and_expired_tokens():
    # 1. Unknown token must raise ValueError and never be auto-registered
    with pytest.raises(ValueError, match="Invalid or unissued session token"):
        set_session_config(
            session_id="unissued-token-99999999",
            provider="ollama",
            model="qwen2.5:1.5b"
        )

    # Confirm it was not added to _ISSUED_SESSIONS or _USER_SESSIONS
    assert is_session_issued("unissued-token-99999999") is False
    assert get_session_config("unissued-token-99999999")["provider"] == "ollama"

    # 2. Expired token cannot be revived by saving configuration
    expired_id = register_session_token("expired-direct-test-token", ttl_seconds=0)
    time.sleep(0.01)
    with pytest.raises(ValueError, match="Session token has expired|Invalid or unissued session token"):
        set_session_config(
            session_id=expired_id,
            provider="groq",
            api_key="gsk-mock-key-1234",
            model="llama-3.3-70b-versatile"
        )


# --------------------------------------------------------------------------
# 35. Local Ollama development configuration toggle
# --------------------------------------------------------------------------
def test_35_local_ollama_dev_configuration_toggle(monkeypatch):
    # 1. Default policy (ALLOW_LOCAL_CUSTOM_API=false): loopback is blocked
    monkeypatch.setenv("ALLOW_LOCAL_CUSTOM_API", "false")
    with pytest.raises(ValueError, match="Localhost/loopback destinations are disabled by policy"):
        validate_custom_api_url("http://localhost:11434")

    token = issue_session_token()
    blocked_res = client.post(
        "/config/test",
        headers={"X-Session-ID": token},
        json={
            "provider": "ollama",
            "base_url": "http://localhost:11434",
            "model": "qwen2.5:1.5b"
        }
    )
    assert blocked_res.status_code == 400
    assert "Localhost/loopback destinations are disabled by policy" in blocked_res.json()["detail"]

    # 2. Local development mode enabled (ALLOW_LOCAL_CUSTOM_API=true): loopback is permitted
    monkeypatch.setenv("ALLOW_LOCAL_CUSTOM_API", "true")
    assert validate_custom_api_url("http://localhost:11434") == "http://localhost:11434"

    class MockOllama200:
        status_code = 200
        is_redirect = False

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockOllama200())

    allowed_res = client.post(
        "/config/test",
        headers={"X-Session-ID": token},
        json={
            "provider": "ollama",
            "base_url": "http://localhost:11434",
            "model": "qwen2.5:1.5b"
        }
    )
    assert allowed_res.status_code == 200
    assert allowed_res.json()["success"] is True


# --------------------------------------------------------------------------
# 36. Secret redaction and no upstream response body leakage
# --------------------------------------------------------------------------
def test_36_secret_redaction_and_no_upstream_response_body_leak(monkeypatch):
    class Mock502InternalLeak:
        status_code = 502
        is_redirect = False
        text = '{"error": "Internal database crashed", "stack": "at /var/secret/keys.py", "internal_ip": "10.10.10.10"}'

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: Mock502InternalLeak())

    token = issue_session_token()
    res = client.post(
        "/config/test",
        headers={"X-Session-ID": token},
        json={
            "provider": "custom",
            "base_url": "https://93.184.216.34/v1",
            "model": "custom-model",
            "api_key": "sk-secret-leak-key-12345"
        }
    )
    assert res.status_code == 400
    detail = res.json()["detail"]
    # Check that generic status is returned, and upstream raw body is NOT reflected
    assert detail == "Custom API returned HTTP status 502."
    assert "Internal database crashed" not in detail
    assert "keys.py" not in detail
    assert "10.10.10.10" not in detail
    assert "sk-secret-leak-key-12345" not in detail


