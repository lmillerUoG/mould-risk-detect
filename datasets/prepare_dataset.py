import pandas as pd

input_file = "AirQualityUCI.csv"
output_file = "sim_data.csv"

df = pd.read_csv(input_file, sep=';', decimal=',')
df = df.rename(columns=lambda x: x.strip())

subset = df[['T', 'RH']].dropna().head(500)
subset.to_csv(output_file, index=False)

print(f"Saved trimmed dataset to: {output_file}")