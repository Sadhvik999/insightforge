
from .analyzer import (
    numerical_summary,
    categorical_summary,
    correlation_analysis
)

from .cleaner import clean_dataset, analyze_missing_values


def inspect_dataset(df, clean=False):
    """
    Inspect a dataset and return its basic information
    along with analytical summaries.

    If clean=True, clean the dataset before analysis.
    """

    # Keep the original DataFrame unchanged
    working_df = df.copy(deep=True)

    report = {}

    # 1. Clean dataset if requested
    if clean:
        working_df, cleaning_report = clean_dataset(working_df)
        report["cleaning_report"] = cleaning_report

    # 2. Dataset dimensions
    report["rows"] = working_df.shape[0]
    report["columns"] = working_df.shape[1]

    # 3. Column names
    report["column_names"] = working_df.columns.tolist()

    # 4. Data types
    report["data_types"] = working_df.dtypes.astype(str).to_dict()

    # 5. Missing values
    report["missing_values"] = working_df.isnull().sum().to_dict()
    report["missing_value_intelligence"] = analyze_missing_values(working_df, threshold=75.0)

    # 6. Duplicate rows
    report["duplicate_rows"] = int(working_df.duplicated().sum())

    # 7. Basic statistics
    report["statistics"] = working_df.describe().to_dict()

    # 8. Numerical analysis
    report["numerical_analysis"] = numerical_summary(working_df).to_dict()

    # 9. Categorical analysis
    report["categorical_analysis"] = categorical_summary(working_df)

    # 10. Correlation analysis
    numeric_columns = working_df.select_dtypes(include="number").columns.tolist()

    if len(numeric_columns) >= 2:
        report["correlation_analysis"] = (
            correlation_analysis(working_df).to_dict()
        )
    else:
        report["correlation_analysis"] = {}

    return report
