# ---- Assumptions ----
drivers_active = 3_000_000          # concurrent active drivers globally at peak
ping_interval_s = 4                 # driver location ping cadence
rides_per_day = 25_000_000          # global rides/day (Uber ~ tens of millions)
sec_per_day = 86_400

# ---- Location ingest (the firehose) ----
loc_qps = drivers_active / ping_interval_s
print(f"Driver location pings/sec       : {loc_qps:,.0f}  (~{loc_qps/1e6:.2f}M/s)")

# bytes per ping: driverId(8)+lat(8)+lng(8)+ts(8)+meta(~20) ~ 52B, call it 100B on wire
ping_bytes = 100
loc_bw_MBps = loc_qps * ping_bytes / 1e6
print(f"Location ingest bandwidth       : {loc_bw_MBps:,.0f} MB/s  (~{loc_bw_MBps*8/1000:.1f} Gbps)")

# ---- Ride request / matching QPS ----
rides_per_sec = rides_per_day / sec_per_day
peak_factor = 5                     # peak vs average
rides_peak = rides_per_sec * peak_factor
print(f"Avg ride requests/sec           : {rides_per_sec:,.0f}")
print(f"Peak ride requests/sec          : {rides_peak:,.0f}")

# ---- Fare estimates: people browse more than they buy ----
estimate_to_request = 5
est_peak = rides_peak * estimate_to_request
print(f"Peak fare estimates/sec         : {est_peak:,.0f}")

# ---- Read:write ratio on the hot path ----
# location writes dominate everything
print(f"\nLocation writes/sec             : {loc_qps:,.0f}")
print(f"Ride writes/sec (peak)          : {rides_peak:,.0f}")
print(f"Ratio loc-writes : ride-writes  : {loc_qps/rides_peak:,.0f} : 1")

# ---- Storage: ride records ----
ride_row_bytes = 1_000             # ride row w/ fare, locations, timestamps, status
rides_year = rides_per_day * 365
ride_storage_TB = rides_year * ride_row_bytes / 1e12
repl = 3
print(f"\nRide rows/year                  : {rides_year/1e9:.1f}B")
print(f"Ride storage/year (raw)         : {ride_storage_TB:,.1f} TB")
print(f"Ride storage/year (x{repl} repl + idx ~2x): {ride_storage_TB*repl*2:,.1f} TB")

# location is ephemeral - kept in memory, not durably stored long-term
