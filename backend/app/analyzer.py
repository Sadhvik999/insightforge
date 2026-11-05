import pandas as pd


def numerical_summary(df, columns=None):
    """
    Generate statistical summaries for numerical columns.

    Parameters:
        df: Input DataFrame.
        columns: Optional list of numerical columns.

    Returns:
        DataFrame containing statistical summaries.
    """

    if columns is None:
        numeric_df = df.select_dtypes(include="number")
    else:
        numeric_df = df[columns]

        # Validate selected columns
        non_numeric = numeric_df.select_dtypes(
            exclude="number"
        ).columns.tolist()

        if non_numeric:
            raise ValueError(
                f"Non-numerical columns found: {non_numeric}"
            )

    return numeric_df.describe()


def categorical_summary(df, columns=None):
    """
    Generate summaries for categorical columns.
    """

    if columns is None:
        categorical_df = df.select_dtypes(
            include=["object", "str"]
        )
    else:
        categorical_df = df[columns]

        non_categorical = categorical_df.select_dtypes(
            exclude=["object", "str"]
        ).columns.tolist()

        if non_categorical:
            raise ValueError(
                f"Non-categorical columns found: {non_categorical}"
            )

    summary = {}

    for column in categorical_df.columns:
        summary[column] = {
            "unique_values": categorical_df[column].nunique(),
            "most_frequent": categorical_df[column].mode().iloc[0],
            "most_frequent_count": categorical_df[column].value_counts().iloc[0]
        }

    return summary


def group_analysis(df, group_column, target_column, operation="mean"):
    """
    Perform dynamic group-by analysis.
    """

    if group_column not in df.columns:
        raise ValueError(f"Column not found: {group_column}")

    if target_column not in df.columns:
        raise ValueError(f"Column not found: {target_column}")

    if operation not in ["mean", "sum", "min", "max", "count"]:
        raise ValueError("Unsupported operation")

    result = df.groupby(group_column)[target_column].agg(operation)

    return result.sort_values(ascending=False)


def correlation_analysis(df, columns=None, method="pearson"):
    """
    Calculate correlations between numerical columns.
    """

    if method not in ["pearson", "spearman", "kendall"]:
        raise ValueError("Unsupported correlation method")

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

    if numeric_df.shape[1] < 2:
        raise ValueError("At least two numerical columns are required")

    return numeric_df.corr(method=method)