
import numpy as np
import pandas as pd
import pytest

from app.cleaner import (
    analyze_missing_values,
    clean_dataset,
    convert_date_columns,
    detect_and_convert_numeric_strings,
    detect_data_quality_issues,
    detect_date_columns,
    detect_duplicates,
    detect_missing_values,
    detect_outliers,
    fill_missing_categorical,
    fill_missing_values,
    handle_outliers,
    is_identifier_column,
    normalize_column_names,
    remove_duplicates,
    replace_sentinel_missing_values,
    validate_missing_threshold,
)


# ==============================================================================
# SECTION A: BASIC HELPER TESTS
# ==============================================================================

def test_detect_missing_values():
    df = pd.DataFrame({
        "Name": ["A", "B", None],
        "Age": [20, None, 30]
    })
    result = detect_missing_values(df)
    assert result["Name"]["missing_count"] == 1
    assert result["Age"]["missing_count"] == 1
    assert result["Name"]["missing_percentage"] == pytest.approx(33.33, abs=0.01)


def test_detect_duplicates():
    df = pd.DataFrame({
        "Name": ["A", "B", "A"],
        "Age": [20, 30, 20]
    })
    result = detect_duplicates(df)
    assert result["duplicate_count"] == 1
    assert result["duplicate_percentage"] == pytest.approx(33.33, abs=0.01)


def test_detect_outliers():
    df = pd.DataFrame({
        "Salary": [10, 12, 11, 13, 12, 100]
    })
    result = detect_outliers(df)
    assert result["Salary"]["outlier_count"] == 1


def test_detect_date_columns():
    df = pd.DataFrame({
        "Date": ["2024-01-01", "2024-02-01", "2024-03-01"],
        "Name": ["A", "B", "C"]
    })
    result = detect_date_columns(df)
    assert "Date" in result
    assert "Name" not in result


# ==============================================================================
# SECTION B: 1-16 MISSING VALUES RULES & IMPUTATION
# ==============================================================================

# 1. 0% missing: retained, no imputation required
def test_01_zero_percent_missing():
    df = pd.DataFrame({
        "row_id": [1, 2, 3, 4],
        "col_clean": [10, 20, 30, 40]
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "col_clean" in cleaned_df.columns
    assert cleaned_df["col_clean"].isnull().sum() == 0
    intel = report["missing_value_intelligence"]["columns"]["col_clean"]
    assert intel["missing_percentage"] == 0.0
    assert intel["classification"] == "none"
    assert intel["recommended_action"] == "no_action"


# 2. 20% missing: retained, classified as low, imputed
def test_02_twenty_percent_missing():
    df = pd.DataFrame({
        "row_id": list(range(10)),
        "col_20": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, None, None]
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "col_20" in cleaned_df.columns
    assert cleaned_df["col_20"].isnull().sum() == 0
    intel = report["missing_value_intelligence"]["columns"]["col_20"]
    assert intel["missing_percentage"] == 20.0
    assert intel["classification"] == "low"
    assert intel["recommended_action"] == "impute"


# 3. 30% missing: boundary <= 30%, classified as low, imputed
def test_03_thirty_percent_missing():
    df = pd.DataFrame({
        "row_id": list(range(10)),
        "col_30": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, None, None, None]
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "col_30" in cleaned_df.columns
    assert cleaned_df["col_30"].isnull().sum() == 0
    intel = report["missing_value_intelligence"]["columns"]["col_30"]
    assert intel["missing_percentage"] == 30.0
    assert intel["classification"] == "low"
    assert intel["recommended_action"] == "impute"


# 4. 50% missing: retained, classified as moderate (review), imputed
def test_04_fifty_percent_missing():
    df = pd.DataFrame({
        "row_id": list(range(10)),
        "col_50": [10.0, 20.0, 30.0, 40.0, 50.0, None, None, None, None, None]
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "col_50" in cleaned_df.columns
    assert cleaned_df["col_50"].isnull().sum() == 0
    intel = report["missing_value_intelligence"]["columns"]["col_50"]
    assert intel["missing_percentage"] == 50.0
    assert intel["classification"] == "moderate"
    assert intel["recommended_action"] == "review"
    assert "col_50" in report["missing_value_intelligence"]["review_columns"]


# 5. 74.9% missing: strictly < 75%, retained, classified as moderate (review)
def test_05_seventy_four_point_nine_percent_missing():
    # 1000 rows, 749 missing (74.9%)
    vals = [100.0] * 251 + [None] * 749
    df = pd.DataFrame({
        "row_id": list(range(1000)),
        "col_74_9": vals
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "col_74_9" in cleaned_df.columns, "Column with 74.9% missing must be RETAINED (< 75%)"
    intel = report["missing_value_intelligence"]["columns"]["col_74_9"]
    assert intel["missing_percentage"] == 74.9
    assert intel["classification"] == "moderate"
    assert intel["recommended_action"] == "review"
    assert "col_74_9" not in report["columns_dropped"]


# 6. Exactly 75% missing: MANDATORY DROP THE ENTIRE COLUMN (>= 75%)
def test_06_exactly_seventy_five_percent_missing_dropped():
    # 4 rows: 1 value, 3 nulls = 75.0%
    df = pd.DataFrame({
        "row_id": [1, 2, 3, 4],
        "col_75": [10.0, None, None, None]
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "col_75" not in cleaned_df.columns, "Column with exactly 75.0% missing must be DROPPED (>= 75%)"
    assert "col_75" in report["columns_dropped"]
    intel = report["missing_value_intelligence"]["columns"]["col_75"]
    assert intel["missing_percentage"] == 75.0
    assert intel["classification"] == "high"
    assert intel["recommended_action"] == "drop"


# 7. 75.1% missing: MANDATORY DROP THE ENTIRE COLUMN (>= 75%)
def test_07_seventy_five_point_one_percent_missing_dropped():
    # 1000 rows: 249 values, 751 nulls = 75.1%
    vals = [10.0] * 249 + [None] * 751
    df = pd.DataFrame({
        "row_id": list(range(1000)),
        "col_75_1": vals
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "col_75_1" not in cleaned_df.columns, "Column with 75.1% missing must be DROPPED (>= 75%)"
    assert "col_75_1" in report["columns_dropped"]
    intel = report["missing_value_intelligence"]["columns"]["col_75_1"]
    assert intel["missing_percentage"] == 75.1
    assert intel["classification"] == "high"


# 8. 90% missing: MANDATORY DROP THE ENTIRE COLUMN
def test_08_ninety_percent_missing_dropped():
    df = pd.DataFrame({
        "row_id": list(range(10)),
        "col_90": [10.0] + [None] * 9
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "col_90" not in cleaned_df.columns, "Column with 90% missing must be DROPPED"
    assert "col_90" in report["columns_dropped"]


# 9. 100% missing: MANDATORY DROP THE ENTIRE COLUMN
def test_09_one_hundred_percent_missing_dropped():
    df = pd.DataFrame({
        "row_id": [1, 2, 3],
        "col_100": [None, None, None]
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "col_100" not in cleaned_df.columns, "Column with 100% missing must be DROPPED"
    assert "col_100" in report["columns_dropped"]


# 10. Numeric median imputation
def test_10_numeric_median_imputation():
    # Values: 10, 20, 100 (median = 20)
    df = pd.DataFrame({
        "row_id": [1, 2, 3, 4],
        "col_num": [10.0, 20.0, 100.0, None]
    })
    cleaned_df, report = clean_dataset(df, numerical_strategy="median")
    assert cleaned_df["col_num"].isnull().sum() == 0
    assert cleaned_df["col_num"].iloc[3] == 20.0
    assert report["imputation_strategies"]["col_num"] == "median"


# 11. Numeric mean imputation
def test_11_numeric_mean_imputation():
    # Values: 10, 20, 30 (mean = 20)
    df = pd.DataFrame({
        "row_id": [1, 2, 3, 4],
        "col_num": [10.0, 20.0, 30.0, None]
    })
    cleaned_df, report = clean_dataset(df, numerical_strategy="mean")
    assert cleaned_df["col_num"].isnull().sum() == 0
    assert cleaned_df["col_num"].iloc[3] == 20.0
    assert report["imputation_strategies"]["col_num"] == "mean"


# 12. Categorical mode imputation
def test_12_categorical_mode_imputation():
    df = pd.DataFrame({
        "row_id": [1, 2, 3, 4],
        "Category": ["Electronics", "Furniture", "Electronics", None]
    })
    cleaned_df, report = clean_dataset(df)
    assert cleaned_df["Category"].isnull().sum() == 0
    assert cleaned_df["Category"].iloc[3] == "Electronics"
    assert report["categorical_values_filled"]["Category"] == 1


# 13. Empty categorical columns: safely handled with fallback
def test_13_empty_categorical_columns():
    df = pd.DataFrame({
        "row_id": [1, 2, 3],
        "empty_cat": pd.Series([None, None, None], dtype="object")
    })
    cleaned_df, skipped, filled, strategies = fill_missing_categorical(
        df,
        fallback="Unknown",
        columns=["empty_cat"]
    )
    assert cleaned_df["empty_cat"].isnull().sum() == 0
    assert (cleaned_df["empty_cat"] == "Unknown").all()
    assert "fallback" in strategies["empty_cat"]


# 14. Empty numerical columns: safely handled without crashing
def test_14_empty_numerical_columns():
    df = pd.DataFrame({
        "row_id": [1, 2, 3],
        "empty_num": pd.Series([None, None, None], dtype="float64")
    })
    cleaned_df, skipped, filled = fill_missing_values(df, strategy="median", columns=["empty_num"])
    assert "empty_num" in skipped
    assert cleaned_df["empty_num"].isnull().sum() == 3


# 15. Missing values represented as strings ("NA", "null", "None", "")
def test_15_missing_values_represented_as_strings():
    df = pd.DataFrame({
        "row_id": [1, 2, 3, 4, 5],
        "col_str": ["Valid", "NA", "null", "None", ""]
    })
    cleaned_df, replaced_count = replace_sentinel_missing_values(df)
    assert replaced_count == 4
    assert cleaned_df["col_str"].isnull().sum() == 4
    assert cleaned_df["col_str"].iloc[0] == "Valid"


# 16. Identifier columns with >= 75% missing MUST also be dropped
def test_16_identifier_columns_ge_75_percent_missing_dropped():
    # Customer_ID has 90% missing (9 nulls out of 10)
    df = pd.DataFrame({
        "row_id": list(range(10)),
        "Customer_ID": ["CUST-001"] + [None] * 9,
        "Order_Key": ["ORD-1"] + [None] * 9,
        "Sales": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "Customer_ID" not in cleaned_df.columns, "Identifier with >=75% missing must be DROPPED"
    assert "Order_Key" not in cleaned_df.columns, "Identifier with >=75% missing must be DROPPED"
    assert "Customer_ID" in report["columns_dropped"]
    assert "Order_Key" in report["columns_dropped"]
    assert "Sales" in cleaned_df.columns


# ==============================================================================
# SECTION C: 17-20 DUPLICATE HANDLING
# ==============================================================================

# 17. Exact duplicate rows detected
def test_17_exact_duplicate_rows():
    df = pd.DataFrame({
        "Name": ["A", "B", "A"],
        "Age": [20, 30, 20]
    })
    res = detect_duplicates(df)
    assert res["duplicate_count"] == 1
    assert res["duplicate_percentage"] == pytest.approx(33.33, abs=0.01)


# 18. Duplicate removal disabled
def test_18_duplicate_removal_disabled():
    df = pd.DataFrame({
        "Name": ["A", "B", "A"],
        "Age": [20, 30, 20]
    })
    cleaned_df, report = clean_dataset(df, remove_duplicate_rows=False)
    assert len(cleaned_df) == 3
    assert report["duplicates_removed"] == 0


# 19. Duplicate removal enabled
def test_19_duplicate_removal_enabled():
    df = pd.DataFrame({
        "Name": ["A", "B", "A"],
        "Age": [20, 30, 20]
    })
    cleaned_df, report = clean_dataset(df, remove_duplicate_rows=True)
    assert len(cleaned_df) == 2
    assert report["duplicates_removed"] == 1


# 20. Deterministic preservation of first occurrence
def test_20_deterministic_preservation_of_first_occurrence():
    df = pd.DataFrame({
        "ID": [1, 2, 1],
        "Label": ["first", "other", "second"]
    })
    # Duplicate rows on subset ID
    cleaned_df, removed = remove_duplicates(df)
    assert len(cleaned_df) == 3  # IDs differ in Label, so not exact duplicate

    # Exact duplicate test:
    df_exact = pd.DataFrame({
        "ID": [1, 2, 1],
        "Label": ["first", "other", "first"],
        "Order": [10, 20, 30]
    })
    # If duplicate on ID and Label:
    df_dup = pd.DataFrame({
        "ID": ["A", "B", "A"],
        "Val": [100, 200, 100]
    })
    cleaned_dup, count = remove_duplicates(df_dup)
    assert count == 1
    assert cleaned_dup.iloc[0]["ID"] == "A"
    assert cleaned_dup.iloc[1]["ID"] == "B"


# ==============================================================================
# SECTION D: 21-26 OUTLIER HANDLING (IQR METHOD)
# ==============================================================================

# 21. IQR outlier detection
def test_21_iqr_outlier_detection():
    df = pd.DataFrame({
        "Score": [10, 12, 11, 13, 12, 11, 14, 12, 100]
    })
    report = detect_outliers(df)
    assert report["Score"]["outlier_count"] == 1
    assert report["Score"]["upper_bound"] < 100


# 22. Outlier detection without removal (default)
def test_22_outlier_detection_without_removal():
    df = pd.DataFrame({
        "row_id": list(range(9)),
        "Score": [10, 12, 11, 13, 12, 11, 14, 12, 100]
    })
    cleaned_df, report = clean_dataset(df, outlier_treatment="detect")
    assert len(cleaned_df) == 9, "Default 'detect' must NOT remove rows"
    assert 100 in cleaned_df["Score"].values, "Default 'detect' must NOT modify values"
    assert report["outliers"]["Score"]["outlier_count"] == 1


# 23. IQR capping (winsorization)
def test_23_iqr_capping():
    df = pd.DataFrame({
        "Score": [10.0, 12.0, 11.0, 13.0, 12.0, 11.0, 14.0, 12.0, 100.0]
    })
    cleaned_df, report, affected = handle_outliers(df, treatment="cap")
    upper_bound = report["Score"]["upper_bound"]
    assert cleaned_df["Score"].max() == upper_bound
    assert 100.0 not in cleaned_df["Score"].values
    assert affected == 1


# 24. Outlier row removal
def test_24_outlier_row_removal():
    df = pd.DataFrame({
        "Score": [10.0, 12.0, 11.0, 13.0, 12.0, 11.0, 14.0, 12.0, 100.0]
    })
    cleaned_df, report, removed = handle_outliers(df, treatment="remove")
    assert len(cleaned_df) == 8
    assert 100.0 not in cleaned_df["Score"].values
    assert removed == 1


# 25. Constant numerical columns: IQR == 0 handled safely
def test_25_constant_numerical_columns():
    df = pd.DataFrame({
        "Constant": [5.0, 5.0, 5.0, 5.0, 5.0]
    })
    report = detect_outliers(df)
    assert report["Constant"]["outlier_count"] == 0
    assert report["Constant"]["iqr"] == 0.0
    assert report["Constant"]["status"] == "constant_distribution"


# 26. Insufficient numerical observations (< 4 observations)
def test_26_insufficient_numerical_observations():
    df = pd.DataFrame({
        "Few": [10.0, 20.0, 30.0]
    })
    report = detect_outliers(df)
    assert report["Few"]["outlier_count"] == 0
    assert report["Few"]["status"] == "insufficient_observations"


# ==============================================================================
# SECTION E: 27-33 DATA TYPES AND FORMAT HANDLING
# ==============================================================================

# 27. Numeric values stored as strings
def test_27_numeric_values_stored_as_strings():
    df = pd.DataFrame({
        "Price": ["$10.50", "$20.00", "$30.25", "$40.00"],
        "Quantity": ["1,000", "2,500", "3,000", "4,200"]
    })
    cleaned_df, conversions = detect_and_convert_numeric_strings(df)
    assert pd.api.types.is_numeric_dtype(cleaned_df["Price"])
    assert pd.api.types.is_numeric_dtype(cleaned_df["Quantity"])
    assert cleaned_df["Price"].iloc[0] == 10.50
    assert cleaned_df["Quantity"].iloc[0] == 1000


# 28. Valid datetime columns
def test_28_valid_datetime_columns():
    df = pd.DataFrame({
        "Date": ["2024-01-01", "2024-01-02", "2024-01-03"]
    })
    cleaned_df, invalid_dates = convert_date_columns(df, ["Date"])
    assert pd.api.types.is_datetime64_any_dtype(cleaned_df["Date"])
    assert invalid_dates == {}


# 29. Invalid datetime values safely coerced
def test_29_invalid_datetime_values():
    df = pd.DataFrame({
        "Date": ["2024-01-01", "not_a_date", "2024-01-03"]
    })
    cleaned_df, invalid_dates = convert_date_columns(df, ["Date"])
    assert pd.api.types.is_datetime64_any_dtype(cleaned_df["Date"])
    assert pd.isna(cleaned_df["Date"].iloc[1])
    assert invalid_dates.get("Date") == 1


# 30. Identifier columns containing digits must NOT be converted to numeric
def test_30_identifier_columns_containing_digits():
    df = pd.DataFrame({
        "order_id": ["00123", "00456", "00789"],
        "zip_code": ["02138", "02139", "10001"],
        "Price": ["10.5", "20.5", "30.5"]
    })
    cleaned_df, conversions = detect_and_convert_numeric_strings(df)
    assert not pd.api.types.is_numeric_dtype(cleaned_df["order_id"]), "order_id must remain string/object"
    assert not pd.api.types.is_numeric_dtype(cleaned_df["zip_code"]), "zip_code must remain string/object"
    assert cleaned_df["order_id"].iloc[0] == "00123"  # Leading zeroes preserved!
    assert pd.api.types.is_numeric_dtype(cleaned_df["Price"])


# 31. Mixed data types handled safely
def test_31_mixed_data_types():
    df = pd.DataFrame({
        "ID": [1, 2, 3, 4],
        "Mixed": [1, "two", 3.0, None]
    })
    cleaned_df, report = clean_dataset(df)
    assert len(cleaned_df) == 4
    assert cleaned_df["Mixed"].isnull().sum() == 0


# 32. Whitespace in column names
def test_32_whitespace_in_column_names():
    cols = ["  Customer Name  ", "\tSales\n", "Profit "]
    clean_cols, renames = normalize_column_names(cols)
    assert clean_cols == ["Customer Name", "Sales", "Profit"]
    assert "  Customer Name  " in renames


# 33. Duplicate column names handled safely
def test_33_duplicate_column_names():
    cols = ["Score", "Score", "Score"]
    clean_cols, renames = normalize_column_names(cols)
    assert clean_cols == ["Score", "Score_1", "Score_2"]


# ==============================================================================
# SECTION F: 34-38 ADDITIONAL DATA QUALITY CHECKS
# ==============================================================================

# 34. Entirely empty rows
def test_34_entirely_empty_rows():
    df = pd.DataFrame({
        "A": [1.0, None, 3.0],
        "B": ["x", None, "z"]
    })
    cleaned_df, report = clean_dataset(df, drop_empty_rows=True)
    assert len(cleaned_df) == 2, "Empty row must be dropped"
    assert report["empty_rows_removed"] == 1


# 35. Entirely empty columns
def test_35_entirely_empty_columns():
    df = pd.DataFrame({
        "Valid": [1, 2, 3],
        "All_Empty": [None, None, None]
    })
    cleaned_df, report = clean_dataset(df)
    assert "All_Empty" not in cleaned_df.columns
    assert "All_Empty" in report["columns_dropped"]


# 36. Constant columns
def test_36_constant_columns():
    df = pd.DataFrame({
        "A": [1, 2, 3],
        "Constant": ["FIXED", "FIXED", "FIXED"]
    })
    quality = detect_data_quality_issues(df)
    assert "Constant" in quality["constant_columns"]
    assert "A" not in quality["constant_columns"]


# 37. Infinite values
def test_37_infinite_values():
    df = pd.DataFrame({
        "Num": [1.0, np.inf, 3.0, -np.inf, 5.0]
    })
    quality = detect_data_quality_issues(df)
    assert quality["infinite_values"]["Num"] == 2

    cleaned_df, replaced = replace_sentinel_missing_values(df)
    assert cleaned_df["Num"].isnull().sum() == 2
    assert not np.isinf(cleaned_df["Num"]).any()


# 38. Duplicate columns detection
def test_38_duplicate_columns():
    df = pd.DataFrame({
        "A": [1, 2, 3],
        "B": ["x", "y", "z"],
        "A_copy": [1, 2, 3]
    })
    quality = detect_data_quality_issues(df)
    assert ("A", "A_copy") in quality["duplicate_columns"] or ("A_copy", "A") in quality["duplicate_columns"]


# ==============================================================================
# SECTION G: 39-44 SAFETY, INTEGRITY & AUDIT REPORT
# ==============================================================================

# 39. Original input DataFrame remains unchanged
def test_39_original_dataframe_unchanged():
    df = pd.DataFrame({
        "Date": ["2024-01-01", "2024-01-02", "2024-01-02"],
        "Age": [20.0, None, None],
        "City": ["Delhi", None, None],
        "Sparse": [10.0, None, None]  # 66.7% missing
    })
    original_copy = df.copy(deep=True)
    cleaned_df, report = clean_dataset(df)

    # df must be completely unchanged
    pd.testing.assert_frame_equal(df, original_copy)
    assert cleaned_df is not df


# 40. Cleaning an already-clean dataset is safe
def test_40_cleaning_already_clean_dataset_is_safe():
    df = pd.DataFrame({
        "ID": [1, 2, 3, 4],
        "Name": ["Alpha", "Beta", "Gamma", "Delta"],
        "Score": [85.0, 90.0, 78.0, 92.0]
    })
    cleaned_df, report = clean_dataset(df)
    assert len(cleaned_df) == 4
    assert len(cleaned_df.columns) == 3
    assert report["duplicates_removed"] == 0
    assert len(report["columns_dropped"]) == 0


# 41. Idempotency: Running cleaning twice introduces no new unintended changes
def test_41_idempotency_running_cleaning_twice():
    df = pd.DataFrame({
        "Date": ["2024-01-01", "2024-01-02", "2024-01-02"],
        "Age": [20.0, 30.0, None],
        "Category": ["A", "B", None],
        "Sparse_Drop": [10.0, None, None]  # 66.7% - let's set threshold=60 to drop
    })
    cleaned_1, report_1 = clean_dataset(df, missing_threshold=60.0)
    cleaned_2, report_2 = clean_dataset(cleaned_1, missing_threshold=60.0)

    # Shapes and values must be identical
    assert len(cleaned_1) == len(cleaned_2)
    assert list(cleaned_1.columns) == list(cleaned_2.columns)
    pd.testing.assert_frame_equal(cleaned_1, cleaned_2)


# 42. Invalid configuration is rejected
def test_42_invalid_configuration_rejected():
    df = pd.DataFrame({"A": [1, 2, 3]})
    with pytest.raises(ValueError, match="Unsupported numerical strategy"):
        clean_dataset(df, numerical_strategy="invalid_strat")

    with pytest.raises(ValueError, match="Invalid outlier treatment"):
        clean_dataset(df, outlier_treatment="invalid_treatment")

    with pytest.raises(ValueError, match="Invalid column"):
        clean_dataset(df, approved_drop_columns=["NonExistentColumn"])


# 43. Audit report accurately records actual actions
def test_44_audit_report_accurately_records_actions():
    df = pd.DataFrame({
        "row_id": [1, 2, 3, 4],
        "Sparse_Col": [10.0, None, None, None],  # 75% -> dropped
        "Num_Col": [10.0, 20.0, None, 40.0],     # 25% -> imputed median
        "Dup_Col": ["A", "A", "A", "A"]
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)

    assert "Sparse_Col" in report["columns_dropped"]
    assert report["missing_value_intelligence"]["columns"]["Sparse_Col"]["actual_action"] == "dropped"
    assert report["missing_value_intelligence"]["columns"]["Num_Col"]["actual_action"] == "imputed_median"
    assert len(report["actual_actions"]) > 0
    assert isinstance(report["warnings"], list)
    assert isinstance(report["recommendations"], list)


# ==============================================================================
# SECTION H: TARGETED BOUNDARY AND PIPELINE VERIFICATION TESTS
# ==============================================================================

# 45. Date detection boundary: exactly 80% (4 out of 5 valid)
def test_detect_date_columns_boundary_exactly_80_percent():
    # 4 valid dates, 1 invalid string = exactly 80.0%
    df = pd.DataFrame({
        "Date_80": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "not_a_date"]
    })
    result = detect_date_columns(df, threshold=0.8)
    assert "Date_80" in result, "Columns with exactly 80% valid dates must be detected (>= 80%)"


# 46. Date detection boundary: above 80% (9 out of 10 valid = 90%)
def test_detect_date_columns_boundary_above_80_percent():
    df = pd.DataFrame({
        "Date_90": [
            "2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05",
            "2023-01-06", "2023-01-07", "2023-01-08", "2023-01-09", "corrupt_text"
        ]
    })
    result = detect_date_columns(df, threshold=0.8)
    assert "Date_90" in result, "Columns with > 80% valid dates must be detected"


# 47. Date detection boundary: below 80% (3 out of 5 = 60%, 79 out of 100 = 79%)
def test_detect_date_columns_boundary_below_80_percent():
    # 3 out of 5 = 60.0%
    df_60 = pd.DataFrame({
        "Date_60": ["2023-01-01", "2023-01-02", "2023-01-03", "bad_text_1", "bad_text_2"]
    })
    assert "Date_60" not in detect_date_columns(df_60, threshold=0.8), "Columns with 60% valid dates must NOT be detected"

    # 79 out of 100 = 79.0% (strictly < 80%)
    df_79 = pd.DataFrame({
        "Date_79": ["2023-05-01"] * 79 + ["regular_text"] * 21
    })
    assert "Date_79" not in detect_date_columns(df_79, threshold=0.8), "Columns with 79% valid dates must NOT be detected"


# 48. Datetime columns must never receive numerical or categorical imputation
def test_datetime_columns_never_receive_numerical_or_categorical_imputation():
    df = pd.DataFrame({
        "row_id": [1, 2, 3, 4, 5],
        "Order_Date": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", None],
        "Category": ["A", "B", "A", "B", None],
        "Amount": [10.0, 20.0, 30.0, 40.0, None]
    })
    cleaned_df, report = clean_dataset(df, convert_dates=True, fill_categorical=True)

    # Order_Date must be datetime
    assert pd.api.types.is_datetime64_any_dtype(cleaned_df["Order_Date"])
    # The null date must remain NaT, never imputed with mode or median
    assert pd.isna(cleaned_df["Order_Date"].iloc[4])
    assert "Order_Date" not in report.get("numerical_values_filled", {})
    assert "Order_Date" not in report.get("categorical_values_filled", {})
    assert "Order_Date" in report["converted_date_columns"]

    # Category and Amount are imputed
    assert cleaned_df["Category"].isnull().sum() == 0
    assert cleaned_df["Amount"].isnull().sum() == 0


# 49. Sentinels and infinity normalized before missingness percentages calculated
def test_sentinels_and_infinity_normalized_before_missingness_assessment():
    # 4 rows: 1 value, 3 sentinels = 75.0% missing after sentinel normalization
    df = pd.DataFrame({
        "row_id": [1, 2, 3, 4],
        "Col_Sentinels": ["100.0", "NA", "null", "None"]
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)

    # After normalization: 3 out of 4 are NaN (75.0%), so it meets the >= 75% rule and is dropped!
    assert "Col_Sentinels" not in cleaned_df.columns
    assert "Col_Sentinels" in report["columns_dropped"]
    intel = report["missing_value_intelligence"]["columns"]["Col_Sentinels"]
    assert intel["missing_percentage"] == 75.0
    assert intel["classification"] == "high"


# 50. All-null numerical and categorical columns handled safely when retained
def test_all_null_retained_numerical_and_categorical_columns_safe():
    df = pd.DataFrame({
        "row_id": [1, 2, 3],
        "All_Null_Num": pd.Series([None, None, None], dtype="float64"),
        "All_Null_Cat": pd.Series([None, None, None], dtype="object")
    })
    # Safe handling: numeric skipped without error, categorical filled with fallback
    cleaned_num, skipped, num_filled = fill_missing_values(df, strategy="median", columns=["All_Null_Num"])
    assert "All_Null_Num" in skipped
    assert num_filled.get("All_Null_Num", 0) == 0

    cleaned_cat, skipped_cat, cat_filled, strategies = fill_missing_categorical(
        df, fallback="Unknown", columns=["All_Null_Cat"]
    )
    assert (cleaned_cat["All_Null_Cat"] == "Unknown").all()
    assert cat_filled["All_Null_Cat"] == 3
    assert strategies["All_Null_Cat"] == "fallback ('Unknown')"


# 51. Deterministic duplicate removal across repeated executions
def test_deterministic_duplicate_removal_multiple_runs():
    df = pd.DataFrame({
        "A": [1, 2, 1, 3, 2, 4],
        "B": ["x", "y", "x", "z", "y", "w"]
    })
    runs = [clean_dataset(df, remove_duplicate_rows=True)[0] for _ in range(5)]
    for i in range(1, len(runs)):
        pd.testing.assert_frame_equal(runs[0], runs[i])


# 52. Mandatory drop: exactly 75.0% missing must be dropped (>= threshold)
def test_mandatory_drop_boundary_exactly_75_percent():
    # 4 rows: 1 value, 3 nulls = 75.0%
    df = pd.DataFrame({
        "row_id": [1, 2, 3, 4],
        "col_exact_75": [10.0, None, None, None],
        "col_clean": [1, 2, 3, 4]
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "col_exact_75" not in cleaned_df.columns
    assert "col_exact_75" in report["columns_dropped"]
    assert "col_clean" in cleaned_df.columns
    intel = report["missing_value_intelligence"]["columns"]["col_exact_75"]
    assert intel["missing_percentage"] == 75.0
    assert intel["actual_action"] == "dropped"


# 53. Mandatory drop: more than 75.0% missing must be dropped
def test_mandatory_drop_more_than_75_percent():
    # 10 rows: 2 values, 8 nulls = 80.0%
    df = pd.DataFrame({
        "row_id": list(range(10)),
        "col_80": [1.0, 2.0] + [None] * 8,
        "col_clean": list(range(10))
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "col_80" not in cleaned_df.columns
    assert "col_80" in report["columns_dropped"]
    assert "col_clean" in cleaned_df.columns


# 54. Mandatory drop: less than 75.0% missing must be retained
def test_mandatory_drop_less_than_75_percent_retained():
    # 1000 rows: 251 values, 749 nulls = 74.9%
    # 1000 rows: 500 values, 500 nulls = 50.0%
    # 1000 rows: 800 values, 200 nulls = 20.0%
    vals_749 = [1.0] * 251 + [None] * 749
    vals_50 = [1.0] * 500 + [None] * 500
    vals_20 = [1.0] * 800 + [None] * 200
    df = pd.DataFrame({
        "row_id": list(range(1000)),
        "col_74_9": vals_749,
        "col_50": vals_50,
        "col_20": vals_20
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "col_74_9" in cleaned_df.columns
    assert "col_50" in cleaned_df.columns
    assert "col_20" in cleaned_df.columns
    assert "col_74_9" not in report["columns_dropped"]
    assert "col_50" not in report["columns_dropped"]
    assert "col_20" not in report["columns_dropped"]


# 55. Mandatory drop: 100% missing must be dropped
def test_mandatory_drop_100_percent_missing():
    df = pd.DataFrame({
        "row_id": [1, 2, 3, 4],
        "col_all_null": [None, None, None, None],
        "col_clean": ["a", "b", "c", "d"]
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0)
    assert "col_all_null" not in cleaned_df.columns
    assert "col_all_null" in report["columns_dropped"]
    assert "col_clean" in cleaned_df.columns


# 56. drop_high_missing=False cannot bypass mandatory removal
def test_drop_high_missing_false_cannot_bypass_mandatory_removal():
    df = pd.DataFrame({
        "row_id": [1, 2, 3, 4],
        "col_75": [10.0, None, None, None],  # 75% missing
        "col_80": [1.0, None, None, None],  # 75% missing
        "col_100": [None, None, None, None],  # 100% missing
        "col_clean": [1, 2, 3, 4]
    })
    # Attempt to pass drop_high_missing=False: mandatory removal MUST still occur
    cleaned_df, report = clean_dataset(df, missing_threshold=75.0, drop_high_missing=False)
    assert "col_75" not in cleaned_df.columns, "drop_high_missing=False must not bypass mandatory removal"
    assert "col_80" not in cleaned_df.columns, "drop_high_missing=False must not bypass mandatory removal"
    assert "col_100" not in cleaned_df.columns, "drop_high_missing=False must not bypass mandatory removal"
    assert "col_75" in report["columns_dropped"]
    assert "col_80" in report["columns_dropped"]
    assert "col_100" in report["columns_dropped"]
    assert "col_clean" in cleaned_df.columns


# 57. approved_drop_columns cannot preserve mandatory-drop columns
def test_approved_drop_columns_cannot_preserve_mandatory_drop_columns():
    df = pd.DataFrame({
        "row_id": list(range(10)),
        "col_mandatory_80": [1.0, 2.0] + [None] * 8,  # 80% missing -> mandatory drop
        "col_clean_other": list(range(10)),  # 0% missing
        "col_low_missing": [1.0] * 8 + [None] * 2  # 20% missing -> normally kept
    })
    # Case 1: Caller passes approved_drop_columns with only col_low_missing
    cleaned_df, report = clean_dataset(
        df,
        missing_threshold=75.0,
        approved_drop_columns=["col_low_missing"]
    )
    # col_mandatory_80 MUST still be dropped (cannot be preserved by omission from approved list)
    assert "col_mandatory_80" not in cleaned_df.columns
    assert "col_mandatory_80" in report["columns_dropped"]
    # col_low_missing is also dropped because it was explicitly approved
    assert "col_low_missing" not in cleaned_df.columns
    assert "col_low_missing" in report["columns_dropped"]
    assert "col_clean_other" in cleaned_df.columns

    # Case 2: Caller passes approved_drop_columns=[]
    cleaned_df2, report2 = clean_dataset(
        df,
        missing_threshold=75.0,
        approved_drop_columns=[]
    )
    assert "col_mandatory_80" not in cleaned_df2.columns
    assert "col_mandatory_80" in report2["columns_dropped"]
    assert "col_low_missing" in cleaned_df2.columns


# 58. Invalid missing_threshold values rejected with ValueError
def test_invalid_missing_threshold_rejected_with_value_error():
    df = pd.DataFrame({
        "row_id": [1, 2, 3],
        "A": [10, 20, 30]
    })

    invalid_thresholds = [
        0, 0.0, -1, -50.0, -0.01,  # Non-positive / zero
        100.1, 105, 150.0, 200,    # Above 100
        "75", "75.0", "auto",      # Non-numeric string
        None, [75], {"t": 75},     # Non-numeric objects
        True, False,               # Booleans
        float("nan"), float("inf"), float("-inf")  # NaN and Inf
    ]

    for bad_threshold in invalid_thresholds:
        # validate_missing_threshold directly
        with pytest.raises(ValueError):
            validate_missing_threshold(bad_threshold)

        # analyze_missing_values
        with pytest.raises(ValueError):
            analyze_missing_values(df, threshold=bad_threshold)

        # clean_dataset
        with pytest.raises(ValueError):
            clean_dataset(df, missing_threshold=bad_threshold)


# 59. Valid missing_threshold boundaries (1.0 and 100.0) accepted
def test_valid_missing_threshold_boundaries():
    df = pd.DataFrame({
        "row_id": [1, 2, 3, 4],
        "A": [10, None, 30, 40]
    })
    # Boundaries 1.0 and 100.0 must be accepted
    assert validate_missing_threshold(1.0) == 1.0
    assert validate_missing_threshold(1) == 1.0
    assert validate_missing_threshold(100.0) == 100.0
    assert validate_missing_threshold(100) == 100.0
    assert validate_missing_threshold(75.0) == 75.0

    # Test clean_dataset with threshold=1.0 and threshold=100.0
    cleaned_1, rep_1 = clean_dataset(df, missing_threshold=1.0)
    assert rep_1["missing_value_intelligence"]["threshold"] == 1.0

    cleaned_100, rep_100 = clean_dataset(df, missing_threshold=100.0)
    assert rep_100["missing_value_intelligence"]["threshold"] == 100.0


# 60. Threshold 100 still drops completely empty (100% missing) columns
def test_threshold_100_drops_100_percent_missing_retains_99_percent():
    # 100 rows: col_100 has 100 nulls (100%), col_99 has 1 value and 99 nulls (99%)
    df = pd.DataFrame({
        "row_id": list(range(100)),
        "col_100": [None] * 100,
        "col_99": [42.0] + [None] * 99,
        "col_clean": list(range(100))
    })
    cleaned_df, report = clean_dataset(df, missing_threshold=100.0)
    # col_100 has 100.0% missing >= 100.0% -> MUST BE DROPPED
    assert "col_100" not in cleaned_df.columns
    assert "col_100" in report["columns_dropped"]
    # col_99 has 99.0% missing < 100.0% -> MUST BE RETAINED
    assert "col_99" in cleaned_df.columns
    assert "col_99" not in report["columns_dropped"]
    assert "col_clean" in cleaned_df.columns
