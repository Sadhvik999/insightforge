
import pandas as pd


# --------------------------------------------------
# TOOL 1: Get information about every column
# --------------------------------------------------

def get_column_info(df):
    """
    Get information about every column in the dataset.
    """

    column_info = {}

    for column in df.columns:
        column_info[column] = {
            "data_type": str(df[column].dtype),
            "missing_values": int(df[column].isnull().sum()),
            "unique_values": int(df[column].nunique()),
            "is_numeric": bool(
                pd.api.types.is_numeric_dtype(df[column])
            )
        }

    return column_info


# --------------------------------------------------
# TOOL 2: Get an overall dataset summary
# --------------------------------------------------

def get_dataset_summary(df):
    """
    Generate an overall summary of the dataset.
    """

    numerical_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    categorical_columns = df.select_dtypes(
        include=["object", "str", "category", "bool"]
    ).columns.tolist()

    summary = {
        "total_rows": int(df.shape[0]),
        "total_columns": int(df.shape[1]),
        "numerical_columns_count": len(numerical_columns),
        "categorical_columns_count": len(categorical_columns),
        "total_missing_values": int(df.isnull().sum().sum()),
        "total_duplicate_rows": int(df.duplicated().sum()),
        "numerical_columns": numerical_columns,
        "categorical_columns": categorical_columns,
        "memory_usage_kb": round(
            float(df.memory_usage(deep=True).sum() / 1024), 2
        )
    }

    return summary


# --------------------------------------------------
# TOOL 3: Filter dataset rows dynamically
# --------------------------------------------------

def filter_data(df, column, operator, value=None):
    """
    Filter rows using a column, operator and value.

    Supported operators:
        eq, ne, gt, gte, lt, lte,
        contains, in, not_in, is_null, not_null
    """

    if column not in df.columns:
        raise ValueError(f"Column not found: {column}")

    allowed_operators = [
        "eq", "ne", "gt", "gte", "lt", "lte",
        "contains", "in", "not_in",
        "is_null", "not_null"
    ]

    if operator not in allowed_operators:
        raise ValueError(f"Unsupported operator: {operator}")

    series = df[column]

    if operator == "eq":
        mask = series == value

    elif operator == "ne":
        mask = series != value

    elif operator == "gt":
        mask = series > value

    elif operator == "gte":
        mask = series >= value

    elif operator == "lt":
        mask = series < value

    elif operator == "lte":
        mask = series <= value

    elif operator == "contains":
        mask = (
            series.astype("string")
            .str.contains(str(value), case=False, na=False, regex=False)
        )

    elif operator == "in":
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("'in' operator requires a list of values")

        mask = series.isin(value)

    elif operator == "not_in":
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("'not_in' operator requires a list of values")

        mask = ~series.isin(value)

    elif operator == "is_null":
        mask = series.isnull()

    else:  # not_null
        mask = series.notnull()

    return df.loc[mask].copy()


# --------------------------------------------------
# TOOL 4: Perform dynamic group-by aggregation
# --------------------------------------------------

def aggregate_data(df, group_column, target_column, operation="mean"):
    """
    Group data and perform an aggregation.

    Supported operations:
        mean, sum, min, max, count
    """

    if group_column not in df.columns:
        raise ValueError(f"Column not found: {group_column}")

    if target_column not in df.columns:
        raise ValueError(f"Column not found: {target_column}")

    allowed_operations = ["mean", "sum", "min", "max", "count"]

    if operation not in allowed_operations:
        raise ValueError(f"Unsupported operation: {operation}")

    if operation in ["mean", "sum", "min", "max"]:
        if not pd.api.types.is_numeric_dtype(df[target_column]):
            raise ValueError(
                f"Target column must be numerical for {operation}"
            )

    result = (
        df.groupby(group_column, dropna=False)[target_column]
        .agg(operation)
        .reset_index(name="result")
    )

    return result
