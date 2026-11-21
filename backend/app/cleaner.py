
import re
import json
import math
from typing import Any
import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# Regex Patterns for Identifier Detection
# --------------------------------------------------------------------------

IDENTIFIER_NAME_PATTERN = re.compile(
    r"(^|[\s_\-])(id|identifier|key|uuid|guid|code|pk|fk|ssn|ein|tin)([\s_\-]|$)",
    re.IGNORECASE
)
CAMEL_ID_PATTERN = re.compile(r"[a-z0-9]id$", re.IGNORECASE)
POSTAL_OR_ZIP_PATTERN = re.compile(r"(^|[\s_\-])(zip|postal|phone|fax)([\s_\-]|$)", re.IGNORECASE)


# Sentinel string values representing missing data across diverse CSV formats
SENTINEL_MISSING_STRINGS = {
    "na", "n/a", "null", "none", "nan", "", " ", "?", "-", "--",
    "nil", "n.a.", "n/d", "#n/a", "unknown", "n/k"
}


def is_identifier_column(column_name: str, df: pd.DataFrame | None = None) -> bool:
    """
    Determine whether a column name represents an identifier, key, or code.
    Identifiers should not be converted into continuous numerical measurements
    or subjected to outlier winsorization.
    """
    col_str = str(column_name).strip()
    if (
        IDENTIFIER_NAME_PATTERN.search(col_str)
        or CAMEL_ID_PATTERN.search(col_str)
        or POSTAL_OR_ZIP_PATTERN.search(col_str)
    ):
        return True
    return False


# --------------------------------------------------------------------------
# Stage 2: Column Name Normalization & Safe Deduplication
# --------------------------------------------------------------------------

def normalize_column_names(columns: list) -> tuple[list[str], dict[str, str]]:
    """
    Strip leading/trailing whitespace and safely rename duplicate column names
    to prevent column collision (e.g. ['A', 'B', 'A'] -> ['A', 'B', 'A_1']).

    Returns:
        (clean_columns, renames_dict)
    """
    counts = {}
    clean_cols = []
    renames = {}

    for orig_col in columns:
        stripped = str(orig_col).strip()
        if stripped not in counts:
            counts[stripped] = 1
            clean_cols.append(stripped)
            if str(orig_col) != stripped:
                renames[str(orig_col)] = stripped
        else:
            new_name = f"{stripped}_{counts[stripped]}"
            counts[stripped] += 1
            clean_cols.append(new_name)
            renames[str(orig_col)] = new_name

    return clean_cols, renames


# --------------------------------------------------------------------------
# Stage 3: Sentinel Missing Values & Infinite Values Handling
# --------------------------------------------------------------------------

def replace_sentinel_missing_values(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Replace common string missing-value representations ('NA', 'null', 'None', '', '?', etc.)
    and infinite values (np.inf, -np.inf) with np.nan.

    Returns:
        (cleaned_df, total_sentinels_replaced)
    """
    cleaned_df = df.copy()
    replacements_count = 0

    # 1. Object and string columns: check for string sentinels
    for col in cleaned_df.select_dtypes(include=["object", "string"]).columns:
        series = cleaned_df[col]
        # Identify non-null strings that match sentinel values (case-insensitive after strip)
        is_str = series.apply(lambda x: isinstance(x, str))
        matches = series.where(is_str).apply(
            lambda x: str(x).strip().lower() in SENTINEL_MISSING_STRINGS if pd.notna(x) else False
        )
        match_count = int(matches.sum())
        if match_count > 0:
            cleaned_df.loc[matches, col] = np.nan
            replacements_count += match_count

    # 2. Numeric columns: replace inf and -inf with np.nan
    for col in cleaned_df.select_dtypes(include=["number"]).columns:
        inf_mask = np.isinf(cleaned_df[col])
        inf_count = int(inf_mask.sum())
        if inf_count > 0:
            cleaned_df.loc[inf_mask, col] = np.nan
            replacements_count += inf_count

    return cleaned_df, replacements_count


# --------------------------------------------------------------------------
# Stage 4: Safe Type Inspection and Conversion
# --------------------------------------------------------------------------

def detect_and_convert_numeric_strings(
    df: pd.DataFrame,
    threshold: float = 0.90
) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Detect object/string columns that actually contain numerical values
    (e.g. '$1,200.50', '42', '3.14') and safely convert them to numeric.

    Strictly skips columns identified as identifiers (IDs, codes, ZIP codes)
    to prevent corrupting identifier strings into continuous numbers.

    Returns:
        (cleaned_df, conversions_dict)
    """
    cleaned_df = df.copy()
    conversions = {}

    for col in cleaned_df.select_dtypes(include=["object", "string"]).columns:
        if is_identifier_column(col):
            continue

        non_null_series = cleaned_df[col].dropna()
        if len(non_null_series) == 0:
            continue

        # Clean common numeric decorations: currency symbols, commas, percent signs
        cleaned_series = non_null_series.astype(str).str.strip().str.replace(
            r"[\$,%]", "", regex=True
        ).str.replace(r"\s+", "", regex=True)

        converted = pd.to_numeric(cleaned_series, errors="coerce")
        valid_ratio = converted.notna().mean()

        if valid_ratio >= threshold:
            orig_dtype = str(cleaned_df[col].dtype)
            full_cleaned = cleaned_df[col].astype(str).str.strip().str.replace(
                r"[\$,%]", "", regex=True
            ).str.replace(r"\s+", "", regex=True)
            cleaned_df[col] = pd.to_numeric(full_cleaned, errors="coerce")
            new_dtype = str(cleaned_df[col].dtype)
            conversions[col] = f"{orig_dtype} -> {new_dtype}"

    return cleaned_df, conversions


def detect_date_columns(df: pd.DataFrame, threshold: float = 0.8) -> list[str]:
    """
    Detect string columns that contain dates.
    A column is considered a date column when at least `threshold` (default 0.8,
    meaning >= 80%) of its non-null values can be parsed as valid dates and it
    is not purely numeric.
    """
    date_columns = []

    for column in df.select_dtypes(include=["object", "string"]).columns:
        non_null_series = df[column].dropna()
        if len(non_null_series) == 0:
            continue

        # Check if column is purely numeric strings (e.g. "12345") - not a date
        numeric_test = pd.to_numeric(non_null_series, errors="coerce")
        if numeric_test.notna().mean() > 0.95:
            continue

        converted = pd.to_datetime(non_null_series, errors="coerce", format="mixed")
        valid_ratio = converted.notna().mean()

        if valid_ratio >= threshold:
            date_columns.append(column)

    return date_columns


def convert_date_columns(
    df: pd.DataFrame,
    columns: list[str]
) -> tuple[pd.DataFrame, dict[str, int]]:
    """
    Convert selected columns to ISO-standardized datetime format.
    Returns:
        (cleaned_df, invalid_dates_dict)
    """
    cleaned_df = df.copy()
    invalid_dates = {}

    for column in columns:
        if column not in cleaned_df.columns:
            raise ValueError(f"Column not found: {column}")

        original_nulls = int(cleaned_df[column].isnull().sum())
        cleaned_df[column] = pd.to_datetime(
            cleaned_df[column],
            errors="coerce",
            format="mixed"
        )
        new_nulls = int(cleaned_df[column].isnull().sum())
        coerced_invalid = max(0, new_nulls - original_nulls)
        if coerced_invalid > 0:
            invalid_dates[column] = coerced_invalid

    return cleaned_df, invalid_dates


# --------------------------------------------------------------------------
# Stage 5 & 6: Missingness Analysis & Mandatory >= 75% Removal Rule
# --------------------------------------------------------------------------

def detect_missing_values(df: pd.DataFrame) -> dict:
    """
    Detect missing values in each column.

    Returns:
        Dictionary containing missing-value counts and percentages for each column.
    """
    total_len = len(df)
    missing_count = df.isnull().sum()
    result = {}

    for column in df.columns:
        count = int(missing_count[column])
        pct = round((count / total_len) * 100, 2) if total_len > 0 else 0.0
        result[column] = {
            "missing_count": count,
            "missing_percentage": pct
        }

    return result


def validate_missing_threshold(threshold: Any) -> float:
    """
    Validate that missing_threshold is a numeric value between 1 and 100 inclusive.
    Rejects invalid values (0, negative, >100, non-numeric, bool, NaN, inf) with ValueError.
    """
    if isinstance(threshold, bool):
        raise ValueError(f"Invalid missing_threshold: {threshold!r}. Threshold must be a numeric value, not boolean.")
    if not isinstance(threshold, (int, float)):
        raise ValueError(f"Invalid missing_threshold: {threshold!r}. Threshold must be a numeric value.")
    if math.isnan(threshold) or math.isinf(threshold):
        raise ValueError(f"Invalid missing_threshold: {threshold!r}. Threshold must be a finite numeric value.")
    val = float(threshold)
    if val < 1.0 or val > 100.0:
        raise ValueError(f"Invalid missing_threshold: {val}. Threshold must be between 1 and 100, inclusive.")
    return val


def analyze_missing_values(df: pd.DataFrame, threshold: float = 75.0) -> dict:
    """
    Analyze missing values for every column according to the mandatory rules:
      - missing_percentage == 0%: 'none' (No missing values)
      - missing_percentage >= threshold%: 'high' (MANDATORY DROP THE ENTIRE COLUMN)
      - 0% < missing_percentage <= 30%: 'low' (Normal imputation)
      - 30% < missing_percentage < threshold%: 'moderate' (Needs review)

    CRITICAL RULE:
      Missing percentage >= threshold (default 75%) DROPS THE COLUMN.
      No exceptions: identifier columns with >= threshold% missing are also dropped.
      Comparison strictly uses >=.

    Returns:
        dict: Detailed per-column analysis, classification, and summary lists.
    """
    valid_threshold = validate_missing_threshold(threshold)
    total_rows = len(df)
    columns_report = {}
    high_missingness_columns = []
    review_columns = []
    recommended_drop_columns = []
    protected_identifier_columns = []

    for col in df.columns:
        if total_rows == 0:
            missing_count = 0
            missing_percentage = 0.0
        else:
            missing_count = int(df[col].isnull().sum())
            missing_percentage = round((missing_count / total_rows) * 100, 2)

        data_type = str(df[col].dtype)
        is_numeric = bool(pd.api.types.is_numeric_dtype(df[col]))
        is_id = is_identifier_column(col, df)

        if missing_count == 0:
            classification = "none"
            recommended_action = "no_action"
            recommendation_reason = "Column contains 0 missing values. No cleaning action required."
        elif missing_percentage >= valid_threshold:
            # missing_percentage >= valid_threshold (e.g. 75.0%, 75.1%, 90%, 100%)
            # MANDATORY DROP: Even identifier columns are removed!
            classification = "high"
            recommended_action = "drop"
            high_missingness_columns.append(col)
            recommended_drop_columns.append(col)
            id_notice = " (Identifier column - no exemption applies)" if is_id else ""
            recommendation_reason = (
                f"Column has {missing_percentage}% missing values (>= {valid_threshold}% threshold). "
                f"Mandatory rule: drop the entire column{id_notice}."
            )
        elif missing_percentage <= 30.0:
            classification = "low"
            strategy_hint = "median" if is_numeric else "mode"
            recommended_action = "impute"
            recommendation_reason = (
                f"Missingness is low ({missing_percentage}% <= 30%). "
                f"Eligible for automated {strategy_hint} imputation."
            )
        else:
            # 30% < missing_percentage < valid_threshold (e.g. 50%, 74.9%)
            classification = "moderate"
            recommended_action = "review"
            recommendation_reason = (
                f"Missingness is moderate ({missing_percentage}%). "
                f"Exceeds standard 30% limit but below {valid_threshold}% removal threshold. "
                "Retain column and apply explicit imputation strategy."
            )
            review_columns.append(col)

        if is_id and missing_count > 0 and missing_percentage < valid_threshold:
            protected_identifier_columns.append(col)

        columns_report[col] = {
            "column_name": col,
            "data_type": data_type,
            "is_numeric": is_numeric,
            "is_identifier": is_id,
            "missing_count": missing_count,
            "missing_percentage": missing_percentage,
            "classification": classification,
            "recommended_action": recommended_action,
            "recommendation_reason": recommendation_reason,
            "actual_action": None
        }

    summary_dict = {
        "threshold": float(valid_threshold),
        "total_columns": len(df.columns),
        "high_missingness_columns": high_missingness_columns,
        "review_columns": review_columns,
        "recommended_drop_columns": recommended_drop_columns,
        "protected_identifier_columns": protected_identifier_columns,
    }

    return {
        "threshold": float(valid_threshold),
        "total_columns": len(df.columns),
        "columns": columns_report,
        "summary": summary_dict,
        **summary_dict
    }


# --------------------------------------------------------------------------
# Stage 7: Duplicate Row Handling
# --------------------------------------------------------------------------

def detect_duplicates(df: pd.DataFrame) -> dict:
    """
    Detect exact duplicate rows in a DataFrame.

    Returns:
        Dictionary containing duplicate count and percentage.
    """
    total_len = len(df)
    duplicate_count = int(df.duplicated().sum())
    duplicate_percentage = (
        round((duplicate_count / total_len) * 100, 2) if total_len > 0 else 0.0
    )

    return {
        "duplicate_count": duplicate_count,
        "duplicate_percentage": duplicate_percentage
    }


def remove_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Remove duplicate rows deterministically, preserving the first occurrence.

    Returns:
        (cleaned_df, removed_count)
    """
    cleaned_df = df.copy()
    original_count = len(cleaned_df)
    cleaned_df = cleaned_df.drop_duplicates(keep="first").reset_index(drop=True)
    removed_count = original_count - len(cleaned_df)

    return cleaned_df, removed_count


# --------------------------------------------------------------------------
# Stage 8: Missing Value Imputation for Retained Columns (< 75%)
# --------------------------------------------------------------------------

def fill_missing_values(
    df: pd.DataFrame,
    strategy: str = "median",
    columns: list[str] | None = None
) -> tuple[pd.DataFrame, list[str], dict[str, int]]:
    """
    Fill missing numerical values using robust median (default) or mean.

    Safety:
      - Replaces infinite values with NaN before imputation.
      - Never imputes a column that contains no valid numerical values (all-null).
      - Operates on a copy without mutating the input.

    Returns:
        (cleaned_df, skipped_columns, filled_counts)
    """
    if strategy not in ["mean", "median"]:
        raise ValueError(f"Unsupported numerical strategy: {strategy}. Must be 'mean' or 'median'.")

    cleaned_df = df.copy()
    skipped_columns = []
    filled_counts = {}

    if columns is None:
        selected_columns = cleaned_df.select_dtypes(include="number").columns.tolist()
    else:
        selected_columns = columns

    for column in selected_columns:
        if column not in cleaned_df.columns:
            raise ValueError(f"Column not found: {column}")

        if not pd.api.types.is_numeric_dtype(cleaned_df[column]):
            raise ValueError(f"Column must be numerical: {column}")

        # Replace any residual infinite values with NaN
        inf_mask = np.isinf(cleaned_df[column])
        if inf_mask.any():
            cleaned_df.loc[inf_mask, column] = np.nan

        valid_values = cleaned_df[column].dropna()
        if valid_values.empty:
            skipped_columns.append(column)
            continue

        missing_before = int(cleaned_df[column].isnull().sum())
        if missing_before == 0:
            continue

        if strategy == "mean":
            fill_val = float(valid_values.mean())
        else:
            fill_val = float(valid_values.median())

        cleaned_df[column] = cleaned_df[column].fillna(fill_val)
        filled_counts[column] = missing_before

    return cleaned_df, skipped_columns, filled_counts


def fill_missing_categorical(
    df: pd.DataFrame,
    fallback: str = "Unknown",
    columns: list[str] | None = None
) -> tuple[pd.DataFrame, list[str], dict[str, int], dict[str, str]]:
    """
    Fill missing categorical values using mode when available, with a configurable fallback.

    Safety:
      - When a valid mode exists, fills missing values with the mode.
      - When column is entirely missing or has no mode, fills safely with `fallback`.
      - Reports the exact strategy applied per column.

    Returns:
        (cleaned_df, skipped_columns, filled_counts, strategy_used)
    """
    cleaned_df = df.copy()
    skipped_columns = []
    filled_counts = {}
    strategies = {}

    if columns is None:
        selected_columns = cleaned_df.select_dtypes(
            include=["object", "string", "category"]
        ).columns.tolist()
    else:
        selected_columns = columns

    for column in selected_columns:
        if column not in cleaned_df.columns:
            raise ValueError(f"Column not found: {column}")

        missing_before = int(cleaned_df[column].isnull().sum())
        if missing_before == 0:
            continue

        mode_values = cleaned_df[column].dropna().mode()

        if not mode_values.empty:
            chosen_fill = mode_values.iloc[0]
            strategies[column] = "mode"
        else:
            chosen_fill = fallback
            strategies[column] = f"fallback ('{fallback}')"

        cleaned_df[column] = cleaned_df[column].fillna(chosen_fill)
        filled_counts[column] = missing_before

    return cleaned_df, skipped_columns, filled_counts, strategies


# --------------------------------------------------------------------------
# Stage 9: Outlier Detection and Configurable Treatment (IQR)
# --------------------------------------------------------------------------

def detect_outliers(df: pd.DataFrame, columns: list[str] | None = None) -> dict:
    """
    Detect outliers using the IQR (Interquartile Range) method.
    Q1: 25th percentile, Q3: 75th percentile.
    Lower bound = Q1 - 1.5 * IQR, Upper bound = Q3 + 1.5 * IQR.

    Safe handling:
      - Ignores constant columns (IQR == 0).
      - Ignores columns with fewer than 4 non-null observations.
      - Outliers are detected and reported; data is not modified.
    """
    if columns is None:
        numeric_df = df.select_dtypes(include="number")
    else:
        numeric_df = df[columns]
        non_numeric = numeric_df.select_dtypes(exclude="number").columns.tolist()
        if non_numeric:
            raise ValueError(f"Non-numerical columns found: {non_numeric}")

    result = {}

    for column in numeric_df.columns:
        series = numeric_df[column].dropna()
        if len(series) < 4:
            result[column] = {
                "outlier_count": 0,
                "lower_bound": float(series.min()) if not series.empty else 0.0,
                "upper_bound": float(series.max()) if not series.empty else 0.0,
                "q1": float(series.min()) if not series.empty else 0.0,
                "q3": float(series.max()) if not series.empty else 0.0,
                "iqr": 0.0,
                "status": "insufficient_observations"
            }
            continue

        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1

        if iqr == 0.0:
            result[column] = {
                "outlier_count": 0,
                "lower_bound": q1,
                "upper_bound": q3,
                "q1": q1,
                "q3": q3,
                "iqr": 0.0,
                "status": "constant_distribution"
            }
            continue

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outliers = series[(series < lower_bound) | (series > upper_bound)]

        result[column] = {
            "outlier_count": int(len(outliers)),
            "lower_bound": round(lower_bound, 4),
            "upper_bound": round(upper_bound, 4),
            "q1": round(q1, 4),
            "q3": round(q3, 4),
            "iqr": round(iqr, 4),
            "status": "evaluated"
        }

    return result


def handle_outliers(
    df: pd.DataFrame,
    treatment: str = "detect",
    columns: list[str] | None = None
) -> tuple[pd.DataFrame, dict, int]:
    """
    Perform IQR outlier detection and apply configurable treatment:
      - 'detect' (default): report only, no data modification.
      - 'remove': remove rows containing outliers in any evaluated numerical column.
      - 'cap': winsorize/clip values to [lower_bound, upper_bound].

    Returns:
        (cleaned_df, outlier_report, affected_row_or_val_count)
    """
    if treatment not in ["detect", "remove", "cap"]:
        raise ValueError(f"Invalid outlier treatment: {treatment}. Must be 'detect', 'remove', or 'cap'.")

    cleaned_df = df.copy()
    outlier_report = detect_outliers(cleaned_df, columns=columns)

    if treatment == "detect":
        total_outliers = sum(item["outlier_count"] for item in outlier_report.values())
        return cleaned_df, outlier_report, total_outliers

    if treatment == "cap":
        capped_values = 0
        for col, stats in outlier_report.items():
            if stats["outlier_count"] > 0:
                lb = stats["lower_bound"]
                ub = stats["upper_bound"]
                mask = (cleaned_df[col] < lb) | (cleaned_df[col] > ub)
                capped_values += int(mask.sum())
                cleaned_df[col] = cleaned_df[col].clip(lower=lb, upper=ub)
        return cleaned_df, outlier_report, capped_values

    # treatment == "remove"
    outlier_row_indices = set()
    for col, stats in outlier_report.items():
        if stats["outlier_count"] > 0:
            lb = stats["lower_bound"]
            ub = stats["upper_bound"]
            col_outliers = cleaned_df[(cleaned_df[col] < lb) | (cleaned_df[col] > ub)].index
            outlier_row_indices.update(col_outliers)

    removed_rows = len(outlier_row_indices)
    if removed_rows > 0:
        cleaned_df = cleaned_df.drop(index=sorted(outlier_row_indices)).reset_index(drop=True)

    return cleaned_df, outlier_report, removed_rows


# --------------------------------------------------------------------------
# Stage 10: Additional Data Quality Checks
# --------------------------------------------------------------------------

def detect_data_quality_issues(df: pd.DataFrame) -> dict:
    """
    Perform deep quality audit across:
      - Empty rows (all NaN)
      - Empty columns (all NaN)
      - Constant columns (single unique value)
      - Near-constant columns (>95% single value)
      - Duplicate columns (columns with identical values)
      - Infinite values
    """
    total_rows = len(df)
    empty_rows_count = int(df.isnull().all(axis=1).sum()) if total_rows > 0 else 0
    empty_columns = [col for col in df.columns if df[col].isnull().all()]

    constant_columns = []
    near_constant_columns = {}
    duplicate_columns = []

    # Constant and near-constant columns
    for col in df.columns:
        non_null = df[col].dropna()
        if len(non_null) > 0:
            val_counts = non_null.value_counts(normalize=True)
            top_freq = float(val_counts.iloc[0])
            top_val = str(val_counts.index[0])

            if len(val_counts) == 1:
                constant_columns.append(col)
            elif top_freq >= 0.95:
                near_constant_columns[col] = {
                    "dominant_value": top_val,
                    "frequency": round(top_freq * 100, 2)
                }

    # Duplicate columns detection
    cols = df.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            col1 = cols[i]
            col2 = cols[j]
            if df[col1].equals(df[col2]):
                duplicate_columns.append((col1, col2))

    # Infinite values
    infinite_values = {}
    for col in df.select_dtypes(include="number").columns:
        inf_count = int(np.isinf(df[col]).sum())
        if inf_count > 0:
            infinite_values[col] = inf_count

    return {
        "empty_rows_count": empty_rows_count,
        "empty_columns": empty_columns,
        "constant_columns": constant_columns,
        "near_constant_columns": near_constant_columns,
        "duplicate_columns": duplicate_columns,
        "infinite_values": infinite_values
    }


# --------------------------------------------------------------------------
# Stage 11: Master Cleaning Pipeline (clean_dataset)
# --------------------------------------------------------------------------

def clean_dataset(
    df: pd.DataFrame,
    numerical_strategy: str = "median",
    fill_categorical: bool = True,
    categorical_fallback: str = "Unknown",
    remove_duplicate_rows: bool = True,
    convert_dates: bool = True,
    missing_threshold: float = 75.0,
    outlier_treatment: str = "detect",
    drop_empty_rows: bool = True,
    drop_high_missing: bool = True,
    approved_drop_columns: list[str] | str | None = None
) -> tuple[pd.DataFrame, dict]:
    """
    Execute the complete, production-grade 11-stage Rule-Based Data Cleaning Engine:

      Stage 1: Load and validate CSV structure on an immutable copy.
      Stage 2: Normalize column names (strip whitespace, safe deduplication).
      Stage 3: Replace sentinel strings ('NA', 'null', etc.) and infinite values with np.nan.
      Stage 4: Safe type conversions (numeric strings to numbers, excluding identifiers).
      Stage 5: Analyze missingness with exact >= threshold boundary.
      Stage 6: Mandatory column removal (drop columns with missing_percentage >= threshold).
      Stage 7: Detect and optionally remove duplicate rows (preserves first occurrence).
      Stage 8: Handle retained-column missing values (< threshold) using median/mode.
      Stage 9: Detect and optionally handle outliers (detect / remove / cap).
      Stage 10: Convert and standardize detected datetime columns.
      Stage 11: Comprehensive data quality audit and structured reporting.

    Returns:
        (cleaned_df, report)
    """
    # Validate missing_threshold (must be numeric, 1 through 100 inclusive)
    valid_threshold = validate_missing_threshold(missing_threshold)

    # Stage 1: Immutable copy
    cleaned_df = df.copy(deep=True)
    report = {}
    actual_actions = []
    warnings = []
    recommendations = []

    original_rows = len(cleaned_df)
    original_cols_count = len(cleaned_df.columns)

    # Stage 2: Normalize column names
    clean_cols, renamed_cols = normalize_column_names(cleaned_df.columns.tolist())
    cleaned_df.columns = clean_cols
    if renamed_cols:
        actual_actions.append(f"Normalized column names: {renamed_cols}")
    report["column_name_normalizations"] = renamed_cols

    # Stage 3: Replace sentinel strings and infinite values
    cleaned_df, sentinels_replaced = replace_sentinel_missing_values(cleaned_df)
    if sentinels_replaced > 0:
        actual_actions.append(f"Standardized {sentinels_replaced} sentinel/infinite missing values to NaN")

    # Initial Pre-cleaning audits
    report["missing_before"] = detect_missing_values(cleaned_df)
    report["duplicates_before"] = detect_duplicates(cleaned_df)
    initial_quality = detect_data_quality_issues(cleaned_df)
    report["quality_checks_before"] = initial_quality

    # Stage 4: Detect and safely convert numeric strings
    cleaned_df, type_conversions = detect_and_convert_numeric_strings(cleaned_df)
    if type_conversions:
        actual_actions.append(f"Safely converted numeric string columns: {type_conversions}")
    report["type_conversions"] = type_conversions

    # Stage 5: Analyze missingness
    intelligence = analyze_missing_values(cleaned_df, threshold=valid_threshold)

    # Stage 6: Mandatory column removal (drop columns with missing_percentage >= threshold)
    # High-missing column removal is mandatory and cannot be disabled (drop_high_missing is deprecated).
    columns_dropped = []
    for col, info in intelligence["columns"].items():
        if info["missing_percentage"] >= valid_threshold:
            if col in cleaned_df.columns:
                columns_dropped.append(col)

    # Support optional user-approved drop list if supplied (only drops additional columns)
    if approved_drop_columns:
        approved_list = []
        if isinstance(approved_drop_columns, (list, tuple, set)):
            approved_list = [str(c).strip() for c in approved_drop_columns if str(c).strip()]
        elif isinstance(approved_drop_columns, str):
            approved_str = approved_drop_columns.strip()
            if approved_str.startswith("[") and approved_str.endswith("]"):
                try:
                    approved_list = json.loads(approved_str)
                except Exception:
                    approved_list = [c.strip() for c in approved_str[1:-1].split(",") if c.strip()]
            elif approved_str:
                approved_list = [c.strip() for c in approved_str.split(",") if c.strip()]

        invalid_cols = [c for c in approved_list if c not in df.columns and c not in cleaned_df.columns]
        if invalid_cols:
            raise ValueError(f"Invalid column(s) for removal: {invalid_cols}")

        for c in approved_list:
            if c in cleaned_df.columns and c not in columns_dropped:
                columns_dropped.append(c)

    if columns_dropped:
        cleaned_df = cleaned_df.drop(columns=columns_dropped)
        actual_actions.append(f"Dropped {len(columns_dropped)} column(s) exceeding {valid_threshold}% threshold: {columns_dropped}")
        warnings.append(f"Dropped columns with excessive missingness: {columns_dropped}")

    report["columns_dropped"] = columns_dropped

    # Drop entirely empty rows if enabled
    empty_rows_removed = 0
    if drop_empty_rows and len(cleaned_df) > 0:
        empty_rows_mask = cleaned_df.isnull().all(axis=1)
        empty_rows_removed = int(empty_rows_mask.sum())
        if empty_rows_removed > 0:
            cleaned_df = cleaned_df[~empty_rows_mask].reset_index(drop=True)
            actual_actions.append(f"Removed {empty_rows_removed} entirely empty rows")

    report["empty_rows_removed"] = empty_rows_removed

    # Stage 7: Detect and optionally remove duplicate rows
    if remove_duplicate_rows and len(cleaned_df) > 0:
        cleaned_df, duplicates_removed = remove_duplicates(cleaned_df)
        if duplicates_removed > 0:
            actual_actions.append(f"Purged {duplicates_removed} duplicate records (first occurrence preserved)")
        report["duplicates_removed"] = duplicates_removed
    else:
        report["duplicates_removed"] = 0

    # Stage 10: Date Detection and Conversion
    converted_date_columns_list = []
    invalid_dates_count = {}
    if convert_dates and len(cleaned_df.columns) > 0:
        date_candidates = detect_date_columns(cleaned_df)
        if date_candidates:
            cleaned_df, invalid_dates_count = convert_date_columns(cleaned_df, date_candidates)
            converted_date_columns_list = date_candidates
            actual_actions.append(f"Standardized {len(date_candidates)} date columns to ISO datetime: {date_candidates}")
            if invalid_dates_count:
                warnings.append(f"Coerced unparseable dates to NaT in: {invalid_dates_count}")

    report["converted_date_columns"] = converted_date_columns_list
    report["invalid_dates"] = invalid_dates_count

    # Stage 8: Handle retained-column missing values (< threshold)
    # Exclude datetime columns from numerical/categorical imputation
    non_date_cols = [
        c for c in cleaned_df.columns
        if c not in converted_date_columns_list and not pd.api.types.is_datetime64_any_dtype(cleaned_df[c])
    ]
    numeric_candidates = cleaned_df[non_date_cols].select_dtypes(include="number").columns.tolist()

    cleaned_df, skipped_numerical, numerical_filled = fill_missing_values(
        cleaned_df,
        strategy=numerical_strategy,
        columns=numeric_candidates
    )
    report["skipped_numerical_columns"] = skipped_numerical
    report["numerical_values_filled"] = numerical_filled
    if numerical_filled:
        actual_actions.append(
            f"Imputed numerical missing values in {len(numerical_filled)} columns using {numerical_strategy}: {numerical_filled}"
        )

    imputation_strategies = {c: numerical_strategy for c in numerical_filled.keys()}

    if fill_categorical and len(cleaned_df.columns) > 0:
        cat_candidates = cleaned_df[non_date_cols].select_dtypes(
            include=["object", "string", "category"]
        ).columns.tolist()
        cleaned_df, skipped_categorical, categorical_filled, cat_strategies = fill_missing_categorical(
            cleaned_df,
            fallback=categorical_fallback,
            columns=cat_candidates
        )
        report["skipped_categorical_columns"] = skipped_categorical
        report["categorical_values_filled"] = categorical_filled
        imputation_strategies.update(cat_strategies)
        if categorical_filled:
            actual_actions.append(
                f"Imputed categorical missing values in {len(categorical_filled)} columns: {categorical_filled}"
            )
    else:
        report["skipped_categorical_columns"] = []
        report["categorical_values_filled"] = {}

    report["imputation_strategies"] = imputation_strategies

    # Stage 9: Detect and optionally handle outliers
    numeric_for_outliers = cleaned_df.select_dtypes(include="number").columns.tolist()
    cleaned_df, outlier_report, outliers_affected = handle_outliers(
        cleaned_df,
        treatment=outlier_treatment,
        columns=numeric_for_outliers
    )
    report["outliers"] = outlier_report
    report["outlier_treatment"] = outlier_treatment
    report["outliers_affected"] = outliers_affected

    if outlier_treatment == "remove" and outliers_affected > 0:
        actual_actions.append(f"Removed {outliers_affected} rows containing IQR outliers")
    elif outlier_treatment == "cap" and outliers_affected > 0:
        actual_actions.append(f"Capped (winsorized) {outliers_affected} values to IQR bounds")

    # Post-cleaning audits and quality checks
    report["missing_after"] = detect_missing_values(cleaned_df)
    quality_after = detect_data_quality_issues(cleaned_df)
    report["quality_checks"] = quality_after

    if quality_after["constant_columns"]:
        recommendations.append(
            f"Columns {quality_after['constant_columns']} are constant. Consider removing them if uninformative."
        )
    if quality_after["near_constant_columns"]:
        recommendations.append(
            f"Near-constant columns detected: {list(quality_after['near_constant_columns'].keys())}."
        )
    if quality_after["duplicate_columns"]:
        recommendations.append(
            f"Duplicate columns detected with identical data: {quality_after['duplicate_columns']}."
        )

    # Populate actual_action on the intelligence columns report
    columns_report = intelligence["columns"]
    for col, c_info in columns_report.items():
        if col in columns_dropped:
            c_info["actual_action"] = "dropped"
        elif col in numerical_filled and numerical_filled[col] > 0:
            c_info["actual_action"] = f"imputed_{numerical_strategy}"
        elif col in report.get("categorical_values_filled", {}) and report["categorical_values_filled"][col] > 0:
            c_info["actual_action"] = "imputed_categorical"
        elif c_info["missing_count"] == 0:
            c_info["actual_action"] = "no_action_needed"
        elif col in cleaned_df.columns:
            c_info["actual_action"] = "preserved"

    columns_preserved = [c for c in df.columns if c not in columns_dropped]
    total_imputed = (
        sum(numerical_filled.values()) +
        sum(report.get("categorical_values_filled", {}).values())
    )

    summary_dict = {
        "threshold": float(valid_threshold),
        "total_columns": original_cols_count,
        "high_missingness_columns": intelligence["high_missingness_columns"],
        "review_columns": intelligence["review_columns"],
        "recommended_drop_columns": intelligence["recommended_drop_columns"],
        "protected_identifier_columns": intelligence["protected_identifier_columns"],
        "columns_actually_removed": columns_dropped,
        "columns_preserved": columns_preserved,
        "missing_values_imputed": total_imputed
    }

    report["missing_value_intelligence"] = {
        "threshold": float(valid_threshold),
        "total_columns": original_cols_count,
        "columns": columns_report,
        "summary": summary_dict,
        **summary_dict
    }

    report["original_rows"] = original_rows
    report["cleaned_rows"] = len(cleaned_df)
    report["original_columns"] = original_cols_count
    report["cleaned_columns"] = len(cleaned_df.columns)
    report["warnings"] = warnings
    report["recommendations"] = recommendations
    report["actual_actions"] = actual_actions

    return cleaned_df, report
