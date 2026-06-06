# --- Inputs ---
daily_rides = 10_000_000
active_drivers = 5_000_000
loc_update_interval_s = 4          # each active driver pings every 4s
seconds_per_day = 86_400
peak_factor = 3                    # peak vs average multiplier

# --- Driver location write QPS (the firehose) ---
loc_writes_avg = active_drivers / loc_update_interval_s
loc_writes_peak = loc_writes_avg * peak_factor

# --- Ride request / match QPS ---
# Assume ~2x estimate calls per actual ride (people check, then request)
estimate_qps_avg = (daily_rides * 2) / seconds_per_day
request_qps_avg  = daily_rides / seconds_per_day
request_qps_peak = request_qps_avg * peak_factor
estimate_qps_peak = estimate_qps_avg * peak_factor

# --- Read:write framing ---
# location writes dominate everything
ratio_loc_to_match = loc_writes_peak / request_qps_peak

# --- Storage: driver location is mostly in-memory (current pos only) ---
# 5M drivers * ~ (id 8 + lat 8 + lng 8 + ts 8 + meta 32) ~= 64 bytes
loc_bytes_per_driver = 64
loc_hot_state_gb = active_drivers * loc_bytes_per_driver / 1e9

# --- Ride records (durable) ---
# ride row ~ 1KB (ids, locations, fare, status, timestamps)
ride_row_bytes = 1024
rides_per_year = daily_rides * 365
ride_storage_tb_raw = rides_per_year * ride_row_bytes / 1e12
# replication x3 + indexes ~ 4x
ride_storage_tb_real = ride_storage_tb_raw * 4

def r(x):
    if x >= 1_000_000: return f"{x/1_000_000:.1f}M"
    if x >= 1_000: return f"{x/1_000:.0f}K"
    return f"{x:.1f}"

print("Location write QPS (avg):   ", r(loc_writes_avg))
print("Location write QPS (peak):  ", r(loc_writes_peak))
print("Estimate QPS (peak):        ", r(estimate_qps_peak))
print("Ride request QPS (avg):     ", r(request_qps_avg))
print("Ride request QPS (peak):    ", r(request_qps_peak))
print("Loc-writes : matches ratio: ", f"{ratio_loc_to_match:.0f}:1")
print("Hot location state (GB):    ", f"{loc_hot_state_gb:.0f}")
print("Ride storage/yr raw (TB):   ", f"{ride_storage_tb_raw:.1f}")
print("Ride storage/yr real (TB):  ", f"{ride_storage_tb_real:.1f}")
