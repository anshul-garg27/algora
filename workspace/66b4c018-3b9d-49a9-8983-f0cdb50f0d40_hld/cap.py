
msgs_per_sec = 1_000_000
avg_bytes = 1024
ingress_MBs = msgs_per_sec*avg_bytes/1e6
ingress_Gbps = ingress_MBs*8/1000
print(f"Ingress: {ingress_MBs:.0f} MB/s  ~{ingress_Gbps:.1f} Gbps (1 copy)")
repl=3
print(f"Replicated disk write rate: {ingress_MBs*repl:.0f} MB/s across cluster")
groups=3
egress_MBs=ingress_MBs*groups
print(f"Egress (3 groups): {egress_MBs:.0f} MB/s ~{egress_MBs*8/1000:.1f} Gbps")
secs=7*24*3600
raw_TB=msgs_per_sec*avg_bytes*secs/1e12
print(f"Raw 7d: {raw_TB:.0f} TB  x{repl} replicas = {raw_TB*repl:.0f} TB")
part_throughput_MBs=10
parts=ingress_MBs/part_throughput_MBs
print(f"Partitions needed (~10MB/s each): ~{parts:.0f}")
broker_MBs=125
brokers=(ingress_MBs*repl)/broker_MBs
print(f"Brokers (~125MB/s each, replicated): ~{brokers:.0f}")
