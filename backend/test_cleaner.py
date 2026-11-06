
import pandas as pd

from app.data_loader import load_dataset

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


# Load actual dataset
df = load_dataset("../data/Sample - Superstore.csv")


# 1. Missing-value report

missing_report = detect_missing_values(df)

print("MISSING VALUE REPORT")

for column, details in missing_report.items():

    print(
        f"{column}: {details['missing_count']} "
        f"({details['missing_percentage']}%)"
    )


# 2. Duplicate report

duplicate_report = detect_duplicates(df)

print("\nDUPLICATE REPORT")

print(
    "Duplicate rows:",
    duplicate_report["duplicate_count"]
)

print(
    "Duplicate percentage:",
    duplicate_report["duplicate_percentage"],
    "%"
)


# 3. Outlier report

outlier_report = detect_outliers(df)

print("\nOUTLIER REPORT")

for column, details in outlier_report.items():

    print(f"\nColumn: {column}")

    print(
        "Outlier count:",
        details["outlier_count"]
    )

    print(
        "Lower bound:",
        round(details["lower_bound"], 2)
    )

    print(
        "Upper bound:",
        round(details["upper_bound"], 2)
    )


# 4. Date column detection

date_columns = detect_date_columns(df)

print("\nDATE COLUMN REPORT")

print(
    "Potential date columns:",
    date_columns
)


# 5. Date conversion

cleaned_df = convert_date_columns(
    df,
    date_columns
)

print("\nDATE CONVERSION REPORT")

for column in date_columns:

    print(f"\nColumn: {column}")

    print(
        "Original type:",
        df[column].dtype
    )

    print(
        "Converted type:",
        cleaned_df[column].dtype
    )


# Verify original dataset is unchanged

print(
    "\nOriginal dataset unchanged:",
    df[date_columns].equals(
        load_dataset(
            "../data/Sample - Superstore.csv"
        )[date_columns]
    )
)


# 6. Numerical missing-value imputation

test_df = df.copy()

# Introduce missing values into a temporary copy
test_df.loc[0, "Sales"] = None
test_df.loc[1, "Profit"] = None

print("\nBEFORE IMPUTATION")

print(
    test_df[["Sales", "Profit"]].isnull().sum()
)


# Mean imputation

mean_cleaned_df, mean_skipped, mean_filled = (
    fill_missing_values(
        test_df,
        strategy="mean",
        columns=["Sales", "Profit"]
    )
)

print("\nAFTER MEAN IMPUTATION")

print(
    mean_cleaned_df[
        ["Sales", "Profit"]
    ].isnull().sum()
)


# Median imputation

median_cleaned_df, median_skipped, median_filled = (
    fill_missing_values(
        test_df,
        strategy="median",
        columns=["Sales", "Profit"]
    )
)

print("\nAFTER MEDIAN IMPUTATION")

print(
    median_cleaned_df[
        ["Sales", "Profit"]
    ].isnull().sum()
)


# Verify original dataset is unchanged

print(
    "\nOriginal dataset unchanged:",
    df.isnull().sum().sum() == 0
)


# 7. Categorical missing-value imputation

categorical_test_df = df.copy()

original_mode = (
    categorical_test_df["Segment"].mode().iloc[0]
)

categorical_test_df.loc[0, "Segment"] = None

mode_cleaned_df, mode_skipped, mode_filled = (
    fill_missing_categorical(
        categorical_test_df,
        columns=["Segment"]
    )
)

print("\nBEFORE MODE IMPUTATION")

print(
    categorical_test_df["Segment"].isnull().sum()
)

print("\nAFTER MODE IMPUTATION")

print(
    mode_cleaned_df["Segment"].isnull().sum()
)

print(
    "\nFilled value:",
    mode_cleaned_df.loc[0, "Segment"]
)

print(
    "Expected mode:",
    original_mode
)

print(
    "Original dataset unchanged:",
    df["Segment"].isnull().sum() == 0
)


# 8. Duplicate removal

duplicate_test_df = pd.concat(
    [df, df.iloc[[0]]],
    ignore_index=True
)

cleaned_df, removed_count = remove_duplicates(
    duplicate_test_df
)

print("\nDUPLICATE REMOVAL REPORT")

print(
    "Rows before cleaning:",
    len(duplicate_test_df)
)

print(
    "Rows after cleaning:",
    len(cleaned_df)
)

print(
    "Duplicates removed:",
    removed_count
)

print(
    "Original dataset unchanged:",
    len(df) == 9994
)


# 9. Complete cleaning workflow

workflow_test_df = df.copy()

# Add missing numerical and categorical values
workflow_test_df.loc[0, "Sales"] = None
workflow_test_df.loc[1, "Segment"] = None

# Add one duplicate row
workflow_test_df = pd.concat(
    [
        workflow_test_df,
        workflow_test_df.iloc[[2]]
    ],
    ignore_index=True
)

cleaned_df, cleaning_report = clean_dataset(
    workflow_test_df
)

print("\nCOMPLETE CLEANING REPORT")

print(
    "Rows before cleaning:",
    len(workflow_test_df)
)

print(
    "Rows after cleaning:",
    len(cleaned_df)
)

print(
    "Duplicates removed:",
    cleaning_report["duplicates_removed"]
)

print(
    "Converted date columns:",
    cleaning_report["converted_date_columns"]
)

print(
    "Missing values after cleaning:",
    cleaned_df.isnull().sum().sum()
)


# Detailed cleaning operation report

print(
    "Numerical values filled:",
    cleaning_report["numerical_values_filled"]
)

print(
    "Categorical values filled:",
    cleaning_report["categorical_values_filled"]
)

print(
    "Skipped numerical columns:",
    cleaning_report["skipped_numerical_columns"]
)

print(
    "Skipped categorical columns:",
    cleaning_report["skipped_categorical_columns"]
)


# Verify original dataset is unchanged

print(
    "Original dataset unchanged:",
    df.isnull().sum().sum() == 0
    and len(df) == 9994
)


# 10. All-null numerical column test

edge_case_df = pd.DataFrame({
    "Age": pd.Series(
        [None, None, None],
        dtype="float64"
    ),
    "Salary": [30000, 40000, 50000]
})

edge_case_cleaned, skipped_columns, filled_counts = (
    fill_missing_values(
        edge_case_df,
        strategy="mean"
    )
)

print("\nALL-NULL COLUMN TEST")

print(edge_case_cleaned)

print(
    "Skipped columns:",
    skipped_columns
)

print(
    "Filled counts:",
    filled_counts
)

print(
    "Remaining missing values:",
    edge_case_cleaned.isnull().sum().to_dict()
)
