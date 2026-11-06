
from .analyzer import (
    numerical_summary,
    categorical_summary,
    correlation_analysis
)

from .cleaner import clean_dataset


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




# Test integrated inspection with cleaning enabled

import pandas as pd
from app.inspector import inspect_dataset

test_df = pd.DataFrame({
    "Age": [20, None, 30, 30],
    "Salary": [30000, 40000, 50000, 50000],
    "City": ["Delhi", "Mumbai", None, None]
})

report = inspect_dataset(test_df, clean=True)

print("\nCleaning Integration Test")
print("Rows:", report["rows"])
print("Columns:", report["columns"])
print("Missing values:", report["missing_values"])
print("Duplicate rows:", report["duplicate_rows"])
print("Cleaning report:", report["cleaning_report"])

print("\nOriginal DataFrame unchanged:")
print(test_df.isnull().sum())
print("Original rows:", len(test_df))