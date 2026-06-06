# --- Inputs (assumptions) ---
writes_per_day = 100_000_000          # 100M new links/day
read_write_ratio = 100                # 100:1 reads:writes
reads_per_day = writes_per_day * read_write_ratio

sec_per_day = 86_400
peak_factor = 5                       # peak is ~5x average

# --- QPS ---
write_avg = writes_per_day / sec_per_day
read_avg  = reads_per_day  / sec_per_day
write_peak = write_avg * peak_factor
read_peak  = read_avg  * peak_factor

print("=== QPS ===")
print(f"writes avg : {write_avg:,.0f}/s   peak ~{write_peak:,.0f}/s")
print(f"reads  avg : {read_avg:,.0f}/s   peak ~{read_peak:,.0f}/s")

# --- Cache miss QPS (the number that sizes the DB read tier) ---
hit_ratio = 0.95
miss_qps_peak = read_peak * (1 - hit_ratio)
print("\n=== Read tier sizing ===")
print(f"cache hit ratio assumed: {hit_ratio:.0%}")
print(f"DB read QPS at peak (misses): ~{miss_qps_peak:,.0f}/s")
print(f"DB read QPS COLD cache (0% hit): ~{read_peak:,.0f}/s")
redis_node_ceiling = 150_000
print(f"redis node ceiling ~{redis_node_ceiling:,}/s -> need ~{read_peak/redis_node_ceiling:.1f} hot nodes for reads")

# --- Keyspace ---
alphabet = 62
for n in (6, 7, 8):
    print(f"\n62^{n} = {alphabet**n:,}")
years_to_exhaust_7 = (alphabet**7) / writes_per_day / 365
print(f"\n7-char space lasts ~{years_to_exhaust_7:,.0f} years at {writes_per_day:,}/day")

# --- Storage (5 year horizon) ---
years = 5
total_links = writes_per_day * 365 * years
bytes_per_row = 500          # code+long url+metadata, generous
replication = 3
overhead = 2                 # indexes + WAL/compaction headroom
link_storage_TB = total_links * bytes_per_row * replication * overhead / 1e12
print(f"\n=== Storage (5yr) ===")
print(f"total links: {total_links:,}")
print(f"link table (x3 repl, x2 overhead): ~{link_storage_TB:,.0f} TB")

# Click events table (the big one)
clicks_5yr = reads_per_day * 365 * years
bytes_per_click = 100
click_raw_TB = clicks_5yr * bytes_per_click / 1e12
print(f"raw click events (5yr, 100B each): ~{click_raw_TB:,.0f} TB  <-- dominant if stored raw")

# --- Bandwidth / cost driver ---
resp_bytes = 500
egress_GB_day = reads_per_day * resp_bytes / 1e9
print(f"\nredirect egress: ~{egress_GB_day:,.0f} GB/day")
