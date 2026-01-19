import pandas as pd

df = pd.read_csv("logs/sweep_v3_results.csv")

# Sort by win_rate (descending), then total_pnl (descending)
df_sorted = df.sort_values(by=["win_rate", "total_pnl"], ascending=[False, False])

# Save ranked output
df_sorted.to_csv("logs/sweep_v3_ranked.csv", index=False)

print("=== Top 20 configs (ranked) ===")
print(df_sorted.head(20).to_string(index=False))

print("\n=== Bottom 20 configs (ranked) ===")
print(df_sorted.tail(20).to_string(index=False))
