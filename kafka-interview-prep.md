# Kafka — Complete Interview Prep Guide

A zero-to-interview-ready guide to Apache Kafka, in simple terms with real-world analogies.

---

## 1. What is Kafka? (The Simple Story)

**Imagine a WhatsApp group:**
- People (apps) send messages to a group
- Other people (apps) read those messages
- Messages stay in the group history even after being read
- New members can scroll up and read old messages

**That's Kafka.** It's a system where:
- **Producers** send messages
- **Consumers** read messages
- Messages are stored durably (on disk) for a configured time
- Many consumers can read the same message independently

Officially: **Kafka is a distributed event streaming platform** used for high-throughput, fault-tolerant, real-time data pipelines.

### Why Kafka exists
Old systems (like RabbitMQ) delete messages after consumption. Kafka **keeps them** — so you can replay events, add new consumers later, and build event-driven systems.

---

## 2. Core Concepts (Memorize These)

### 2.1 Topic
A **named stream** of messages. Like a folder/channel.
- Example: `user-signups`, `payment-events`, `order-placed`

### 2.2 Partition
Each topic is split into **partitions** (for parallelism + scalability).
- Topic `orders` with 3 partitions = 3 separate logs
- Each partition is an **ordered, immutable, append-only log**
- Order is guaranteed **within a partition**, NOT across partitions

```
Topic: orders
 ├── Partition 0: [msg1, msg2, msg3, ...]
 ├── Partition 1: [msg1, msg2, msg3, ...]
 └── Partition 2: [msg1, msg2, msg3, ...]
```

### 2.3 Offset
A unique sequential ID for each message in a partition. Like a row number.
- Consumers track "where they are" using offsets.

### 2.4 Producer
App that **writes** messages to a topic.

### 2.5 Consumer
App that **reads** messages from a topic.

### 2.6 Consumer Group
A group of consumers sharing the work.
- **Rule:** Each partition is consumed by **only one** consumer in a group.
- 3 partitions + 3 consumers in a group = each gets 1 partition (parallel).
- 3 partitions + 5 consumers = 2 consumers sit idle.
- 3 partitions + 1 consumer = that consumer reads all 3.

This is **how Kafka scales consumption**.

### 2.7 Broker
A Kafka **server**. A Kafka cluster = multiple brokers.

### 2.8 Cluster
A group of brokers working together.

### 2.9 Replication
Each partition is copied to multiple brokers for fault tolerance.
- **Replication factor = 3** means 3 copies exist.
- One copy is the **Leader** (handles reads/writes).
- Others are **Followers** (replicate from leader).
- If leader dies, a follower becomes the new leader.

### 2.10 ZooKeeper / KRaft
- Old Kafka used **ZooKeeper** to manage cluster metadata.
- New Kafka (2.8+) uses **KRaft** (Kafka Raft) — no ZooKeeper needed.
- *Interview tip:* Mention KRaft is the modern way.

---

## 3. How a Message Flows (End-to-End)

```
[Producer] → sends message with optional key →
[Broker]   → determines partition (hash of key % num_partitions) →
            → writes to leader partition →
            → replicates to followers →
[Consumer] → polls broker → reads from assigned partition → commits offset
```

### Partition selection rule
- **If key is provided** → `hash(key) % partitions` → same key always goes to same partition (preserves order per key, e.g., per user).
- **If no key** → round-robin / sticky.

**Interview gold:** "I use the user ID as the key so all events for a user go to the same partition and are processed in order."

---

## 4. Delivery Guarantees (VERY Important for Interviews)

### 4.1 At-most-once
Message may be lost, never duplicated. (Fire and forget.)

### 4.2 At-least-once (default)
Message never lost, may be duplicated. (Most common.)

### 4.3 Exactly-once
Never lost, never duplicated. Achieved with:
- **Idempotent producer** (`enable.idempotence=true`)
- **Transactions** (`transactional.id`)

### Producer `acks` setting
| acks | Meaning | Durability |
|------|---------|------------|
| `0` | Don't wait for ack | Fastest, can lose data |
| `1` | Wait for leader only | Balanced |
| `all` (`-1`) | Wait for leader + all in-sync replicas | Safest |

**Use `acks=all` + `min.insync.replicas=2` + `enable.idempotence=true` for safety.**

---

## 5. Key Configurations to Know

### Producer
- `acks` — durability
- `retries` — retry on failure
- `batch.size` / `linger.ms` — batching for throughput
- `compression.type` — `snappy`, `lz4`, `gzip`, `zstd`
- `enable.idempotence=true` — no duplicates from retries

### Consumer
- `group.id` — consumer group
- `auto.offset.reset` — `earliest` or `latest` (where to start if no offset)
- `enable.auto.commit` — auto-commit offsets (set `false` for manual control)
- `max.poll.records` — batch size per poll
- `session.timeout.ms` — heartbeat timeout

### Topic
- `num.partitions`
- `replication.factor`
- `retention.ms` — how long to keep messages (default 7 days)
- `cleanup.policy` — `delete` or `compact`

---

## 6. Log Compaction vs Retention

- **Delete (default):** Drops messages older than `retention.ms`.
- **Compact:** Keeps **only the latest value per key**. Used for "current state" topics (e.g., user profile updates). Old keys are eventually deleted.

---

## 7. Consumer Rebalancing

When a consumer joins/leaves a group, partitions are **rebalanced** across remaining consumers.
- During rebalance, consumption pauses briefly ("stop the world").
- Newer Kafka uses **cooperative/incremental rebalancing** to reduce pauses.

---

## 8. Common Real-World Use Cases

1. **Event-driven microservices** — services publish events, others react.
2. **Log aggregation** — collect logs from many services.
3. **Stream processing** — real-time analytics (with Kafka Streams / Flink).
4. **Change Data Capture (CDC)** — DB changes → Kafka (via Debezium).
5. **Metrics pipelines** — IoT, clickstreams.
6. **Decoupling** — producer doesn't care who consumes.

---

## 9. Kafka Ecosystem

- **Kafka Connect** — pre-built connectors to move data in/out (DB, S3, Elasticsearch).
- **Kafka Streams** — Java library for stream processing.
- **ksqlDB** — SQL on streams.
- **Schema Registry** — manages Avro/Protobuf/JSON schemas (versioning).
- **MirrorMaker** — replicate between clusters.

---

## 10. Hands-On: Run Kafka Locally (5 minutes)

```bash
docker run -d --name kafka -p 9092:9092 apache/kafka:latest
```

Or with docker-compose:

```yaml
services:
  kafka:
    image: apache/kafka:latest
    ports:
      - "9092:9092"
```

### CLI commands every engineer should know

```bash
# Create topic
kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic orders --partitions 3 --replication-factor 1

# List topics
kafka-topics.sh --bootstrap-server localhost:9092 --list

# Describe topic
kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic orders

# Produce
kafka-console-producer.sh --bootstrap-server localhost:9092 --topic orders

# Consume from beginning
kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic orders --from-beginning

# Consumer groups
kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --group my-group
```

---

## 11. Code Examples

### Java Producer

```java
Properties props = new Properties();
props.put("bootstrap.servers", "localhost:9092");
props.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
props.put("value.serializer", "org.apache.kafka.common.serialization.StringSerializer");
props.put("acks", "all");
props.put("enable.idempotence", "true");

KafkaProducer<String, String> producer = new KafkaProducer<>(props);
producer.send(new ProducerRecord<>("orders", "user-123", "order-placed"));
producer.close();
```

### Java Consumer

```java
Properties props = new Properties();
props.put("bootstrap.servers", "localhost:9092");
props.put("group.id", "order-service");
props.put("key.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
props.put("value.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
props.put("auto.offset.reset", "earliest");
props.put("enable.auto.commit", "false");

KafkaConsumer<String, String> consumer = new KafkaConsumer<>(props);
consumer.subscribe(List.of("orders"));

while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
    for (ConsumerRecord<String, String> record : records) {
        System.out.printf("key=%s value=%s offset=%d%n",
            record.key(), record.value(), record.offset());
    }
    consumer.commitSync();
}
```

---

## 12. TOP INTERVIEW QUESTIONS (with answers)

### Q1: What is Kafka and why use it over RabbitMQ?
Kafka is a distributed event streaming platform optimized for high throughput, durability, and replay. Unlike RabbitMQ (a traditional broker that deletes messages after ack), Kafka **persists messages** for a configured retention, enabling multiple independent consumers and replay.

### Q2: How does Kafka guarantee ordering?
Order is guaranteed **only within a partition**. To preserve order for a logical entity (e.g., a user), use that entity's ID as the message key — Kafka hashes the key and routes it to the same partition.

### Q3: What's the difference between a consumer and a consumer group?
A consumer reads from topics. A consumer group is a set of consumers that **share** partitions — each partition is read by exactly one consumer in the group. This enables parallel scaling.

### Q4: What happens if a broker fails?
Each partition has replicas. If the leader broker fails, one of the **in-sync replicas (ISR)** is promoted to leader automatically. Producers/consumers transparently reconnect.

### Q5: How do you achieve exactly-once semantics?
- Set `enable.idempotence=true` on producer (prevents duplicates from retries).
- Use **transactions** (`transactional.id`) when writing to multiple partitions/topics atomically.
- On consumer side, commit offsets in the same transaction as the side effect (read-process-write pattern).

### Q6: What is ISR (In-Sync Replicas)?
Replicas that are caught up with the leader. If a replica falls behind, it's removed from ISR. `min.insync.replicas` controls how many ISR are needed for a write to succeed with `acks=all`.

### Q7: What's the difference between `earliest` and `latest` for `auto.offset.reset`?
Used when a consumer group has no committed offset:
- `earliest` → start from the oldest message.
- `latest` → start from new messages only.

### Q8: How do you decide the number of partitions?
Based on:
- Target throughput (more partitions = more parallelism).
- Number of consumers (partitions ≥ consumers in group).
- Ordering requirements (more partitions = less global order).
- Rule of thumb: start with 3–10x your consumer count. Hard to reduce later.

### Q9: What is log compaction? When to use it?
Kafka keeps only the **latest message per key**, deleting older ones. Use for state-like topics (e.g., user profile, latest config) where you only need the current value.

### Q10: How does Kafka achieve high throughput?
- **Sequential disk writes** (append-only log).
- **Zero-copy** (`sendfile` syscall) for sending data to consumers.
- **Batching** on producer and consumer.
- **Compression** (snappy, lz4).
- **Partitioning** for parallelism.

### Q11: What is a rebalance? Why is it bad?
When a consumer joins/leaves a group, partitions are reassigned. During rebalance, consumption pauses. Frequent rebalances hurt throughput. Mitigate with cooperative rebalancing and proper `session.timeout.ms`.

### Q12: Producer `acks=0` vs `acks=1` vs `acks=all`?
- `0`: no ack, fastest, can lose data.
- `1`: leader ack only, can lose if leader dies before replication.
- `all`: leader + all ISR, safest.

### Q13: What is the role of ZooKeeper? Is it still required?
ZooKeeper stored cluster metadata (brokers, topics, ACLs, leader election). **Kafka 2.8+ supports KRaft mode**, which removes the ZooKeeper dependency. Kafka 4.0 removes ZooKeeper entirely.

### Q14: How do you handle a poison pill (bad message)?
- Wrap deserialization in try/catch.
- Send bad messages to a **Dead Letter Queue (DLQ)** topic.
- Log + skip + monitor.

### Q15: How is Kafka different from a message queue?

| | Queue (RabbitMQ) | Kafka |
|---|---|---|
| Storage | Deleted after ack | Retained for time/size |
| Consumers | Compete for messages | Each group reads independently |
| Replay | No | Yes |
| Throughput | Medium | Very high |
| Ordering | Per queue | Per partition |

### Q16: What is back-pressure handling in Kafka?
Kafka consumers **pull** (not push), so consumers control rate. If a consumer is slow, lag grows. Monitor **consumer lag** (`kafka-consumer-groups.sh --describe`).

### Q17: How do you scale a Kafka consumer?
Add more consumers to the same group, up to the partition count. To go beyond, increase partitions.

### Q18: What is idempotent producer?
Producer assigns a sequence number per message. Broker dedupes retries with the same sequence number → no duplicates from retries.

### Q19: Difference between Kafka Streams and Kafka Consumer?
- **Consumer**: low-level, you handle everything.
- **Kafka Streams**: high-level DSL for stateful processing (joins, aggregations, windows) with built-in fault tolerance.

### Q20: How do you monitor Kafka?
- **Consumer lag** (most important).
- Broker metrics: under-replicated partitions, request latency.
- Tools: Prometheus + Grafana, Confluent Control Center, Burrow.

---

## 13. Common Gotchas (Senior-level talking points)

1. **You can increase partitions but not decrease** — plan ahead.
2. **Adding partitions breaks ordering for existing keys** (rehashes).
3. **Auto-commit can lose messages** — use manual commit after processing.
4. **Large messages** (>1MB) hurt throughput — store in S3, send pointer.
5. **Too many partitions** hurt failover time and memory.
6. **Consumer lag** is the #1 metric to watch in production.

---

## 14. 1-Day Crash Plan (Before Interview)

| Time | What |
|------|------|
| 30 min | Read sections 1–4 above |
| 30 min | Run Kafka in Docker, create a topic, produce/consume via CLI |
| 1 hr | Write a small producer + consumer in your language |
| 1 hr | Memorize all 20 interview Q&As |
| 30 min | Read about consumer groups + rebalancing deeply |
| 30 min | Practice explaining: partition, offset, replication, ISR, acks |

---

## 15. One-Line Summary You Can Say in an Interview

> "Kafka is a distributed, partitioned, replicated commit log. Producers append events to partitions of a topic; consumers read at their own pace using offsets. Partitions enable parallelism, replication enables fault tolerance, and retention enables replay — that's why it's the backbone of modern event-driven systems."
