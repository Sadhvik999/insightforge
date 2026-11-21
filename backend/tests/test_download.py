import io
import time
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.export_store import (
    save_cleaned_export,
    get_cleaned_export,
    cleanup_expired_exports,
    clear_all_exports,
    EXPORT_DIR,
)

client = TestClient(app)


def setup_function():
    clear_all_exports()


def teardown_function():
    clear_all_exports()


# --------------------------------------------------------------------------
# 1. Successful cleaning generates a downloadable CSV
# --------------------------------------------------------------------------
def test_01_successful_cleaning_generates_downloadable_csv():
    csv_data = "ID,Score,Status\n1,10.5,active\n2,20.0,pending\n"
    files = {"file": ("students.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}

    response = client.post("/clean", files=files)
    assert response.status_code == 200
    data = response.json()

    assert "download_id" in data
    assert "download_url" in data
    assert "download_filename" in data
    assert data["download_filename"] == "students_cleaned.csv"
    assert data["download_url"] == f"/clean/download/{data['download_id']}"

    # Request the download endpoint
    dl_response = client.get(data["download_url"])
    assert dl_response.status_code == 200
    assert "text/csv" in dl_response.headers.get("content-type", "")
    assert 'filename="students_cleaned.csv"' in dl_response.headers.get("content-disposition", "")
    assert len(dl_response.text) > 0


# --------------------------------------------------------------------------
# 2. Downloaded CSV contains the cleaned data
# --------------------------------------------------------------------------
def test_02_downloaded_csv_contains_cleaned_data():
    csv_data = "Name,Age,Salary\nAlice,30,70000\nBob,25,50000\nCharlie,35,90000\n"
    files = {"file": ("employees.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}

    response = client.post("/clean", files=files)
    assert response.status_code == 200
    dl_url = response.json()["download_url"]

    dl_response = client.get(dl_url)
    assert dl_response.status_code == 200

    df_cleaned = pd.read_csv(io.StringIO(dl_response.text))
    assert len(df_cleaned) == 3
    assert list(df_cleaned.columns) == ["Name", "Age", "Salary"]
    assert df_cleaned.iloc[0]["Name"] == "Alice"
    assert df_cleaned.iloc[1]["Salary"] == 50000


# --------------------------------------------------------------------------
# 3. Downloaded CSV does not contain columns dropped by the >=75% rule
# --------------------------------------------------------------------------
def test_03_downloaded_csv_does_not_contain_dropped_columns():
    # 4 rows: Sparse has 3 nulls out of 4 (75% missing -> dropped)
    # Valid has 0 nulls -> kept
    csv_data = "ID,Valid,Sparse\n1,100,A\n2,200,NaN\n3,300,NaN\n4,400,NaN\n"
    files = {"file": ("data.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}

    response = client.post("/clean", files=files, data={"threshold": "75.0"})
    assert response.status_code == 200
    data = response.json()
    assert "Sparse" not in data["columns"]

    dl_response = client.get(data["download_url"])
    assert dl_response.status_code == 200
    df_downloaded = pd.read_csv(io.StringIO(dl_response.text))

    assert "Sparse" not in df_downloaded.columns
    assert "Valid" in df_downloaded.columns
    assert "ID" in df_downloaded.columns
    assert len(df_downloaded.columns) == 2


# --------------------------------------------------------------------------
# 4. Downloaded CSV reflects numerical and categorical imputation
# --------------------------------------------------------------------------
def test_04_downloaded_csv_reflects_numerical_and_categorical_imputation():
    # ID is 1, 2, 3 (ensures row 3 is not an entirely empty row)
    # Num has 10, 20, NaN -> median = 15.0
    # Cat has 'X', 'X', NaN -> mode = 'X'
    csv_data = "ID,Num,Cat\n1,10.0,X\n2,20.0,X\n3,NaN,NaN\n"
    files = {"file": ("impute.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}

    response = client.post(
        "/clean",
        files=files,
        data={"threshold": "75.0", "numerical_strategy": "median"}
    )
    assert response.status_code == 200
    dl_response = client.get(response.json()["download_url"])
    df_downloaded = pd.read_csv(io.StringIO(dl_response.text))

    # All missing values must be imputed in downloaded CSV
    assert df_downloaded["Num"].isna().sum() == 0
    assert df_downloaded["Cat"].isna().sum() == 0
    assert df_downloaded.loc[2, "Num"] == 15.0
    assert df_downloaded.loc[2, "Cat"] == "X"
    assert len(df_downloaded) == 3


# --------------------------------------------------------------------------
# 5. Downloaded CSV reflects duplicate removal
# --------------------------------------------------------------------------
def test_05_downloaded_csv_reflects_duplicate_removal():
    csv_data = "ID,Value\n1,10\n1,10\n1,10\n2,20\n"
    files = {"file": ("dups.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}

    response = client.post(
        "/clean",
        files=files,
        data={"remove_duplicates": "true"}
    )
    assert response.status_code == 200
    assert response.json()["cleaned_rows"] == 2

    dl_response = client.get(response.json()["download_url"])
    df_downloaded = pd.read_csv(io.StringIO(dl_response.text))
    assert len(df_downloaded) == 2
    assert list(df_downloaded["ID"]) == [1, 2]


# --------------------------------------------------------------------------
# 6. Downloaded CSV reflects configured outlier treatment
# --------------------------------------------------------------------------
def test_06_downloaded_csv_reflects_outlier_treatment():
    # Dataset with 10 values: 10 to 19, plus one massive outlier 1000.0
    rows = [f"1,{i}" for i in range(10, 20)] + ["1,1000.0"]
    csv_data = "ID,Metric\n" + "\n".join(rows) + "\n"

    # Test outlier capping
    files_cap = {"file": ("outliers.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    res_cap = client.post(
        "/clean",
        files=files_cap,
        data={"outlier_treatment": "cap"}
    )
    assert res_cap.status_code == 200
    dl_cap = client.get(res_cap.json()["download_url"])
    df_cap = pd.read_csv(io.StringIO(dl_cap.text))
    # Extreme 1000.0 should be capped below 1000
    assert df_cap["Metric"].max() < 1000.0
    assert len(df_cap) == 11

    # Test outlier removal
    files_rem = {"file": ("outliers.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    res_rem = client.post(
        "/clean",
        files=files_rem,
        data={"outlier_treatment": "remove"}
    )
    assert res_rem.status_code == 200
    dl_rem = client.get(res_rem.json()["download_url"])
    df_rem = pd.read_csv(io.StringIO(dl_rem.text))
    # Outlier row should be deleted
    assert len(df_rem) == 10
    assert df_rem["Metric"].max() <= 19.0


# --------------------------------------------------------------------------
# 7. Downloaded CSV does not contain an unwanted DataFrame index
# --------------------------------------------------------------------------
def test_07_downloaded_csv_does_not_contain_unwanted_dataframe_index():
    csv_data = "Alpha,Beta,Gamma\n1,2,3\n4,5,6\n"
    files = {"file": ("test_index.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}

    response = client.post("/clean", files=files)
    assert response.status_code == 200
    dl_response = client.get(response.json()["download_url"])

    raw_csv = dl_response.text
    first_line = raw_csv.strip().split("\n")[0]
    assert first_line == "Alpha,Beta,Gamma"
    assert "Unnamed: 0" not in first_line

    df_downloaded = pd.read_csv(io.StringIO(raw_csv))
    assert list(df_downloaded.columns) == ["Alpha", "Beta", "Gamma"]
    assert len(df_downloaded.columns) == 3


# --------------------------------------------------------------------------
# 8. Invalid download ID returns HTTP 404
# --------------------------------------------------------------------------
def test_08_invalid_download_id_returns_404():
    # Non-existent download ID
    res = client.get("/clean/download/0123456789abcdef0123456789abcdef")
    assert res.status_code == 404
    assert "not found or has expired" in res.json()["detail"].lower()

    # Path traversal attack attempt
    res_traversal = client.get("/clean/download/../../etc/passwd")
    assert res_traversal.status_code == 404

    # Invalid characters in ID
    res_invalid_chars = client.get("/clean/download/bad!id@chars#")
    assert res_invalid_chars.status_code == 404


# --------------------------------------------------------------------------
# 9. Expired download returns HTTP 404
# --------------------------------------------------------------------------
def test_09_expired_download_returns_404():
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    # Save with 0 seconds TTL (already expired)
    download_id, _, _ = save_cleaned_export(df, original_filename="expired.csv", ttl_seconds=0)

    # Allow clock to tick slightly so now - created_at > ttl
    time.sleep(0.01)

    dl_response = client.get(f"/clean/download/{download_id}")
    assert dl_response.status_code == 404
    assert "expired" in dl_response.json()["detail"].lower()


# --------------------------------------------------------------------------
# 10. Multiple downloads do not overwrite one another
# --------------------------------------------------------------------------
def test_10_multiple_downloads_do_not_overwrite_one_another():
    csv1 = "ColA\n100\n200\n"
    csv2 = "ColB\n999\n888\n"

    # Upload two files both named 'data.csv' but with different content
    files1 = {"file": ("data.csv", io.BytesIO(csv1.encode("utf-8")), "text/csv")}
    files2 = {"file": ("data.csv", io.BytesIO(csv2.encode("utf-8")), "text/csv")}

    res1 = client.post("/clean", files=files1)
    res2 = client.post("/clean", files=files2)

    assert res1.status_code == 200
    assert res2.status_code == 200

    id1 = res1.json()["download_id"]
    id2 = res2.json()["download_id"]
    assert id1 != id2

    dl1 = client.get(f"/clean/download/{id1}")
    dl2 = client.get(f"/clean/download/{id2}")

    assert dl1.status_code == 200
    assert dl2.status_code == 200

    df1 = pd.read_csv(io.StringIO(dl1.text))
    df2 = pd.read_csv(io.StringIO(dl2.text))

    assert "ColA" in df1.columns
    assert "ColB" in df2.columns
    assert df1.iloc[0]["ColA"] == 100
    assert df2.iloc[0]["ColB"] == 999


# --------------------------------------------------------------------------
# 11. Existing POST /clean response behavior remains compatible
# --------------------------------------------------------------------------
def test_11_existing_post_clean_response_behavior_remains_compatible():
    csv_data = "X,Y\n1,10\n2,20\n"
    files = {"file": ("compat.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}

    response = client.post("/clean", files=files)
    assert response.status_code == 200
    data = response.json()

    # Verify all legacy keys exist with expected types
    assert isinstance(data["original_rows"], int)
    assert isinstance(data["cleaned_rows"], int)
    assert isinstance(data["original_columns"], int)
    assert isinstance(data["cleaned_columns"], int)
    assert isinstance(data["columns"], list)
    assert isinstance(data["cleaning_report"], dict)

    report = data["cleaning_report"]
    assert "missing_before" in report
    assert "missing_after" in report
    assert "duplicates_removed" in report
    assert "outliers" in report
    assert "converted_date_columns" in report
    assert "numerical_values_filled" in report
    assert "categorical_values_filled" in report


# --------------------------------------------------------------------------
# 12. Temporary exports are cleaned up
# --------------------------------------------------------------------------
def test_12_temporary_exports_are_cleaned_up():
    df = pd.DataFrame({"A": [1, 2]})
    download_id, _, path = save_cleaned_export(df, original_filename="cleanup_test.csv", ttl_seconds=0)

    assert path.exists()

    time.sleep(0.01)
    purged = cleanup_expired_exports(max_age_seconds=0)
    assert purged >= 1
    assert not path.exists()

    # Subsequent retrieval returns 404
    res = client.get(f"/clean/download/{download_id}")
    assert res.status_code == 404


# --------------------------------------------------------------------------
# 13. Empty datasets and zero remaining columns handled safely
# --------------------------------------------------------------------------
def test_13_empty_dataset_and_zero_remaining_columns():
    # Dataset where only column has 100% missing values -> 0 remaining columns
    csv_data = "AllNull\nNaN\nNaN\n"
    files = {"file": ("all_null.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}

    response = client.post("/clean", files=files, data={"threshold": "75.0"})
    assert response.status_code == 200
    data = response.json()
    assert data["cleaned_columns"] == 0

    dl_response = client.get(data["download_url"])
    assert dl_response.status_code == 200
