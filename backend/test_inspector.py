from app.data_loader import load_dataset
from app.inspector import inspect_dataset

# Load dataset
df = load_dataset("../data/Sample - Superstore.csv")

# Inspect dataset
report = inspect_dataset(df)

print("===== DATASET INSPECTION REPORT =====")

print("\nRows:", report["rows"])
print("Columns:", report["columns"])

print("\nMissing Values:")
for column, count in report["missing_values"].items():
    print(column, ":", count)

print("\nDuplicate Rows:", report["duplicate_rows"])

print("\nBasic Statistics:")
print(report["statistics"])