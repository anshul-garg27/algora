
symbols = 10_000
peak_ticks_per_sec = 1_000_000
avg_ticks_per_sec = 100_000
alerts = 50_000_000
users = 5_000_000

hot_share = 0.02
hot_symbol_alerts = alerts * hot_share
hot_ticks = 50
naive_evals_per_sec = hot_symbol_alerts * hot_ticks

bytes_per_alert = 300
alert_storage_gb = alerts * bytes_per_alert / 1e9
alert_storage_real_gb = alert_storage_gb * 3 * 1.5

fires_per_day = 5_000_000
log_bytes = 500
log_90d_gb = fires_per_day * 90 * log_bytes / 1e9

tick_bytes = 40
ticks_per_year = avg_ticks_per_sec * 86400 * 365
hist_tb = ticks_per_year * tick_bytes / 1e12

eff_bytes = 1000
alerts_per_node_mem = 64e9 / eff_bytes
nodes_for_alerts = alerts / alerts_per_node_mem

print(f"peak ticks/s: {peak_ticks_per_sec:,}")
print(f"hot symbol alerts: {hot_symbol_alerts:,.0f}")
print(f"naive evals/s on ONE hot symbol if rescanned: {naive_evals_per_sec:,.0f}")
print(f"alert raw storage GB: {alert_storage_gb:,.0f}")
print(f"alert storage w/ 3x repl + index GB: {alert_storage_real_gb:,.0f}")
print(f"90-day notif log GB: {log_90d_gb:,.0f}")
print(f"1yr historical ticks TB: {hist_tb:,.0f}")
print(f"alerts per 64GB node (in-mem): {alerts_per_node_mem:,.0f}")
print(f"matching nodes needed (mem only): {nodes_for_alerts:,.1f}")
