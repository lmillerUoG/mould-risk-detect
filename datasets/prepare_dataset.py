import pandas as pd

input_file = "IoTsec-Room-Climate-Datasets.txt"
output_file = "sim_data.csv"

# Read full dataset
df = pd.read_csv(input_file, header=None, names=["timestamp_ms", "rh_pct", "temp_c"])

# Keep only rows 27000–28000 (inclusive of 28000)
df = df.iloc[27000:28001]

# Save only the temperature and humidity columns
df[["temp_c", "rh_pct"]].to_csv(output_file, index=False)

print(f"Saved filtered dataset to: {output_file} ({len(df)} rows)")
