
peak_views_per_sec = 500_000
avg_views_per_sec  = 150_000
event_bytes        = 200

print("Peak ingest QPS:", peak_views_per_sec)
print("Avg ingest QPS :", avg_views_per_sec)

log_bw_mb = peak_views_per_sec * event_bytes / 1e6
print(f"Peak log write bandwidth: {log_bw_mb:.0f} MB/s")

daily = avg_views_per_sec * 86400
print(f"Daily events: {daily/1e9:.1f} billion/day")

raw_bytes = daily * 90 * event_bytes * 3
print(f"Raw events 90d x3 replicas: {raw_bytes/1e12:.0f} TB")

videos_total = 2_000_000_000
agg_row_bytes = 40
alltime = videos_total * agg_row_bytes * 3
print(f"All-time counters (2B videos) x3: {alltime/1e12:.1f} TB")

hourly = 200_000_000 * 720 * agg_row_bytes * 3
print(f"Hourly buckets (200M active x720) x3: {hourly/1e12:.0f} TB")

redis_node = 150_000
print(f"Redis nodes needed if all hit one tier: {peak_views_per_sec/redis_node:.1f}")
