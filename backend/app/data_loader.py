import pandas as pd

def load_dataset(file_path):
    """
    Load a CSV dataset into a Pandas DataFrame.
    """
    df = pd.read_csv(file_path , encoding="latin1")
    return df