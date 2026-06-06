# --- Writes ---
writes_per_month = 100_000_000
seconds_per_month = 30 * 24 * 3600
write_qps = writes_per_month / seconds_per_month
write_qps_peak = write_qps * 5  # peak multiplier

# --- Reads (100:1) ---
read_qps = write_qps * 100
read_qps_peak = read_qps * 5

# --- Storage over 5 years ---
# per row: short_code(7) + long_url(~100) + creator_id(8) + created_at(8)
#          + expiry(8) + overhead/indexes ~ call it ~500 bytes all-in
bytes_per_row = 500
links_5yr = writes_per_month * 12 * 5
raw_storage_tb = links_5yr * bytes_per_row / 1e12
# with replication x3 and index/WAL headroom ~2x
storage_with_repl_tb = raw_storage_tb * 3 * 2

# --- Code space: base62, 7 chars ---
code_space = 62 ** 7
years_to_exhaust = code_space / writes_per_month / 12

# --- Cache sizing: hot 20% of reads, store hottest links ---
# top 20% of links serve 80% of reads; size cache for ~100M hottest links
hot_links = 100_000_000
cache_bytes_per_entry = 120  # code->url, trimmed
cache_gb = hot_links * cache_bytes_per_entry / 1e9

# --- Miss QPS at 90% hit ratio ---
hit_ratio = 0.90
miss_qps_peak = read_qps_peak * (1 - hit_ratio)

def r(x):
    return f"{x:,.0f}"

print("Write QPS avg:        ", r(write_qps))
print("Write QPS peak (5x):  ", r(write_qps_peak))
print("Read QPS avg:         ", r(read_qps))
print("Read QPS peak (5x):   ", r(read_qps_peak))
print("Links over 5yr:       ", r(links_5yr))
print("Raw storage (TB):     ", f"{raw_storage_tb:,.1f}")
print("Storage x3repl x2 (TB):", f"{storage_with_repl_tb:,.1f}")
print("Code space 62^7:      ", f"{code_space:,}")
print("Years to exhaust:     ", f"{years_to_exhaust:,.0f}")
print("Cache size (GB):      ", f"{cache_gb:,.0f}")
print("Miss QPS peak @90% hit:", r(miss_qps_peak))
