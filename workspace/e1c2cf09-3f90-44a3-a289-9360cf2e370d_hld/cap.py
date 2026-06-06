
sec=86400
msgs_day=100_000_000_000
avg=msgs_day/sec
peak=avg*3
print("avg msgs/s", f"{avg/1e6:.2f}M")
print("peak msgs/s", f"{peak/1e6:.2f}M")

concurrent=500_000_000
conns_per_server=100_000
print("ws servers", f"{concurrent/conns_per_server:,.0f}")

bytes_per_msg=300
raw=msgs_day*bytes_per_msg
repl=raw*3
print("raw/day GB", f"{raw/1e9:.0f}")
print("replicated/day TB", f"{repl/1e12:.1f}")
print("replicated/year PB", f"{repl*365/1e15:.1f}")

avg_group=50
group_msgs=msgs_day*0.3
fanout=group_msgs*avg_group + msgs_day*0.7
print("delivery rows/day", f"{fanout/1e12:.1f}T")
print("delivery peak/s", f"{fanout/sec*3/1e6:.1f}M")
