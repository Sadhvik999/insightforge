
from .analyzer import (
    numerical_summary,
    categorical_summary,
    correlation_analysis
)


def inspect_dataset(df):
    """
    Inspect a dataset and return its basic information
    along with analytical summaries.
    """

    report = {}

    # 1. Dataset dimensions
    report["rows"] = df.shape[0]
    report["columns"] = df.shape[1]

    # 2. Column names
    report["column_names"] = df.columns.tolist()

    # 3. Data types
    report["data_types"] = df.dtypes.astype(str).to_dict()

    # 4. Missing values
    report["missing_values"] = df.isnull().sum().to_dict()

    # 5. Duplicate rows
    report["duplicate_rows"] = int(df.duplicated().sum())

    # 6. Basic statistics
    report["statistics"] = df.describe().to_dict()

    # 7. Numerical analysis
    report["numerical_analysis"] = numerical_summary(df).to_dict()

    # 8. Categorical analysis
    report["categorical_analysis"] = categorical_summary(df)

    # 9. Correlation analysis
    numeric_columns = df.select_dtypes(include="number").columns.tolist()

    if len(numeric_columns) >= 2:
        report["correlation_analysis"] = (
            correlation_analysis(df).to_dict()
        )
    else:
        report["correlation_analysis"] = {}

    return report
