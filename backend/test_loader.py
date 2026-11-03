from app.data_loader import load_dataset

df = load_dataset('../data/Sample - Superstore.csv')
print(df.head())
print("\nDataset Shape:")
print(df.shape)

print("\nColumns:")
print(df.columns.tolist())