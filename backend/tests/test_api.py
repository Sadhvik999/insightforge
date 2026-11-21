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


def test_clean_endpoint_success():
    import io
    client = TestClient(app)

    csv_data = (
        "Name,Age,Salary,Date\n"
        "Alice,25,50000,2023-01-01\n"
        "Bob,,60000,2023-01-02\n"
        "Charlie,30,70000,2023-01-03\n"
        "Alice,25,50000,2023-01-01\n"
    )

    response = client.post(
        "/clean",
        files={
            "file": ("test_dataset.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert data["original_rows"] == 4
    assert data["cleaned_rows"] == 3
    assert "cleaning_report" in data

    report = data["cleaning_report"]
    assert report["duplicates_removed"] == 1
    assert report["duplicates_before"]["duplicate_count"] == 1
    assert "Date" in report["converted_date_columns"]
    assert report["missing_before"]["Age"]["missing_count"] == 1
    assert report["missing_after"]["Age"]["missing_count"] == 0
    assert report["numerical_values_filled"]["Age"] == 1


def test_clean_endpoint_non_csv_rejection():
    import io
    client = TestClient(app)

    response = client.post(
        "/clean",
        files={
            "file": ("test_file.txt", io.BytesIO(b"Hello world"), "text/plain")
        }
    )

    assert response.status_code == 400
    assert "Only CSV files are supported" in response.json()["detail"]


def test_clean_endpoint_missing_file():
    client = TestClient(app)
    response = client.post("/clean")
    assert response.status_code == 422
