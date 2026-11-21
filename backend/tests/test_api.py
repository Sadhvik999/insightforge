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


def test_clean_endpoint_with_approved_drop_columns():
    import io
    client = TestClient(app)

    csv_data = (
        "ID,Sparse,Valid\n"
        "1,10.0,100\n"
        "2,,200\n"
        "3,,300\n"
        "4,,400\n"
    )

    response = client.post(
        "/clean",
        files={
            "file": ("test.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")
        },
        data={
            "threshold": "50.0",
            "approved_drop_columns": '["Sparse"]'
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "Sparse" not in data["columns"]
    intel = data["cleaning_report"]["missing_value_intelligence"]
    assert "Sparse" in intel["summary"]["columns_actually_removed"]
    assert intel["columns"]["Sparse"]["actual_action"] == "dropped"


def test_clean_endpoint_with_invalid_drop_columns_returns_400():
    import io
    client = TestClient(app)

    csv_data = "A,B\n1,2\n"

    response = client.post(
        "/clean",
        files={
            "file": ("test.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")
        },
        data={
            "approved_drop_columns": '["NonExistentColumn"]'
        }
    )

    assert response.status_code == 400
    assert "Invalid column" in response.json()["detail"]


def test_clean_endpoint_with_custom_threshold():
    import io
    client = TestClient(app)

    csv_data = (
        "ID,Col_60,Col_Valid\n"
        "1,10,100\n"
        "2,20,200\n"
        "3,,300\n"
        "4,,400\n"
        "5,,500\n"
    )

    # 3 out of 5 = 60% missing. With threshold=50, 60% >= 50%, so it is dropped by mandatory rule
    response = client.post(
        "/clean",
        files={
            "file": ("test.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")
        },
        data={
            "threshold": "50.0"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "Col_60" not in data["columns"]
    assert "Col_60" in data["cleaning_report"]["columns_dropped"]
    intel = data["cleaning_report"]["missing_value_intelligence"]
    assert "Col_60" in intel["high_missingness_columns"]
    assert "Col_60" in intel["recommended_drop_columns"]
    assert intel["columns"]["Col_60"]["actual_action"] == "dropped"


def test_clean_endpoint_invalid_threshold_returns_400():
    import io
    client = TestClient(app)

    csv_data = "A,B\n1,2\n"

    response = client.post(
        "/clean",
        files={
            "file": ("test.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")
        },
        data={
            "threshold": "150.0"
        }
    )

    assert response.status_code == 400
    assert "Threshold must be between 1 and 100" in response.json()["detail"]


def test_clean_endpoint_zero_and_negative_threshold_returns_400():
    import io
    client = TestClient(app)

    csv_data = "A,B\n1,2\n"

    for bad_threshold in ["0", "-10", "0.99", "100.1"]:
        response = client.post(
            "/clean",
            files={
                "file": ("test.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")
            },
            data={
                "threshold": bad_threshold
            }
        )
        assert response.status_code == 400
        assert "Threshold must be between 1 and 100" in response.json()["detail"]


def test_clean_endpoint_invalid_numerical_strategy_returns_400():
    import io
    client = TestClient(app)

    csv_data = "A,B\n1,2\n"

    response = client.post(
        "/clean",
        files={
            "file": ("test.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")
        },
        data={
            "numerical_strategy": "invalid_strategy"
        }
    )

    assert response.status_code == 400
    assert "Invalid numerical strategy" in response.json()["detail"]


def test_clean_endpoint_invalid_outlier_treatment_returns_400():
    import io
    client = TestClient(app)

    csv_data = "A,B\n1,2\n"

    response = client.post(
        "/clean",
        files={
            "file": ("test.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")
        },
        data={
            "outlier_treatment": "invalid_treatment"
        }
    )

    assert response.status_code == 400
    assert "Invalid outlier treatment" in response.json()["detail"]


def test_clean_endpoint_with_outlier_capping():
    import io
    client = TestClient(app)

    csv_data = (
        "Val\n"
        "10.0\n12.0\n11.0\n13.0\n12.0\n11.0\n14.0\n12.0\n100.0\n"
    )

    response = client.post(
        "/clean",
        files={
            "file": ("test.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")
        },
        data={
            "outlier_treatment": "cap"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["cleaning_report"]["outlier_treatment"] == "cap"
    assert data["cleaning_report"]["outliers_affected"] == 1
