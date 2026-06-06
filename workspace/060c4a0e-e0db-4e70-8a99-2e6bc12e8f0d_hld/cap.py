
orders_day = 10_000_000
sec = 86400
avg_qps = orders_day/sec
peak = avg_qps*5
print("avg orders/s", round(avg_qps), "peak", round(peak))

restaurants = 500_000
active = 0.10*restaurants
read_qps = active/30
print("active viewers", int(active), "read qps", round(read_qps))

bytes_per_order = 300
raw_day = orders_day*bytes_per_order
print("raw/day GB", round(raw_day/1e9,2), "raw/week GB", round(raw_day*7/1e9,1))

mins_week = 7*24*60
val_rows = restaurants*mins_week
print("value bucket rows", f"{val_rows/1e9:.1f}B", "GB", round(val_rows*40/1e9,1))

hours_week=7*24
item_rows = restaurants*hours_week*30
print("item hourly rows/wk", f"{item_rows/1e6:.0f}M", "GB", round(item_rows*30/1e9,1))

per_rest_bytes = 3*(8 + 30*16)
print("redis MB", round(restaurants*per_rest_bytes/1e6))
