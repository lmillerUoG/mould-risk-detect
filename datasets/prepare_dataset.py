import pandas as pd

input_file = "IoTsec-Room-Climate-Datasets.txt"
output_file = "sim_data.csv"

df = pd.read_csv(input_file, header=None, names=["timestamp_ms", "rh_pct", "temp_c"])

df[["temp_c", "rh_pct"]].to_csv(output_file, index=False)


print(f"Saved dataset to: {output_file}")