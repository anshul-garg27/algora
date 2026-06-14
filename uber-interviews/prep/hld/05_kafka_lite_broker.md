# HLD Playbook 5: Distributed Message Broker (Kafka-lite)
*Asked at Uber as a Senior round ("design a distributed messaging system like
Kafka/RabbitMQ — persistence, partitioning, consumer coordination") and it's
the HLD twin of the LLD pub-sub machine-coding round (3x). Learn both layers
and you cover two interview rounds with one mental model.*

## The prompt
"Design a scalable, fault-tolerant message broker: publishers, subscribers,
topics, reliable delivery, decoupling."

## Step 1 — Requirements
- FR: topics; publish; subscribe (consumer groups: each message to ONE
  member); replay (offset reset); ordering guarantee — ask WHICH: global
  (expensive) vs per-partition (standard; per-key via partition keying).
- NFR: durability (no loss on broker crash); throughput (~1M msg/s);
  at-least-once baseline delivery; consumer lag observability.
- Ask: message size cap? retention (time/size)? fan-out count?

## Step 2 — Estimates
1M msg/s × 1KB = 1 GB/s cluster-wide → forces partitioning (no single node
does 1GB/s durable writes) and **sequential disk I/O**: append-only log +
page cache ≈ disk at memory-ish speed. (The real candidate said exactly
"write-ahead log + page cache" — it landed.)

## Step 3 — The data model IS the design: the partitioned log
- Topic = N **partitions**; partition = append-only segment files on disk.
- Message gets (partition, monotonically increasing **offset**).
- Ordering: guaranteed within a partition only; producer keys (e.g., user_id)
  → consistent hash → same partition → per-key order. Say this trade
  ("global order would serialize the world to one partition").
- Consumers don't delete: they track **their own offset** (stored back in a
  special topic / metadata store). Retention deletes old segments by
  time/size, independent of consumption. This decoupling = replay for free.

## Step 4 — Architecture
```
producers ──► broker cluster (each partition: 1 leader + R-1 replicas)
                │ append to leader log → replicate to followers
                │ ack modes: acks=0/1/quorum (producer chooses)
consumers (group "g1") ◄── pull from partition leaders
                │ group coordinator assigns partitions ↔ members
metadata/coordination: Raft/ZK-style — leader election, ISR, group membership
```
Key choices to narrate:
- **Pull, not push** (the real round's discussion): consumers control pace →
  natural backpressure; long-poll to avoid busy polling.
- **Leader per partition**: all writes go to leader; followers replicate;
  in-sync replica set (ISR); commit = quorum ack (acks=all) for durability.
- **Consumer groups**: coordinator runs assignment (partition count caps
  group parallelism — say it); heartbeats; member death → rebalance.

## Step 5 — Deep dives
**Durability vs latency (probe #1):** producer `acks`: 0 = fire-forget,
1 = leader fsync'd... actually leader-received, quorum = ISR replicated.
Loss windows of each; pick quorum for money, 1 for telemetry. Trade-off
table answers beat single answers.

**Broker dies:** its partitions' leadership fails over to an ISR follower
(metadata layer). Un-replicated tail (acks=1) is lost — tie back to acks.
Consumer offsets live in replicated metadata → consumers resume.

**Exactly-once? (probe #2 — the trap):** the honest answer: delivery is
at-least-once after rebalances/redeliveries; "exactly-once PROCESSING" =
consumer-side idempotency (dedupe on message key) or transactional
offsets+output commit (Kafka EOS-style, expensive). Never claim free
exactly-once — interviewers set this trap deliberately.

**Slow consumer (probe #3):** pull model means it just lags; monitor lag =
(log end offset − committed offset); alert; scale group members up to
partition count; beyond that → repartition or batch processing.

**Rebalance storms:** static membership / cooperative rebalancing one-liner:
"don't stop-the-world; move only the partitions that need moving."

**Why is it fast? (probe #4):** sequential appends; page cache; zero-copy
sendfile to consumers; batching+compression producer-side. Four bullets,
memorize.

## Connecting down to the LLD round
The 45-min machine-coding version (`../lld/pubsub_broker.py`) is this design
with: partitions=1, replication=none, group=all-fan-out, Condition variable
instead of long-poll. If you've internalized the HLD, the LLD class split
(Broker / Topic / subscriber offsets + lock + Condition) falls out naturally —
rehearse saying that mapping; interviewers LOVE the cross-altitude story.

## Sentences that score
- "Ordering is a per-partition contract; per-key ordering via partition keys."
- "Consumers own their offsets; retention is time-based — that's why replay
  is free."
- "At-least-once delivery, exactly-once effect via idempotent consumers."
- "Append-only log + page cache + zero-copy is the whole performance story."
