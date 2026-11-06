
import pandas as pd


def detect_missing_values(df):
    """
    Detect missing values in each column.

    Returns:
        Dictionary containing missing-value counts
        and percentages for each column.
    """

    missing_count = df.isnull().sum()
    missing_percentage = (missing_count / len(df)) * 100

    result = {}

    for column in df.columns:
        result[column] = {
            "missing_count": int(missing_count[column]),
            "missing_percentage": round(
                missing_percentage[column], 2
            )
        }

    return result


def detect_duplicates(df):
    """
    Detect duplicate rows in a DataFrame.

    Returns:
        Dictionary containing duplicate count and percentage.
    """

    duplicate_count = int(df.duplicated().sum())

    duplicate_percentage = (
        duplicate_count / len(df)
    ) * 100

    return {
        "duplicate_count": duplicate_count,
        "duplicate_percentage": round(
            duplicate_percentage, 2
        )
    }


def detect_outliers(df, columns=None):
    """
    Detect potential outliers using the IQR method.
    Outliers are reported but not removed.
    """

    if columns is None:
        numeric_df = df.select_dtypes(include="number")
    else:
        numeric_df = df[columns]

        non_numeric = numeric_df.select_dtypes(
            exclude="number"
        ).columns.tolist()

        if non_numeric:
            raise ValueError(
                f"Non-numerical columns found: {non_numeric}"
            )

    result = {}

    for column in numeric_df.columns:

        q1 = numeric_df[column].quantile(0.25)
        q3 = numeric_df[column].quantile(0.75)

        iqr = q3 - q1

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outliers = numeric_df[
            (numeric_df[column] < lower_bound) |
            (numeric_df[column] > upper_bound)
        ][column]

        result[column] = {
            "outlier_count": int(len(outliers)),
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound)
        }

    return result


def detect_date_columns(df, threshold=0.8):
    """
    Detect string columns that may contain dates.

    A column is considered a potential date column
    when at least the specified ratio of its values
    can be converted into dates.
    """

    date_columns = []

    for column in df.select_dtypes(
        include=["object", "str"]
    ).columns:

        converted = pd.to_datetime(
            df[column],
            errors="coerce",
            format="mixed"
        )

        valid_ratio = converted.notna().mean()

        if valid_ratio >= threshold:
            date_columns.append(column)

    return date_columns


def convert_date_columns(df, columns):
    """
    Convert selected columns into datetime format.

    Returns:
        A cleaned copy of the DataFrame.
    """

    cleaned_df = df.copy()

    for column in columns:

        if column not in cleaned_df.columns:
            raise ValueError(
                f"Column not found: {column}"
            )

        cleaned_df[column] = pd.to_datetime(
            cleaned_df[column],
            errors="coerce",
            format="mixed"
        )

    return cleaned_df


def fill_missing_values(df, strategy, columns=None):
    """
    Fill missing numerical values using mean or median.

    All-null columns are skipped because no valid
    replacement value can be calculated.

    Returns:
        cleaned_df
        skipped_columns
        filled_counts
    """

    if strategy not in ["mean", "median"]:
        raise ValueError("Unsupported strategy")

    cleaned_df = df.copy()

    skipped_columns = []
    filled_counts = {}

    if columns is None:
        selected_columns = cleaned_df.select_dtypes(
            include="number"
        ).columns.tolist()
    else:
        selected_columns = columns

    for column in selected_columns:

        if column not in cleaned_df.columns:
            raise ValueError(
                f"Column not found: {column}"
            )

        if not pd.api.types.is_numeric_dtype(
            cleaned_df[column]
        ):
            raise ValueError(
                f"Column must be numerical: {column}"
            )

        # Skip columns containing only missing values
        if cleaned_df[column].isnull().all():
            skipped_columns.append(column)
            continue

        if strategy == "mean":
            fill_value = cleaned_df[column].mean()
        else:
            fill_value = cleaned_df[column].median()

        missing_before = cleaned_df[column].isnull().sum()

        cleaned_df[column] = cleaned_df[column].fillna(
            fill_value
        )

        filled_counts[column] = int(missing_before)

    return cleaned_df, skipped_columns, filled_counts


def fill_missing_categorical(df, columns=None):
    """
    Fill missing categorical values using mode.

    Columns without a valid mode are skipped.

    Returns:
        cleaned_df
        skipped_columns
        filled_counts
    """

    cleaned_df = df.copy()

    skipped_columns = []
    filled_counts = {}

    if columns is None:
        selected_columns = cleaned_df.select_dtypes(
            include=["object", "str", "category"]
        ).columns.tolist()
    else:
        selected_columns = columns

    for column in selected_columns:

        if column not in cleaned_df.columns:
            raise ValueError(
                f"Column not found: {column}"
            )

        missing_before = int(
            cleaned_df[column].isnull().sum()
        )

        mode_values = cleaned_df[column].mode()

        if mode_values.empty:
            skipped_columns.append(column)
            continue

        cleaned_df[column] = cleaned_df[column].fillna(
            mode_values.iloc[0]
        )

        filled_counts[column] = missing_before

    return cleaned_df, skipped_columns, filled_counts


def remove_duplicates(df):
    """
    Remove duplicate rows while preserving the original DataFrame.

    Returns:
        cleaned_df
        removed_count
    """

    cleaned_df = df.copy()

    original_count = len(cleaned_df)

    cleaned_df = cleaned_df.drop_duplicates(
        keep="first"
    ).reset_index(drop=True)

    removed_count = original_count - len(cleaned_df)

    return cleaned_df, removed_count


def clean_dataset(
    df,
    numerical_strategy="median",
    fill_categorical=True,
    remove_duplicate_rows=True,
    convert_dates=True
):
    """
    Run a basic cleaning workflow on a copy of the dataset.

    Operations:
        1. Detect missing values
        2. Detect duplicates
        3. Detect outliers
        4. Convert detected date columns
        5. Fill missing numerical values
        6. Fill missing categorical values
        7. Remove duplicate rows
        8. Generate final missing-value report

    Returns:
        cleaned_df
        report
    """

    cleaned_df = df.copy()

    report = {}

    # 1. Detect missing values before cleaning
    report["missing_before"] = detect_missing_values(
        cleaned_df
    )

    # 2. Detect duplicates before cleaning
    report["duplicates_before"] = detect_duplicates(
        cleaned_df
    )

    # 3. Detect outliers (report only)
    report["outliers"] = detect_outliers(
        cleaned_df
    )

    # 4. Convert detected date columns
    if convert_dates:

        date_columns = detect_date_columns(
            cleaned_df
        )

        cleaned_df = convert_date_columns(
            cleaned_df,
            date_columns
        )

        report["converted_date_columns"] = date_columns

    # 5. Fill missing numerical values
    cleaned_df, skipped_columns, filled_counts = (
        fill_missing_values(
            cleaned_df,
            strategy=numerical_strategy
        )
    )

    report["skipped_numerical_columns"] = skipped_columns
    report["numerical_values_filled"] = filled_counts

    # 6. Fill missing categorical values
    if fill_categorical:

        cleaned_df, categorical_skipped, categorical_filled = (
            fill_missing_categorical(cleaned_df)
        )

        report["skipped_categorical_columns"] = (
            categorical_skipped
        )

        report["categorical_values_filled"] = (
            categorical_filled
        )

    # 7. Remove duplicate rows
    if remove_duplicate_rows:

        cleaned_df, removed_count = remove_duplicates(
            cleaned_df
        )

        report["duplicates_removed"] = removed_count

    # 8. Final missing-value report
    report["missing_after"] = detect_missing_values(
        cleaned_df
    )

    return cleaned_df, report
