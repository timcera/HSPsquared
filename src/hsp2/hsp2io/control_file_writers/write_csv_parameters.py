import os


def write_csv_parameters(basename, model, mode="w"):
    """
    Write a set of CSV files from a model dictionary.

    Parameters
    ----------
    basename : str
        The path and optional base name of the RUN.csv that identifies the
        location of the model files.
    model
        A dictionary of pandas DataFrames.
    """
    # Ensure the directory exists
    directory = os.path.dirname(basename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    basename = basename[: -len("run.csv")]

    # Write each DataFrame to a CSV file
    for key, df in model.items():
        skey = (str(k) for k in key)
        fname = "_".join(skey)
        csv_path = f"{basename}{fname}.csv"
        df.to_csv(csv_path, mode=mode, index=False)
    with open(f"{basename}run.csv", mode) as f:
        f.write("\n")
