# Ride-sharing backend capacity — only the numbers that drive a decision

# --- Assumptions ---
concurrent_drivers = 10_000_000      # 10M drivers online at peak
ping_interval_s = 4                  # location update every 4s
rides_per_day = 20_000_000           # 20M rides/day (Uber-ish order of magnitude)
seconds_per_day = 86_400

# --- 1. Location update firehose (THE binding number) ---
location_writes_per_s = concurrent_drivers / ping_interval_s
print(f"Location updates/sec (avg)      : {location_writes_per_s:,.0f}  (~{location_writes_per_s/1e6:.1f}M/s)")
# peak multiplier for rush hour clustering
peak = location_writes_per_s * 1.5
print(f"Location updates/sec (peak x1.5): {peak:,.0f}  (~{peak/1e6:.1f}M/s)")

# --- 2. Ride requests (the matching work) ---
rides_per_s = rides_per_day / seconds_per_day
rides_peak = rides_per_s * 5   # rides cluster hard at rush hour
print(f"Ride requests/sec (avg)         : {rides_per_s:,.0f}  (~{rides_per_s/1000:.1f}K/s)")
print(f"Ride requests/sec (peak x5)     : {rides_peak:,.0f}  (~{rides_peak/1000:.1f}K/s)")

# --- 3. Read:write ratio for location ---
# every active trip = 2 parties tracking each other ~1/s
active_trips = 2_000_000
track_reads_per_s = active_trips * 2
print(f"Live-track reads/sec            : {track_reads_per_s:,.0f}  (~{track_reads_per_s/1e6:.1f}M/s)")

# --- 4. Single-node ceiling check ---
redis_geo_ops_ceiling = 100_000  # ~100K ops/s realistic per Redis node
nodes_needed = peak / redis_geo_ops_ceiling
print(f"\nRedis nodes if ALL writes hit one geo index: {nodes_needed:,.0f}")
print("=> Cannot use a single global index. MUST shard by geography.")

# --- 5. Storage: location is ephemeral, trips are durable ---
bytes_per_location = 64          # driverId, lat, lng, ts, status
hot_location_state = concurrent_drivers * bytes_per_location
print(f"\nHot location state (latest only): {hot_location_state/1e9:.1f} GB  (fits in a sharded in-memory tier)")

trip_row_bytes = 500
trips_per_year = rides_per_day * 365
trip_storage_year = trips_per_year * trip_row_bytes * 3  # x3 replication
print(f"Trip history/yr (x3 replication): {trip_storage_year/1e12:.1f} TB/yr")
