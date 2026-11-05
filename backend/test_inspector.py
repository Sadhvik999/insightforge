from app.data_loader import load_dataset
from app.inspector import inspect_dataset

df = load_dataset("../data/Sample - Superstore.csv")

report = inspect_dataset(df)

print("INSIGHTFORGE DATASET REPORT")

print("\nDataset dimensions:")
print("Rows:", report["rows"])
print("Columns:", report["columns"])

print("\nMissing values:")
print(report["missing_values"])

print("\nDuplicate rows:")
print(report["duplicate_rows"])

print("\nNumerical analysis:")
print(report["numerical_analysis"])

print("\nCategorical analysis:")
print(report["categorical_analysis"])

print("\nCorrelation analysis:")
print(report["correlation_analysis"])