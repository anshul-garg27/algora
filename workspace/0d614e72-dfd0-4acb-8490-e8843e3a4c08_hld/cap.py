
users=10_000_000
dau=2_000_000
orders_per_active_per_day=10
orders_day=dau*orders_per_active_per_day
avg_qps=orders_day/(6.25*3600)
print("orders/day:",orders_day, "avg order qps:",round(avg_qps))
spike=0.20*orders_day/(5*60)
print("peak order qps at open:",round(spike))
symbols=5000
ticks_per_symbol_per_sec=5
concurrent_subscribers=1_500_000
avg_subs_per_symbol=concurrent_subscribers/symbols
fanout_msgs=symbols*ticks_per_symbol_per_sec*avg_subs_per_symbol
print("raw tick fan-out msgs/sec:",f"{fanout_msgs:,.0f}")
order_row=300
trades_day=orders_day*0.7
events=orders_day*3 + trades_day
bytes_day=events*order_row
print("order-event GB/day:",round(bytes_day/1e9,1))
print("order-event TB/year x3:",round(bytes_day*365*3/1e12,1))
tick_row=50
tick_bytes_day=symbols*ticks_per_symbol_per_sec*6.25*3600*tick_row
print("tick history GB/day:",round(tick_bytes_day/1e9,1))
