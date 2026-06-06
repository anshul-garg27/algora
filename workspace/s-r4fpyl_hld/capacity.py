# ---- Inputs (rounded, defensible) ----
drivers_online_peak = 5_000_000      # concurrent online drivers globally at peak
loc_ping_interval_s = 4              # each online driver pings location every 4s
daily_rides = 50_000_000            # rides/day globally (Uber-scale order)
sec_per_day = 86_400

# ---- Location ingest (the firehose) ----
loc_writes_per_s = drivers_online_peak / loc_ping_interval_s
print(f"Location updates/sec (peak): {loc_writes_per_s:,.0f}  (~{loc_writes_per_s/1e6:.1f}M/s)")

# ---- Ride requests ----
avg_rides_per_s = daily_rides / sec_per_day
peak_factor = 5  # commute/event spikes concentrated in hot cities
peak_rides_per_s = avg_rides_per_s * peak_factor
print(f"Ride requests/sec (avg):  {avg_rides_per_s:,.0f}")
print(f"Ride requests/sec (peak): {peak_rides_per_s:,.0f}  (~{peak_rides_per_s/1000:.0f}K/s)")

# ---- Matching read amplification ----
# each request -> spatial query over nearby drivers; cheap vs location writes
print(f"\nRead:write feel -> location ingest dominates everything by ~{loc_writes_per_s/peak_rides_per_s:,.0f}:1")

# ---- Location store sizing ----
# Hot location state = latest position per driver, kept in memory (Redis geo)
bytes_per_driver_loc = 100  # driverId, lat, lng, ts, status, geohash
hot_loc_bytes = drivers_online_peak * bytes_per_driver_loc
print(f"\nHot location state (latest only): {hot_loc_bytes/1e9:.1f} GB  -> fits in a small Redis cluster")

# ---- Ride record storage (durable) ----
bytes_per_ride = 1_000  # ride row + denormalized fields
rides_per_year = daily_rides * 365
ride_storage_year = rides_per_year * bytes_per_ride
repl = 3
print(f"Ride rows/year: {rides_per_year/1e9:.1f}B  raw {ride_storage_year/1e12:.1f} TB"
      f"  x{repl} repl+overhead ~{ride_storage_year*repl*2/1e12:.0f} TB/yr")

# ---- One Redis node ceiling check ----
redis_node_ops = 150_000
nodes_needed = loc_writes_per_s / redis_node_ops
print(f"\nLocation writes {loc_writes_per_s/1e6:.1f}M/s ÷ ~150K ops/node "
      f"=> need ~{nodes_needed:.0f} shards (geo-partitioned) -- THIS forces sharding")
