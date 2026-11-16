from fastapi.testclient import TestClient
from app.main import app


def test_health_check_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_cors_headers_for_allowed_origins():
    client = TestClient(app)

    # 1. Test Vite default origin
    response_5173 = client.options("/health", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET"
    })
    assert response_5173.status_code == 200
    assert response_5173.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # 2. Test React default origin
    response_3000 = client.options("/health", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    })
    assert response_3000.status_code == 200
    assert response_3000.headers.get("access-control-allow-origin") == "http://localhost:3000"

    # 3. Disallowed origin should not receive allow-origin header matching the rogue origin
    response_disallowed = client.options("/health", headers={
        "Origin": "http://malicious-site.com",
        "Access-Control-Request-Method": "GET"
    })
    assert response_disallowed.headers.get("access-control-allow-origin") != "http://malicious-site.com"
