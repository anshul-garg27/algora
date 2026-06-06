
drivers = 5_000_000
interval = 4
writes = drivers/interval
print("avg location updates/s:", writes)
print("peak (2x):", writes*2)
b = 8+8+8+8
print("ingest bandwidth MB/s avg:", writes*b/1e6)
viewers = 1_000_000
qps = viewers/10
print("heatmap query qps:", qps)
cells_per_city = 200_000
minutes_day = 1440
bytes_per_cell = 30
days = 365
raw = cells_per_city*minutes_day*bytes_per_cell*days
print("historical agg/year GB (1 city):", raw/1e9)
raw_ingest_day = writes*86400*b
print("raw ingest/day TB:", raw_ingest_day/1e12)
print("raw ingest/year PB:", raw_ingest_day*365/1e15)
