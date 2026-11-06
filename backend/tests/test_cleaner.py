
import pandas as pd
import pytest

from app.cleaner import (
    detect_missing_values,
    detect_duplicates,
    detect_outliers,
    detect_date_columns,
    convert_date_columns,
    fill_missing_values,
    fill_missing_categorical,
    remove_duplicates,
    clean_dataset
)


# 1. Test missing value detection
def test_detect_missing_values():
    df = pd.DataFrame({
        "Name": ["A", "B", None],
        "Age": [20, None, 30]
    })

    result = detect_missing_values(df)

    assert result["Name"]["missing_count"] == 1
    assert result["Age"]["missing_count"] == 1
    assert result["Name"]["missing_percentage"] == pytest.approx(33.33, abs=0.01)


# 2. Test duplicate detection
def test_detect_duplicates():
    df = pd.DataFrame({
        "Name": ["A", "B", "A"],
        "Age": [20, 30, 20]
    })

    result = detect_duplicates(df)

    assert result["duplicate_count"] == 1
    assert result["duplicate_percentage"] == pytest.approx(33.33, abs=0.01)


# 3. Test outlier detection
def test_detect_outliers():
    df = pd.DataFrame({
        "Salary": [10, 12, 11, 13, 12, 100]
    })

    result = detect_outliers(df)

    assert result["Salary"]["outlier_count"] == 1


# 4. Test date column detection
def test_detect_date_columns():
    df = pd.DataFrame({
        "Date": ["2024-01-01", "2024-02-01", "2024-03-01"],
        "Name": ["A", "B", "C"]
    })

    result = detect_date_columns(df)

    assert "Date" in result
    assert "Name" not in result


# 5. Test date conversion
def test_convert_date_columns():
    df = pd.DataFrame({
        "Date": ["2024-01-01", "2024-02-01"]
    })

    original_df = df.copy(deep=True)

    cleaned_df = convert_date_columns(df, ["Date"])

    # Converted DataFrame should contain datetime values
    assert pd.api.types.is_datetime64_any_dtype(cleaned_df["Date"])

    # Original DataFrame should remain unchanged
    pd.testing.assert_frame_equal(df, original_df)

    # Function should return a separate DataFrame
    assert cleaned_df is not df


# 6. Test numerical missing value imputation
def test_fill_missing_values():
    df = pd.DataFrame({
        "Age": [20, None, 40]
    })

    cleaned_df, skipped_columns, filled_counts = fill_missing_values(
        df,
        strategy="median"
    )

    assert cleaned_df["Age"].isnull().sum() == 0
    assert cleaned_df["Age"].iloc[1] == 30
    assert filled_counts["Age"] == 1
    assert skipped_columns == []
    assert pd.isnull(df["Age"].iloc[1])


# 7. Test all-null numerical column
def test_fill_missing_values_all_null_column():
    df = pd.DataFrame({
        "Age": pd.Series([None, None, None], dtype="float64"),
        "Salary": [30000, 40000, 50000]
    })

    cleaned_df, skipped_columns, filled_counts = fill_missing_values(
        df,
        strategy="median"
    )

    assert "Age" in skipped_columns
    assert cleaned_df["Age"].isnull().sum() == 3
    assert cleaned_df["Salary"].isnull().sum() == 0


# 8. Test categorical missing value imputation
def test_fill_missing_categorical():
    df = pd.DataFrame({
        "City": ["Delhi", "Mumbai", None, "Delhi"]
    })

    cleaned_df, skipped_columns, filled_counts = fill_missing_categorical(df)

    assert cleaned_df["City"].isnull().sum() == 0
    assert cleaned_df["City"].iloc[2] == "Delhi"
    assert filled_counts["City"] == 1
    assert skipped_columns == []
    assert pd.isnull(df["City"].iloc[2])


# 9. Test duplicate removal
def test_remove_duplicates():
    df = pd.DataFrame({
        "Name": ["A", "B", "A"],
        "Age": [20, 30, 20]
    })

    cleaned_df, removed_count = remove_duplicates(df)

    assert removed_count == 1
    assert len(cleaned_df) == 2
    assert len(df) == 3


# 10. Test complete cleaning workflow
def test_clean_dataset():
    df = pd.DataFrame({
        "Date": ["2024-01-01", "2024-01-02", "2024-01-02"],
        "Age": [20, None, None],
        "City": ["Delhi", None, None]
    })

    original_df = df.copy(deep=True)

    cleaned_df, report = clean_dataset(df)

    # Missing values should be handled
    assert cleaned_df.isnull().sum().sum() == 0

    # Duplicate rows should be removed
    assert len(cleaned_df) == 2

    # Date column should be converted
    assert pd.api.types.is_datetime64_any_dtype(cleaned_df["Date"])

    # Original DataFrame should remain unchanged
    pd.testing.assert_frame_equal(df, original_df)

    # Cleaning report should be returned
    assert isinstance(report, dict)


# 11. Test that outlier detection does not modify original data
def test_detect_outliers_does_not_modify_original():
    df = pd.DataFrame({
        "Salary": [10, 12, 11, 13, 12, 100]
    })

    original_df = df.copy(deep=True)

    detect_outliers(df)

    pd.testing.assert_frame_equal(df, original_df)
