from app.data_loader import load_dataset
from app.analyzer import numerical_summary,categorical_summary,group_analysis,correlation_analysis

df = load_dataset("../data/Sample - Superstore.csv")

result = numerical_summary(df)

print("NUMERICAL ANALYSIS")
print(result)

print("\nCATEGORICAL ANALYSIS")
result = categorical_summary(df)
print(result)

print("\nGROUP-BY ANALYSIS")

print("\nTotal Sales by Category:")
print(group_analysis(df, "Category", "Sales", "sum"))

print("\nAverage Profit by Region:")
print(group_analysis(df, "Region", "Profit", "mean"))

print("\nTotal Sales by Segment:")
print(group_analysis(df, "Segment", "Sales", "sum"))

print("\nCORRELATION ANALYSIS")

result = correlation_analysis(
    df,
    columns=["Sales", "Profit", "Discount", "Quantity"]
)

print(result)