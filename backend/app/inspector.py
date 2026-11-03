def inspect_dataset(df):
    """
    Inspect a dataset and return its basic information.
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

    return report