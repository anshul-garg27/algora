
matches_live = 10
events_per_match_per_s = 1
write_qps = matches_live * events_per_match_per_s
print("Peak write QPS (ingestion):", write_qps)

concurrent_viewers = 50_000_000
poll_interval_s = 10
naive_read_qps = concurrent_viewers / poll_interval_s
print("Naive polling read QPS:", f"{naive_read_qps/1e6:.1f}M")

conns_per_node = 100_000
gateway_nodes = concurrent_viewers / conns_per_node
print("WebSocket gateway nodes needed:", int(gateway_nodes))

fanout_msgs_per_s = concurrent_viewers * 1
print("Fan-out messages/sec on an event:", f"{fanout_msgs_per_s/1e6:.0f}M")

print("Live state object: 5000 bytes ; fits in Redis")

matches_per_year = 2000
events_per_match = 2000
bytes_per_event = 1000
yearly = matches_per_year*events_per_match*bytes_per_event
print("Historical raw/yr:", f"{yearly/1e9:.1f} GB")
