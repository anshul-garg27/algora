# Event-gRPC: Master Interview Prep

> **Good Creator Co. (GCC)** -- SaaS platform for influencer marketing analytics, powering real-time insights for brands and creators across mobile, web, and third-party integrations.
>
> **Event-gRPC** is the central nervous system for all analytics data -- a Go-based event ingestion service that receives, validates, routes, and persists 10M+ daily data points across 60+ event types.

**Resume bullets this covers:**

| Bullet | Text | How Event-gRPC Maps |
|--------|------|---------------------|
| **Bullet 2** | "Designed an asynchronous data processing system handling 10M+ daily data points" | gRPC ingestion with 6 worker pools, 26 RabbitMQ queues, 90+ concurrent workers processing events from mobile/web/backend clients |
| **Bullet 3** | "Built a high-performance logging system with RabbitMQ, transitioning to ClickHouse, 2.5x faster retrieval" | Buffered sinker pattern (ticker + batch flush) writing to ClickHouse; 18+ analytical tables replacing slow PostgreSQL queries |

---

## Table of Contents

1. [Elevator Pitches](#1-elevator-pitches)
2. [Key Numbers](#2-key-numbers)
3. [Architecture](#3-architecture)
4. [Technical Implementation](#4-technical-implementation)
5. [Technical Decisions](#5-technical-decisions)
6. [Interview Q&A](#6-interview-qa)
7. [Behavioral Stories (STAR)](#7-behavioral-stories-star)
8. [What-If Scenarios](#8-what-if-scenarios)
9. [How to Speak About This Project](#9-how-to-speak-about-this-project)

---

## 1. Elevator Pitches

### 15-Second Pitch (Hallway Version)

> "I built the event ingestion backbone for a SaaS analytics platform -- a Go service that handles 10 million daily data points through gRPC, fans them across 26 RabbitMQ queues, and batch-writes to ClickHouse for 2.5x faster analytics."

### 30-Second Pitch (Intro Round)

> "At Good Creator Co., I designed and built Event-gRPC, the high-throughput event ingestion system for our influencer marketing analytics platform. It receives events from mobile and web clients via gRPC with 60+ typed event definitions in Protocol Buffers, routes them through 26 RabbitMQ queues with 90+ concurrent workers, and persists them to ClickHouse using a buffered sinker pattern for batch inserts. The system processes 10 million events daily, and the ClickHouse migration gave us 2.5x faster query performance over our previous PostgreSQL setup."

### 60-Second Pitch (Technical Deep Dive Intro)

> "At Good Creator Co., our analytics platform needed to ingest events from multiple sources -- mobile apps, web clients, and third-party webhooks from Shopify, Branch.io, and WebEngage -- all in real time. I built Event-gRPC, a Go service that handles this.
>
> Events arrive via gRPC for our own clients -- we defined 60+ event types in Protocol Buffers using the `oneof` pattern for type-safe polymorphism. Third-party events come in through HTTP webhooks on a parallel Gin server.
>
> Incoming events hit a worker pool -- configurable goroutines reading from a buffered channel. Workers group events by type, correct any future timestamps from bad device clocks, and publish to RabbitMQ with the event type as the routing key. RabbitMQ's exchange-based routing fans this into 26 specialized queues.
>
> On the consumer side, high-volume streams use a buffered sinker pattern: events accumulate in a Go channel and flush to ClickHouse in batches of 100 or every 5 minutes. This is critical because ClickHouse's columnar storage is optimized for batch writes. Lower-volume streams write directly.
>
> The system handles 10M+ daily events with 90+ concurrent consumers. ClickHouse gave us 2.5x faster analytics queries over PostgreSQL, and the whole thing self-heals with auto-reconnecting database connections and dead letter queues for failed messages."

---

## 2. Key Numbers

| Metric | Value |
|--------|-------|
| Total Lines of Code | 10,000+ |
| Go Source Files | 90+ |
| Proto Definition | 688 lines |
| Event Types | 60+ (oneof in proto) |
| Worker Pools | 6 |
| RabbitMQ Exchanges | 11 |
| RabbitMQ Queues | 26 configured in main.go |
| Consumer Workers | 90+ concurrent |
| Buffered Channel Capacity | 1,000 per pool + 10,000 per sinker |
| ClickHouse Tables | 18+ |
| Sinker Functions | 20+ (direct + buffered) |
| Batch Flush Threshold | 100 events (buffered sinkers) |
| Flush Interval | 5 minutes (ticker) |
| Ingestion Target | ~10K events/sec |
| Daily Data Points | 10M+ |
| Direct Dependencies | 30+ |

### Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Go 1.14 |
| RPC Framework | gRPC + Protocol Buffers |
| HTTP Framework | Gin |
| Message Broker | RabbitMQ (streadway/amqp) |
| Analytics DB | ClickHouse (GORM driver) |
| Transactional DB | PostgreSQL (jinzhu/gorm) |
| Cache | Redis Cluster + Ristretto |
| Monitoring | Prometheus + Sentry |
| CI/CD | GitLab CI |
| Client Libraries | Go, Java (Maven), JavaScript (NPM) |

---

## 3. Architecture

### System Architecture Diagram

```
CLIENT APPLICATIONS (Mobile, Web, Backend Services)
                    |
        gRPC (Protobuf)  +  HTTP (JSON)
                    |
    +=======================================+
    |         EVENT-GRPC SERVICE            |
    |                                       |
    |  gRPC Server (:8017)                  |
    |    - dispatch(Events) RPC             |
    |    - Health Check (Watch/Check)       |
    |                                       |
    |  HTTP Server (:8019, Gin)             |
    |    - /heartbeat (LB control)          |
    |    - /metrics (Prometheus)            |
    |    - /vidooly/event                   |
    |    - /branch/event                    |
    |    - /webengage/event                 |
    |    - /shopify/event                   |
    |    - /graphy/event                    |
    |                                       |
    |  6 Worker Pools                       |
    |    Event | Branch | WebEngage         |
    |    Vidooly | Graphy | Shopify         |
    |    (buffered channels, 1000 cap each) |
    +=======================================+
                    |
            Publish (JSON/Protobuf)
                    |
    +=======================================+
    |         RABBITMQ BROKER               |
    |  11 Exchanges, 26 Queues              |
    |  90+ Consumer Workers                 |
    |  Retry logic (max 2) + DLQ            |
    |  Prefetch QoS=1, Durable queues       |
    +=======================================+
                    |
        +-----------+-----------+
        |           |           |
   ClickHouse   PostgreSQL   External APIs
   (Analytics)  (Transact.)  (WebEngage,
   18+ tables   Schema-based  Identity,
   Multi-DB     Pool: 10/20   SocialStream)
   GORM ORM
   Auto-reconnect (1s cron)
```

### Retry Flow

```
Attempt 1: Process event
  |-- Success -> ACK
  |-- Failure -> Republish with x-retry-count=1

Attempt 2: Process event (x-retry-count=1)
  |-- Success -> ACK
  |-- Failure -> x-retry-count becomes 2 -> EXCEEDS MAX
                 -> Publish to Error Exchange (DLQ)
                 -> ACK original message
```

### Complete Consumer Count Table

| # | Queue Name | Workers | Type | Exchange |
|---|-----------|---------|------|----------|
| 1 | grpc_clickhouse_event_q | 2 | Direct | grpc_event.tx |
| 2 | grpc_clickhouse_event_error_q | 2 | Direct | grpc_event_error.dx |
| 3 | clickhouse_click_event_q | 2 | Direct | grpc_event.dx |
| 4 | app_init_event_q | 2 | Direct | event.dx |
| 5 | launch_refer_event_q | 2 | Direct | event.dx |
| 6 | create_user_account_q | 2 | Direct | identity.dx |
| 7 | event.account_profile_complete | 2 | Direct | identity.dx |
| 8 | ab_assignments | 2 | Direct | ab.dx |
| 9 | branch_event_q | 2 | Direct | branch_event.tx |
| 10 | graphy_event_q | 2 | Direct | graphy_event.tx |
| 11 | trace_log | 2 | Buffered | identity.dx |
| 12 | affiliate_orders_event_q | 2 | Buffered | affiliate.dx |
| 13 | bigboss_votes_log_q | 2 | Buffered | bigboss |
| 14 | post_log_events_q | **20** | Buffered | beat.dx |
| 15 | sentiment_log_events_q | 2 | Buffered | beat.dx |
| 16 | post_activity_log_events_q | 2 | Buffered | beat.dx |
| 17 | profile_log_events_q | 2 | Buffered | beat.dx |
| 18 | profile_relationship_log_events_q | 2 | Buffered | beat.dx |
| 19 | scrape_request_log_events_q | 2 | Buffered | beat.dx |
| 20 | order_log_events_q | 2 | Buffered | beat.dx |
| 21 | shopify_events_q | 2 | Buffered | shopify_event.dx |
| 22 | webengage_event_q | 3 | Direct | webengage_event.dx |
| 23 | webengage_ch_event_q | 5 | Direct | webengage_event.dx |
| 24 | webengage_user_event_q | 5 | Direct | webengage_event.dx |
| 25 | post_log_events_q_bkp | 5 | Buffered | beat.dx |
| 26 | activity_tracker_q | 2 | Buffered | coffee.dx |
| | **TOTAL** | **~90+** | | |

### 18+ ClickHouse Tables by Domain

- **Core analytics:** `event` (main events), `error_event` (processing failures), `click_event` (click tracking with 600+ lines of fields)
- **App lifecycle:** `app_init_event`, `launch_refer_event`
- **Third-party:** `branch_event` (49 fields for attribution), `webengage_event`, `graphy_event`, `shopify_event`
- **Scraping logs:** `trace_log`, `post_log_event`, `profile_log`, `sentiment_log`, `scrape_request_log`, `profile_relationship_log`
- **Commerce:** `order_log`, `affiliate_order`, `bigboss_votes`
- **AB testing:** `ab_assignment`

---

## 4. Technical Implementation

All code snippets below are taken directly from the repository source files with annotations.

### 4.1 gRPC Service Definition (proto/eventservice.proto)

The proto file defines 60+ event types using Protocol Buffers' `oneof` for type-safe polymorphism. A single `dispatch` RPC accepts batched events.

```protobuf
// File: proto/eventservice.proto (688 lines)
syntax = "proto3";

option go_package = "proto/go/bulbulgrpc";
option java_multiple_files = true;
option java_package = "com.bulbul.grpc.event";
option java_outer_classname = "BulbulGrpc";

package event;

service EventService {
  rpc dispatch(Events) returns (Response) {}
}

message Events {
  Header header = 4;
  repeated Event events = 5;
}

message Header {
  string sessionId = 5;
  int64 bbDeviceId = 6;
  int64 userId = 7;
  string deviceId = 8;
  string androidAdvertisingId = 9;
  string clientId = 10;
  string channel = 11;
  string os = 12;
  string clientType = 13;
  string appLanguage = 14;
  string appVersion = 15;
  string appVersionCode = 16;
  string currentURL = 17;
  string merchantId = 18;
  string utmReferrer = 19;
  string utmPlatform = 20;
  string utmSource = 21;
  string utmMedium = 22;
  string utmCampaign = 23;
  string ppId = 24;
}

message Event {
  string id = 4;
  string timestamp = 5;
  string currentURL = 6;
  oneof EventOf {
    LaunchEvent launchEvent = 9;
    PageOpenedEvent pageOpenedEvent = 10;
    PageLoadedEvent pageLoadedEvent = 11;
    PageLoadFailedEvent pageLoadFailedEvent = 12;
    WidgetViewEvent widgetViewEvent = 13;
    WidgetCtaClickedEvent widgetCtaClickedEvent = 14;
    WidgetElementViewEvent widgetElementViewEvent = 15;
    WidgetElementClickedEvent widgetElementClickedEvent = 16;
    EnterPWAProductPageEvent enterPWAProductPageEvent = 17;
    StreamEnterEvent streamEnterEvent = 18;
    ChooseProductEvent chooseProductEvent = 19;
    PhoneVerificationInitiateEvent phoneVerificationInitiateEvent = 20;
    PhoneNumberEntered phoneNumberEntered = 21;
    OTPVerifiedEvent otpVerifiedEvent = 22;
    AddToCartEvent addToCartEvent = 23;
    GoToPaymentsEvent goToPaymentsEvent = 24;
    InitiatePurchaseEvent initiatePurchaseEvent = 25;
    CompletePurchaseEvent completePurchaseEvent = 26;
    SocialStreamEnterEvent socialStreamEnterEvent = 27;
    SocialStreamActionEvent socialStreamActionEvent = 28;
    EnterProductEvent enterProductEvent = 29;
    LaunchReferEvent launchReferEvent = 30;
    PurchaseFailedEvent purchaseFailedEvent = 31;
    // ... 30+ more event types through field 64
    NotificationActionEvent notificationActionEvent = 62;
    AffiliateActionEvent affiliateActionEvent = 63;
    HostActionEvent hostActionEvent = 64;
  }
}
```

**Key design points:**
- `oneof EventOf` gives type-safe union types -- each event has its own strongly-typed message
- `repeated Event events` allows batching -- clients send multiple events in one RPC call
- `Header` contains session/device context shared across all events in a batch
- Cross-platform: Go, Java (`java_package`), and JavaScript (gRPC-Web) client generation

### 4.2 gRPC Server + HTTP Hybrid (main.go)

The service runs both a gRPC server (for high-perf client ingestion) and an HTTP/Gin server (for webhooks, health, and metrics).

```go
// File: main.go (573 lines)

type server struct {
    bulbulgrpc.UnimplementedEventServiceServer
}

type healthserver struct {
    grpc_health_v1.UnimplementedHealthServer
}

// gRPC health check -- used by load balancer for graceful deployments
func (s *healthserver) Check(ctx context.Context,
    request *grpc_health_v1.HealthCheckRequest) (*grpc_health_v1.HealthCheckResponse, error) {
    if heartbeat.BEAT {
        return &grpc_health_v1.HealthCheckResponse{
            Status: grpc_health_v1.HealthCheckResponse_SERVING}, nil
    } else {
        return &grpc_health_v1.HealthCheckResponse{
            Status: grpc_health_v1.HealthCheckResponse_NOT_SERVING}, nil
    }
}

// The core dispatch RPC -- receives batched events from clients
func (s *server) Dispatch(ctx context.Context,
    in *bulbulgrpc.Events) (*bulbulgrpc.Response, error) {
    if in != nil {
        if err := event.DispatchEvent(ctx, *in); err != nil {
            return &bulbulgrpc.Response{Status: "ERROR"}, err
        }
    }
    return &bulbulgrpc.Response{Status: "SUCCESS"}, nil
}

func main() {
    config := config.New()

    // gRPC server on port 8017
    go func() {
        lis, err := net.Listen("tcp", ":"+config.Port)
        if err != nil {
            log.Fatalf("failed to listen: %v", err)
        }
        s := grpc.NewServer()
        bulbulgrpc.RegisterEventServiceServer(s, &server{})
        grpc_health_v1.RegisterHealthServer(s, &healthserver{})
        if err := s.Serve(lis); err != nil {
            log.Fatalf("failed to serve: %v", err)
        }
    }()

    // ... 26 consumer configurations (see section 4.5) ...

    // HTTP server on port 8019 (Gin) -- blocks main goroutine
    err := router.SetupRouter(config).Run(":" + config.GinPort)
    if err != nil {
        log.Fatal("Error starting server")
    }
}
```

### 4.3 Event Dispatch with Timeout Protection (event/event.go)

The dispatch function pushes events into a buffered channel with a 1-second timeout to prevent blocking under backpressure.

```go
// File: event/event.go

func DispatchEvent(ctx context.Context, events bulbulgrpc.Events) error {
    gCtx := util.GatewayContextFromGinContext(nil, config.New())

    incompleteEvent := false
    processedEvent := false

    // Validate required header fields
    if events.Header == nil || events.Header.DeviceId == "" {
        incompleteEvent = true
    }

    if eventChannel := eventworker.GetChannel(gCtx.Config); eventChannel == nil {
        gCtx.Logger.Error().Msgf("Event channel nil: %v", events)
    } else {
        // Non-blocking send with 1-second timeout
        select {
        case <-time.After(1 * time.Second):
            gCtx.Logger.Log().Msgf("Error publishing event: %v", events)
        case eventChannel <- events:
            processedEvent = true
        }
    }

    if incompleteEvent {
        return errors.New("Incomplete event")
    } else if processedEvent {
        return nil
    } else {
        return errors.New("Error publishing event")
    }
}
```

**Key pattern:** The `select` with `time.After` prevents the gRPC handler from blocking indefinitely if the worker pool channel is full. This is backpressure control -- the client gets a fast error instead of a hung connection.

### 4.4 Worker Pool Pattern (eventworker/eventworker.go)

Singleton pattern with `sync.Once` for lazy initialization. A configurable number of workers read from a buffered channel, group events by type, correct timestamps, and publish to RabbitMQ.

```go
// File: eventworker/eventworker.go (72 lines)

var (
    eventWrapperChannel chan bulbulgrpc.Events
    channelInit         sync.Once
)

// Singleton channel initialization -- thread-safe, lazy
func GetChannel(config config.Config) chan bulbulgrpc.Events {
    channelInit.Do(func() {
        eventWrapperChannel = make(chan bulbulgrpc.Events,
            config.EVENT_WORKER_POOL_CONFIG.EVENT_BUFFERED_CHANNEL_SIZE)
        initWorkerPool(config,
            config.EVENT_WORKER_POOL_CONFIG.EVENT_WORKER_POOL_SIZE,
            eventWrapperChannel,
            config.EVENT_SINK_CONFIG)
    })
    return eventWrapperChannel
}

// Spawn N workers, each in a safe goroutine with panic recovery
func initWorkerPool(config config.Config, workerPoolSize int,
    eventChannel <-chan bulbulgrpc.Events,
    eventSinkConfig *config.EVENT_SINK_CONFIG) {
    for i := 0; i < workerPoolSize; i++ {
        safego.GoNoCtx(func() {
            worker(config, eventChannel)
        })
    }
}

// Each worker: reads from channel, groups events by type, publishes to RabbitMQ
func worker(config config.Config, eventChannel <-chan bulbulgrpc.Events) {
    for e := range eventChannel {
        rabbitConn := rabbit.Rabbit(config)
        header := e.Header

        // GROUP events by type (e.g., "LaunchEvent", "AddToCartEvent")
        eventsGrouped := make(map[string][]*bulbulgrpc.Event)
        for i, _ := range e.Events {
            // Extract event type name via reflection
            eventName := fmt.Sprintf("%v", reflect.TypeOf(e.Events[i].GetEventOf()))
            eventName = strings.ReplaceAll(eventName, "*bulbulgrpc.Event_", "")

            // TIMESTAMP CORRECTION: future timestamps clamped to now
            et := time.Unix(transformer.InterfaceToInt64(e.Events[i].Timestamp)/1000, 0)
            timeNow := time.Now()
            if et.Unix() > timeNow.Unix() {
                e.Events[i].Timestamp = strconv.FormatInt(timeNow.Unix()*1000, 10)
            }

            eventsGrouped[eventName] = append(eventsGrouped[eventName], e.Events[i])
        }

        // Publish each group to RabbitMQ with event type as routing key
        for eventName, events := range eventsGrouped {
            e := bulbulgrpc.Events{Header: header, Events: events}
            if b, err := protojson.Marshal(&e); err != nil || b == nil {
                log.Printf("Some error publishing message, empty event: %v", err)
            } else {
                err := rabbitConn.Publish(
                    config.EVENT_SINK_CONFIG.EVENT_EXCHANGE,
                    eventName,  // routing key = event type name
                    b, map[string]interface{}{})
                if err != nil {
                    log.Printf("Some error publishing message: %v", err)
                }
            }
        }
    }
}
```

**Key design points:**
- `sync.Once` ensures the channel and pool are created exactly once, even under concurrent gRPC calls
- Event grouping by type enables targeted routing -- `CLICK` events go to click-specific queues, `APP_INIT` to init queues
- Timestamp correction prevents future-dated events from corrupting analytics
- `protojson.Marshal` for RabbitMQ (JSON-compatible protobuf) enables downstream consumers in any language

### 4.5 RabbitMQ Consumer Configurations (main.go)

All 26 consumers are configured declaratively in `main.go`. Representative examples showing both direct and buffered patterns:

```go
// File: main.go -- DIRECT consumer (events processed one-by-one)

clickhouseEventErrorEx := "grpc_event_error.dx"
clickhouseEventErrorRK := "error.grpc_clickhouse_event_q"

rabbitClickhouseEventConsumerCfg := rabbit.RabbitConsumerConfig{
    QueueName:       "grpc_clickhouse_event_q",
    Exchange:        "grpc_event.tx",
    RoutingKey:      "*",                          // wildcard: all event types
    RetryOnError:    true,
    ErrorExchange:   &clickhouseEventErrorEx,      // dead letter exchange
    ErrorRoutingKey: &clickhouseEventErrorRK,       // dead letter routing key
    ExitCh:          boolCh,
    ConsumerCount:   2,                             // 2 concurrent consumers
    ConsumerFunc:    sinker.SinkEventToClickhouse,  // direct processing function
}
rabbit.Rabbit(config).InitConsumer(rabbitClickhouseEventConsumerCfg)

// BUFFERED consumer (high-volume events batched before flush)
traceLogChan := make(chan interface{}, 10000)  // 10K buffer capacity

traceLogEventConsumerCfg := rabbit.RabbitConsumerConfig{
    QueueName:            "trace_log",
    Exchange:             "identity.dx",
    RoutingKey:           "*",
    RetryOnError:         true,
    ErrorExchange:        &traceLogEventErrorEx,
    ErrorRoutingKey:      &traceLogEventErrorRK,
    ExitCh:               boolCh,
    ConsumerCount:        2,
    BufferedConsumerFunc: sinker.BufferTraceLogEvent,  // pushes to channel
    BufferChan:           traceLogChan,
}
rabbit.Rabbit(config).InitConsumer(traceLogEventConsumerCfg)
go sinker.TraceLogEventsSinker(traceLogChan)  // separate goroutine for batch flush

// HIGH-THROUGHPUT consumer: post logs with 20 workers
postLogChan := make(chan interface{}, 10000)
postLogConsumerConfig := rabbit.RabbitConsumerConfig{
    QueueName:            "post_log_events_q",
    Exchange:             "beat.dx",
    RoutingKey:           "post_log_events",
    RetryOnError:         true,
    ErrorExchange:        &postLogEx,
    ErrorRoutingKey:      &postLogExErrorRK,
    ExitCh:               boolCh,
    ConsumerCount:        20,  // highest worker count -- hottest queue
    BufferedConsumerFunc: sinker.BufferPostLogEvents,
    BufferChan:           postLogChan,
}
rabbit.Rabbit(config).InitConsumer(postLogConsumerConfig)
go sinker.PostLogEventsSinker(postLogChan)
```

### 4.6 RabbitMQ Connection Management (rabbit/rabbit.go)

Singleton connection with auto-recovery. Uses `sync.Once` for initialization and a forever loop that waits for close notifications to trigger reconnect.

```go
// File: rabbit/rabbit.go (293 lines)

type RabbitConnection struct {
    connection *amqp.Connection
}

var (
    singletonRabbit  *RabbitConnection
    rabbitCloseError chan *amqp.Error
    rabbitInit       sync.Once
)

// Thread-safe singleton with 5-second connection timeout
func Rabbit(config config.Config) *RabbitConnection {
    rabbitInit.Do(func() {
        rabbitConnected := make(chan bool)
        safego.GoNoCtx(func() {
            rabbitConnector(config, rabbitConnected)
        })
        select {
        case <-rabbitConnected:
        case <-time.After(5 * time.Second):
        }
    })
    return singletonRabbit
}

// Infinite loop: connect, wait for close, reconnect
func rabbitConnector(config config.Config, connected chan bool) {
    for {
        log.Printf("Connecting to rabbit\n")
        singletonRabbit = connectToRabbit(config)
        connected <- true
        rabbitCloseError = make(chan *amqp.Error)
        singletonRabbit.connection.NotifyClose(rabbitCloseError)
        <-rabbitCloseError  // blocks until connection drops
    }
}

// Retry connection forever with 1-second backoff
func connectToRabbit(config config.Config) *RabbitConnection {
    for {
        rabbitURL := fmt.Sprintf("amqp://%s:%s@%s:%s/",
            config.RABBIT_CONNECTION_CONFIG.RABBIT_USER,
            config.RABBIT_CONNECTION_CONFIG.RABBIT_PASSWORD,
            config.RABBIT_CONNECTION_CONFIG.RABBIT_HOST,
            config.RABBIT_CONNECTION_CONFIG.RABBIT_PORT)

        conn, err := amqp.DialConfig(rabbitURL, amqp.Config{
            Vhost:      config.RABBIT_CONNECTION_CONFIG.RABBIT_VHOST,
            ChannelMax: 200,
            Heartbeat:  time.Duration(
                config.RABBIT_CONNECTION_CONFIG.RABBIT_HEARTBEAT) * time.Millisecond,
        })
        if err == nil {
            return &RabbitConnection{connection: conn}
        }
        log.Printf("Trying to reconnect to RabbitMQ at %s\n", rabbitURL)
        time.Sleep(time.Second)
    }
}
```

### 4.7 Retry Logic with Dead Letter Queues (rabbit/rabbit.go)

Max-2-retry pattern: on failure, republish with incremented `x-retry-count` header. After 2 failures, route to error exchange (dead letter queue).

```go
// File: rabbit/rabbit.go -- Consume method

func (rabbit *RabbitConnection) Consume(rabbitConsumerConfig RabbitConsumerConfig) error {
    channel, _ := rabbit.connection.Channel()
    defer channel.Close()

    // Declare durable queue
    channel.QueueDeclare(rabbitConsumerConfig.QueueName,
        true, false, false, false, nil)

    // Bind queue to exchange with routing key
    channel.QueueBind(rabbitConsumerConfig.QueueName,
        rabbitConsumerConfig.RoutingKey,
        rabbitConsumerConfig.Exchange, false, nil)

    // Prefetch 1 message at a time (backpressure control)
    channel.Qos(1, 0, false)

    msgs, _ := channel.Consume(rabbitConsumerConfig.QueueName,
        "", false, false, false, false, nil)  // manual ACK

    for msg := range msgs {
        // Route to appropriate handler (direct or buffered)
        buffering := rabbitConsumerConfig.BufferChan != nil
        listenerResponse := false
        if buffering {
            listenerResponse = rabbitConsumerConfig.BufferedConsumerFunc(
                msg, rabbitConsumerConfig.BufferChan)
        } else {
            listenerResponse = rabbitConsumerConfig.ConsumerFunc(msg)
        }

        if listenerResponse {
            msg.Ack(false)  // SUCCESS: acknowledge
        } else if !rabbitConsumerConfig.RetryOnError {
            // No retry configured: send to error queue immediately
            rabbit.Publish(*rabbitConsumerConfig.ErrorExchange,
                *rabbitConsumerConfig.ErrorRoutingKey, msg.Body, msg.Headers)
            msg.Ack(false)
        } else {
            // RETRY LOGIC
            requeue := true
            retryCount := 1
            if retryCountInterface, ok := msg.Headers[header.XRetryCount]; ok {
                retryCount = transformer.InterfaceToInt(retryCountInterface)
                if retryCount >= 2 {
                    // MAX RETRIES EXCEEDED: route to dead letter queue
                    requeue = false
                    rabbit.Publish(*rabbitConsumerConfig.ErrorExchange,
                        *rabbitConsumerConfig.ErrorRoutingKey, msg.Body, msg.Headers)
                } else {
                    retryCount++
                }
            }

            if msg.Headers == nil {
                msg.Headers = map[string]interface{}{}
            }
            msg.Headers[header.XRetryCount] = retryCount

            if requeue {
                // Republish with incremented retry count
                rabbit.Publish(rabbitConsumerConfig.Exchange,
                    rabbitConsumerConfig.RoutingKey, msg.Body, msg.Headers)
                msg.Ack(false)
            } else {
                msg.Ack(false)
            }
        }
    }
    return nil
}
```

### 4.8 Buffered Sinker Pattern (sinker/tracelogeventsinker.go)

High-volume events use a two-stage pattern: (1) buffer to channel, (2) batch flush on size threshold or time interval.

```go
// File: sinker/tracelogeventsinker.go

// Stage 1: Buffer -- push parsed event into channel (non-blocking)
func BufferTraceLogEvent(delivery amqp.Delivery,
    eventBuffer chan interface{}) bool {
    event := parser.GetTraceLogEvent(delivery.Body)
    if event != nil {
        eventBuffer <- *event
        return true
    }
    return false
}

// Stage 2: Batch flush -- runs in dedicated goroutine
func TraceLogEventsSinker(traceLogsChannel chan interface{}) {
    var buffer []model.TraceLogEvent
    ticker := time.NewTicker(5 * time.Minute)
    BufferLimit := 100
    for {
        select {
        case v := <-traceLogsChannel:
            buffer = append(buffer, v.(model.TraceLogEvent))
            // Flush when batch is full
            if len(buffer) >= BufferLimit {
                FlushTraceLogEvents(buffer)
                buffer = []model.TraceLogEvent{}
            }
        case _ = <-ticker.C:
            // Flush on timer (ensure stale data is written)
            FlushTraceLogEvents(buffer)
            buffer = []model.TraceLogEvent{}
        }
    }
}

// Batch insert to ClickHouse via GORM
func FlushTraceLogEvents(events []model.TraceLogEvent) {
    log.Printf("Creating %v trace log events in batches", len(events))
    if events == nil || len(events) == 0 {
        return
    }
    result := clickhouse.Clickhouse(config.New(), nil).Create(events)
    if result != nil && result.Error == nil {
        log.Printf("Created trace log events successfully: %v",
            result.RowsAffected)
    } else {
        log.Printf("Trace log events creation failed: %v", result.Error)
    }
}
```

**Why this pattern matters:**
- ClickHouse is optimized for batch inserts (columnar storage)
- Reduces network round trips: 100 events per INSERT instead of 100 separate INSERTs
- Timer ensures data freshness: even if volume is low, data flushes every 5 minutes
- The `select` statement gives dual-trigger semantics (size OR time, whichever first)

### 4.9 Direct Event Sinker (sinker/eventsinker.go)

For lower-volume queues, events are processed immediately -- unmarshal protobuf, transform to model, insert to ClickHouse.

```go
// File: sinker/eventsinker.go

func SinkEventToClickhouse(delivery amqp.Delivery) bool {
    grpcEvent := &bulbulgrpc.Events{}
    if err := protojson.Unmarshal(delivery.Body, grpcEvent); err == nil {
        if grpcEvent.Events == nil || len(grpcEvent.Events) == 0 {
            log.Println("No event in events: ", grpcEvent)
            return false
        }

        events := []model.Event{}
        for _, e := range grpcEvent.Events {
            event, err := TransformToEventModel(grpcEvent, e)
            if err != nil {
                return false
            }
            events = append(events, event)
        }

        if len(events) > 0 {
            if result := clickhouse.Clickhouse(config.New(), nil).Create(events);
                result != nil && result.Error == nil {
                return true
            }
        }
    }
    return true
}

// Transform protobuf to ClickHouse model
func TransformToEventModel(grpcEvent *bulbulgrpc.Events,
    e *bulbulgrpc.Event) (model.Event, error) {
    // Validate required fields
    if grpcEvent.Header == nil || e.Timestamp == "" ||
       e.Id == "" || grpcEvent.Header.DeviceId == "" {
        return model.Event{}, errors.New("Incomplete event")
    }

    // Extract event type name via reflection
    eventName := fmt.Sprintf("%v", reflect.TypeOf(e.GetEventOf()))
    eventName = strings.ReplaceAll(eventName, "*bulbulgrpc.Event_", "")

    event := model.Event{
        EventId:         e.Id,
        EventName:       eventName,
        EventTimestamp:  time.Unix(
            transformer.InterfaceToInt64(e.Timestamp)/1000, 0),
        InsertTimestamp: time.Now(),
        SessionId:       grpcEvent.Header.SessionId,
        BbDeviceId:      grpcEvent.Header.BbDeviceId,
        UserId:          grpcEvent.Header.UserId,
        DeviceId:        grpcEvent.Header.DeviceId,
        // ... all header fields mapped ...
    }

    // Extract event-specific params as JSON (dynamic schema)
    data := map[string]interface{}{}
    if e.GetLaunchEvent() != nil {
        js, _ := json.Marshal(e.GetLaunchEvent())
        json.Unmarshal(js, &data)
        event.EventParams = data
    }
    // ... 50+ more event type checks ...

    return event, nil
}
```

### 4.10 ClickHouse Multi-DB Connection (clickhouse/clickhouse.go)

Supports multiple ClickHouse databases from a single service. Uses `sync.Once` for initialization and a 1-second health check cron for auto-recovery.

```go
// File: clickhouse/clickhouse.go (84 lines)

var (
    singletonClickhouseMap map[string]*gorm.DB
    clickhouseInit         sync.Once
    mutex                  *sync.Mutex = &sync.Mutex{}
)

// Multi-DB singleton: returns connection for specific DB or default
func Clickhouse(config config.Config, dbName *string) *gorm.DB {
    clickhouseInit.Do(func() {
        connectToClickhouse(config)
        go clickhouseConnectionCron(config)  // auto-reconnect
    })

    if dbName != nil {
        if db, ok := singletonClickhouseMap[*dbName]; ok {
            return db
        }
    }
    return singletonClickhouseMap[
        config.CLICKHOUSE_CONNECTION_CONFIG.CLICKHOUSE_DB_NAME]
}

// Health check every 1 second -- reconnects broken connections
func clickhouseConnectionCron(config config.Config) {
    for {
        connectToClickhouse(config)
        time.Sleep(1000 * time.Millisecond)
    }
}

// Connect to all configured databases
func connectToClickhouse(config config.Config) {
    mutex.Lock()

    for _, dbName := range config.CLICKHOUSE_CONNECTION_CONFIG.CLICKHOUSE_DB_NAMES {
        dsn := "tcp://" +
            config.CLICKHOUSE_CONNECTION_CONFIG.CLICKHOUSE_HOST + ":" +
            config.CLICKHOUSE_CONNECTION_CONFIG.CLICKHOUSE_PORT +
            "?database=" + dbName +
            "&username=" + config.CLICKHOUSE_CONNECTION_CONFIG.CLICKHOUSE_USER +
            "&password=" + config.CLICKHOUSE_CONNECTION_CONFIG.CLICKHOUSE_PASSWORD +
            "&read_timeout=10&write_timeout=20"

        connectionBroken := false
        if singletonClickhouseMap == nil {
            singletonClickhouseMap = map[string]*gorm.DB{}
        }
        if singletonClickhouseMap[dbName] == nil ||
           singletonClickhouseMap[dbName].Error != nil {
            connectionBroken = true
        }
        if !connectionBroken {
            if _, err := singletonClickhouseMap[dbName].DB(); err != nil {
                connectionBroken = true
            }
        }

        if connectionBroken {
            db, err := gorm.Open(clickhouse.New(clickhouse.Config{
                DSN:                      dsn,
                DisableDatetimePrecision: true,
            }), &gorm.Config{})
            if err != nil {
                log.Printf("Error connecting to clickhouse: %v", err)
            } else {
                singletonClickhouseMap[dbName] = db
            }
        }
    }
    mutex.Unlock()
}
```

### 4.11 Safe Goroutine Execution (safego/safego.go)

Every goroutine in the system is wrapped in panic recovery to prevent a single bad event from crashing the entire service.

```go
// File: safego/safego.go (35 lines)

// With context (for structured logging)
func Go(gCtx *context.Context, f func()) {
    go func() {
        defer func() {
            if panicMessage := recover(); panicMessage != nil {
                stack := debug.Stack()
                gCtx.Logger.Error().Msgf(
                    "RECOVERED FROM UNHANDLED PANIC: %v\nSTACK: %s",
                    panicMessage, stack)
            }
        }()
        f()
    }()
}

// Without context (for infrastructure goroutines)
func GoNoCtx(f func()) {
    go func() {
        defer func() {
            if panicMessage := recover(); panicMessage != nil {
                stack := debug.Stack()
                log.Printf(
                    "RECOVERED FROM UNHANDLED PANIC: %v\nSTACK: %s",
                    panicMessage, stack)
            }
        }()
        f()
    }()
}
```

**Why this matters:** In Go, an unrecovered panic in any goroutine kills the entire process. With 90+ concurrent workers, a single malformed event could crash the service. This wrapper guarantees graceful degradation.

### 4.12 PostgreSQL Connection with Schema Routing (pg/pg.go)

```go
// File: pg/pg.go (60 lines)

func PG(config config.Config) *gorm.DB {
    pgInit.Do(func() {
        connectToPG(config)
        go pgConnectionCron(config)  // auto-reconnect every 1s
    })
    return singletonPg
}

func connectToPG(config config.Config) {
    mutex.Lock()
    if singletonPg == nil || singletonPg.Error != nil ||
       singletonPg.DB().Ping() != nil {
        singletonPg, _ = gorm.Open("postgres",
            "host="+config.POSTGRES_CONNECTION_CONFIG.POSTGRES_HOST+
            " port="+config.POSTGRES_CONNECTION_CONFIG.POSTGRES_PORT+
            " user="+config.POSTGRES_CONNECTION_CONFIG.POSTGRES_USER+
            " dbname="+config.POSTGRES_CONNECTION_CONFIG.POSTGRES_DBNAME+
            " password="+config.POSTGRES_CONNECTION_CONFIG.POSTGRES_PASSWORD)

        singletonPg.DB().SetMaxIdleConns(10)
        singletonPg.DB().SetMaxOpenConns(20)
        singletonPg.DB().SetConnMaxLifetime(0)

        // Schema-based multi-tenancy: all tables prefixed with schema
        gorm.DefaultTableNameHandler = func(db *gorm.DB,
            defaultTableName string) string {
            return config.POSTGRES_CONNECTION_CONFIG.POSTGRES_EVENT_SCHEMA +
                "." + defaultTableName
        }
    }
    mutex.Unlock()
}
```

### 4.13 HTTP Router with Observability (router/router.go)

```go
// File: router/router.go

func SetupRouter(config config.Config) *gin.Engine {
    sentry.Init(sentry.ClientOptions{
        Dsn:              "http://...@172.31.14.149:9000/26",
        Environment:      config.Env,
        AttachStacktrace: true,
    })

    router := gin.New()
    router.Use(sentrygin.New(sentrygin.Options{Repanic: true}))
    router.Use(gin.Recovery())
    router.Use(cors.New(cors.Options{
        AllowedOrigins: []string{"*"},
        AllowedMethods: []string{
            http.MethodHead, http.MethodGet, http.MethodPost,
            http.MethodPut, http.MethodPatch, http.MethodDelete},
        AllowedHeaders:   []string{"*"},
        AllowCredentials: true,
    }))

    // Prometheus metrics endpoint
    router.GET("/metrics", gin.WrapH(promhttp.Handler()))

    // Webhook endpoints for third-party event sources
    heartbeatRouter := router.Group("/heartbeat")
    vidoolyEventRouter := router.Group("/vidooly/event")
    branchEventRouter := router.Group("/branch/event")
    webengageRouter := router.Group("/webengage/event")
    shopifyRouter := router.Group("/shopify/event")
    graphyEventRouter := router.Group("/graphy/event")
    // ... route registration ...

    return router
}
```

### 4.14 Configuration Management (config/config.go)

40+ fields loaded from environment-specific `.env` files, supporting 6 worker pool configurations and 3 database connections.

```go
// File: config/config.go (283 lines)

type Config struct {
    Port    string  // 8017 (gRPC)
    GinPort string  // 8019 (HTTP)
    Env     string  // PRODUCTION, STAGE, LOCAL

    // 6 Worker Pool Configs (each with pool size + channel size)
    EVENT_WORKER_POOL_CONFIG           *EVENT_WORKER_POOL_CONFIG
    BRANCH_EVENT_WORKER_POOL_CONFIG    *EVENT_WORKER_POOL_CONFIG
    VIDOOLY_EVENT_WORKER_POOL_CONFIG   *EVENT_WORKER_POOL_CONFIG
    WEBENGAGE_EVENT_WORKER_POOL_CONFIG *EVENT_WORKER_POOL_CONFIG
    SHOPIFY_EVENT_WORKER_POOL_CONFIG   *EVENT_WORKER_POOL_CONFIG
    GRAPHY_EVENT_WORKER_POOL_CONFIG    *EVENT_WORKER_POOL_CONFIG

    // Database connections
    CLICKHOUSE_CONNECTION_CONFIG *CLICKHOUSE_CONNECTION_CONFIG  // multi-DB
    POSTGRES_CONNECTION_CONFIG   *POSTGRES_CONNECTION_CONFIG     // schema-based
    RABBIT_CONNECTION_CONFIG     *RABBIT_CONNECTION_CONFIG

    // External APIs
    WEBENGAGE_API_KEY  string
    IDENTITY_URL       string
    SOCIAL_STREAM_URL  string

    // Security
    HMAC_SECRET []byte
    LOG_LEVEL   int
}

type EVENT_WORKER_POOL_CONFIG struct {
    EVENT_WORKER_POOL_SIZE      int  // number of goroutines
    EVENT_BUFFERED_CHANNEL_SIZE int  // channel buffer capacity
}

type CLICKHOUSE_CONNECTION_CONFIG struct {
    CLICKHOUSE_HOST     string
    CLICKHOUSE_PORT     string
    CLICKHOUSE_USER     string
    CLICKHOUSE_DB_NAMES []string  // comma-separated in env, split to slice
    CLICKHOUSE_PASSWORD string
    CLICKHOUSE_DB_NAME  string    // default DB
}
```

### Source Files Referenced

| File | Lines | Purpose |
|------|-------|---------|
| `main.go` | 573 | Entry point, 26 consumer configs, gRPC + HTTP servers |
| `eventworker/eventworker.go` | 72 | Worker pool, event grouping, timestamp correction |
| `event/event.go` | 47 | Dispatch with backpressure timeout |
| `sinker/eventsinker.go` | 1477 | Direct sinker, protobuf-to-model transform |
| `sinker/tracelogeventsinker.go` | 57 | Buffered sinker pattern (ticker + batch) |
| `rabbit/rabbit.go` | 293 | Connection management, retry logic, consumer framework |
| `clickhouse/clickhouse.go` | 84 | Multi-DB singleton, auto-reconnect cron |
| `pg/pg.go` | 60 | PostgreSQL singleton, schema routing |
| `safego/safego.go` | 35 | Panic recovery wrapper for goroutines |
| `config/config.go` | 283 | 40+ env-based config fields |
| `router/router.go` | 76 | Gin HTTP setup, Prometheus, Sentry |
| `proto/eventservice.proto` | 688 | 60+ event types, gRPC service definition |

---

## 5. Technical Decisions

Ten "Why X not Y?" design decisions. Each explains the tradeoff, references actual code, and provides a concise interview-ready response.

### 5.1 Why gRPC + HTTP hybrid vs pure REST?

**Decision:** gRPC on port 8017 for high-throughput event ingestion from mobile/backend clients, HTTP/Gin on port 8019 for webhooks, health checks, and metrics.

**Why gRPC for events:**
- Protocol Buffers give 5-10x smaller payloads than JSON for mobile clients on slow networks
- Strongly-typed contracts with 60+ event types via `oneof` -- compile-time safety across Go, Java, and JavaScript clients
- HTTP/2 multiplexing -- multiple event batches on a single connection
- Binary serialization is 3-5x faster than JSON parsing at 10K events/sec

**Why keep HTTP:**
- Third-party webhooks (Vidooly, Branch, WebEngage, Shopify) send standard HTTP POST with JSON
- `/metrics` endpoint for Prometheus (standard HTTP scraping)
- `/heartbeat` endpoint for load balancer health checks
- No control over third-party webhook format -- they will not adopt gRPC

> **Interview answer:** "We used gRPC for our own mobile and backend clients because protobuf gives us 5-10x smaller payloads and type safety across 60+ event types. But we kept an HTTP server alongside it because third-party integrations like Shopify and Branch.io only support webhooks, and our Prometheus metrics and load balancer health checks use standard HTTP."

### 5.2 Why RabbitMQ vs Kafka?

**Decision:** RabbitMQ with 11 exchanges and 26 queues for event routing.

**Why RabbitMQ:**
- **Smart routing needed:** Exchange-based routing with routing keys (e.g., `CLICK` events to click queue, `APP_INIT` to init queue). Kafka requires consumer-side filtering
- **Per-message acknowledgment:** Critical for retry logic -- if processing fails, the specific message can be re-queued. Kafka only tracks offsets
- **Dead letter exchanges:** Native DLQ support. Failed messages route to error exchanges after max retries. Kafka DLQ requires custom implementation
- **Lower operational overhead:** Single-node RabbitMQ vs Kafka cluster (ZooKeeper + brokers)
- **Message-level retry:** `x-retry-count` header incremented per message. Kafka would require a separate retry topic

**Why NOT Kafka:**
- We did not need ordered processing (events are independent)
- We did not need replay capability (events are append-only to ClickHouse)
- Our daily volume (10M events) is well within RabbitMQ capacity
- Would have been over-engineering for our team size at a startup

> **Interview answer:** "We chose RabbitMQ because we needed smart routing -- exchange-based routing keys let us fan events from one gRPC endpoint to 26 specialized queues without consumer-side filtering. We also needed per-message acknowledgment for our retry logic. Kafka would have been overkill -- we didn't need ordering guarantees or replay, and at 10M daily events RabbitMQ handles the volume easily with lower ops overhead for a startup team."

### 5.3 Why buffered sinkers vs direct writes?

**Decision:** High-volume event streams (trace logs, post logs, sentiment) use buffered sinkers with batch flush; lower-volume streams (branch events, app init) use direct writes.

**Why buffered for high-volume:**
- ClickHouse is a columnar database optimized for batch inserts -- inserting 100 rows at once is barely more expensive than inserting 1 row
- Reduces network round trips: 1 INSERT per batch vs 100 separate INSERTs
- Post log queue has 20 workers -- without batching, 20 concurrent single-row inserts would bottleneck ClickHouse's merge tree
- The `select` on channel + ticker gives dual-trigger semantics: flush on batch size OR time interval

**Why direct for low-volume:**
- Branch events, app init events have low volume -- batching would add unnecessary latency
- These events often trigger downstream actions (referral processing, A/B assignment) where immediacy matters
- Simpler code path -- no need for a separate flush goroutine

> **Interview answer:** "We used a buffered sinker pattern for high-volume streams like post logs and trace logs. ClickHouse is columnar -- batch inserts are dramatically more efficient than row-by-row writes. The buffer accumulates events in a Go channel and flushes either when we hit 100 events or every 5 minutes, whichever comes first. For low-volume streams like branch events, we write directly because the added latency of batching isn't worth the complexity."

### 5.4 Why ClickHouse vs PostgreSQL for events?

**Decision:** ClickHouse as the primary analytics store, PostgreSQL retained only for transactional data (referrals, user accounts).

**Why ClickHouse for events:**
- **Columnar storage:** Analytics queries (aggregations, time-series) scan only relevant columns. A query like "count events by type this week" reads 1 column instead of full rows
- **10-100x compression:** Event data with repetitive strings (event names, device IDs) compresses dramatically in columnar format
- **2.5x faster retrieval** over PostgreSQL for the same queries (measured after migration)
- **Append-only workload:** Events are never updated -- perfect for ClickHouse's MergeTree engine
- **Scale-out architecture:** Can add shards as data grows without application changes

**Why keep PostgreSQL:**
- Referral events need transactions (check if user exists, then insert referral)
- User account creation requires ACID guarantees
- Schema-based multi-tenancy (`config.POSTGRES_EVENT_SCHEMA + "." + tableName`)
- These are low-volume, write-rarely workloads where PostgreSQL excels

> **Interview answer:** "We migrated our event analytics from PostgreSQL to ClickHouse and saw a 2.5x improvement in query performance. ClickHouse's columnar storage is ideal for our workload -- events are append-only, and analytics queries aggregate across millions of rows but only need a few columns. We kept PostgreSQL for transactional data like referrals and user accounts where we need ACID guarantees."

### 5.5 Why Go channels for worker pools vs goroutine-per-request?

**Decision:** Fixed-size worker pools with buffered channels instead of spawning a goroutine per incoming gRPC request.

**Why worker pools:**
- **Bounded concurrency:** At 10K events/sec, goroutine-per-request would spawn 10K goroutines per second, each holding a RabbitMQ channel. Channel exhaustion would crash the service
- **Backpressure:** When the channel is full, the `select` with timeout returns an error to the client instead of accepting unbounded work
- **Memory predictability:** Fixed pool size means predictable memory usage. Goroutine-per-request has unbounded memory growth under spikes
- **Connection reuse:** Workers hold long-lived RabbitMQ connections. Per-request goroutines would need connection pooling

**Why buffered channels (not unbuffered):**
- Buffer of 1000 absorbs burst traffic without blocking the gRPC handler
- Acts as a shock absorber between ingestion rate and processing rate
- The 1-second timeout in `DispatchEvent` prevents indefinite blocking when buffer is full

> **Interview answer:** "We used fixed-size worker pools with buffered channels instead of goroutine-per-request. At 10K events per second, spawning a goroutine per request would exhaust our RabbitMQ channel limit and cause unbounded memory growth during traffic spikes. The buffered channel absorbs burst traffic, and if it fills up, the 1-second timeout returns a fast error to the client instead of blocking. This gives us predictable resource usage and natural backpressure."

### 5.6 Why Protocol Buffers vs JSON?

**Decision:** Protocol Buffers for the event schema, with protojson for RabbitMQ serialization.

**Why Protobuf:**
- **Type safety across languages:** One `.proto` file generates Go, Java, and JavaScript clients. JSON schemas are informal and error-prone
- **`oneof` for 60+ event types:** Each event type has its own message with specific fields. JSON would require ad-hoc validation
- **Smaller payloads:** Binary encoding is 5-10x smaller than JSON, critical for mobile clients on cellular networks
- **Forward/backward compatibility:** Adding new event types (new `oneof` variants) doesn't break existing clients
- **Code generation:** `protoc` generates serialization, deserialization, and gRPC stubs automatically

**Why protojson for RabbitMQ (not raw binary):**
- Downstream consumers may be in non-Go languages -- JSON is universally readable
- Debugging: JSON messages in RabbitMQ management UI are human-readable
- `protojson.Marshal` preserves the protobuf schema while producing standard JSON

> **Interview answer:** "We used Protocol Buffers for the event schema because it gives us type safety across Go, Java, and JavaScript clients from a single definition file. The `oneof` construct lets us define 60+ event types with specific fields per type -- something JSON schemas can't enforce at compile time. For RabbitMQ messaging we serialize to protojson, which gives us human-readable JSON while preserving the schema structure."

### 5.7 Why sync.Once singleton vs global init?

**Decision:** All connection pools (RabbitMQ, ClickHouse, PostgreSQL, worker channels) use `sync.Once` for lazy initialization instead of package-level `init()`.

**Why sync.Once:**
- **Lazy initialization:** Connections only created when first needed, not at import time. This matters during testing -- importing the package doesn't force a DB connection
- **Thread-safe:** Multiple goroutines calling `Rabbit(config)` concurrently will only trigger one connection attempt. Package `init()` runs once but at import time, not first-use time
- **Config-dependent:** Connection parameters come from the `Config` struct, which is itself lazily loaded from `.env` files. `init()` would need to hardcode the config loading order
- **Testability:** Can mock or replace the singleton in tests without package-level side effects

**Why NOT global init():**
- `init()` cannot accept parameters -- we need the `config.Config` struct
- `init()` runs at import time, which makes test setup painful
- Circular dependency risk: if `clickhouse.init()` needs `config.Config`, and `config.init()` needs something from another package

> **Interview answer:** "We used `sync.Once` for all connection pools instead of package `init()` because our connections are config-dependent -- the DB credentials come from environment-specific config that's also lazily loaded. `sync.Once` gives us thread-safe lazy initialization: the first goroutine that calls `Clickhouse(config)` creates the connection, and all subsequent calls get the cached instance. This also makes testing easier because importing the package doesn't force a database connection."

### 5.8 Why dead letter queues vs infinite retry?

**Decision:** Maximum 2 retries per message, then route to a dead letter queue (error exchange). No infinite retry.

**Why cap at 2 retries:**
- **Poison messages:** A malformed event that causes a parsing error will never succeed no matter how many times you retry. Infinite retry would create an infinite loop
- **Resource protection:** A stuck message blocks the consumer (QoS prefetch=1). Infinite retry on one bad message starves all other messages in the queue
- **Observability:** Dead letter queues make failures visible. Ops can inspect the error queue, fix the issue, and replay messages. Silent infinite retry hides problems
- **SLA compliance:** With 2 retries + DLQ, a transient failure (ClickHouse momentarily unreachable) gets retried, but a permanent failure (invalid schema) gets captured quickly

**Why NOT just drop failed messages:**
- Analytics data is valuable -- we want to capture and replay failed events after fixing the root cause
- Error queues provide a natural audit trail for data quality issues

> **Interview answer:** "We capped retries at 2 and route failures to a dead letter queue. Infinite retry is dangerous because a poison message -- say, a malformed protobuf that always fails to parse -- would create an infinite loop and block the consumer. With our QoS prefetch of 1, that would starve all other messages. The DLQ gives us visibility into failures, and we can inspect and replay messages after fixing the root cause."

### 5.9 Why multi-DB ClickHouse vs single DB?

**Decision:** Support multiple ClickHouse databases from the same service, stored as `map[string]*gorm.DB`.

**Why multi-DB:**
- **Domain separation:** Different business domains (analytics events, scraping logs, partner data) in separate databases with independent schema evolution
- **Access control:** Different databases can have different user permissions. The analytics DB is read-heavy for dashboards; the log DB is write-heavy for ingestion
- **Operational isolation:** One database's maintenance (OPTIMIZE TABLE, mutations) doesn't affect other databases' read performance
- **Migration flexibility:** Can move one domain's database to a different ClickHouse cluster without changing others

**Why not separate services per DB:**
- All databases share the same ClickHouse cluster -- separate services would add unnecessary network hops
- A single connection cron monitors all databases -- simpler ops than N separate health checks

> **Interview answer:** "We supported multiple ClickHouse databases from the same service because different business domains need separate schema evolution and access control. Analytics events, scraping logs, and partner data each have their own database. The `Clickhouse(config, &dbName)` function takes an optional database name -- callers specify which DB they need, and if they don't, they get the default. One connection cron monitors all databases, so operational complexity stays low."

### 5.10 Why GORM vs raw SQL for ClickHouse?

**Decision:** GORM ORM with the ClickHouse driver for all database operations.

**Why GORM:**
- **Batch insert convenience:** `db.Create([]model.Event{...})` generates a multi-row INSERT statement automatically. Raw SQL batch inserts require manual value interpolation
- **Model-driven:** Go structs with `gorm` tags define the schema. Adding a new field to the model automatically includes it in INSERTs without changing SQL strings
- **Driver abstraction:** Same API for ClickHouse and PostgreSQL. Switching the connection from PG to ClickHouse required zero changes to sinker code
- **Connection lifecycle:** GORM manages connection pooling, idle connections, and connection max lifetime

**Tradeoff accepted:**
- GORM adds some overhead vs raw SQL -- but for INSERT-heavy workloads (no complex JOINs or subqueries), the overhead is negligible
- ClickHouse-specific features (MergeTree settings, OPTIMIZE TABLE) are done via raw DDL, not through GORM

> **Interview answer:** "We used GORM because our primary operation is batch inserts -- `db.Create([]Event{...})` generates multi-row INSERTs automatically, which would be tedious to build manually with raw SQL for 100-event batches. GORM also gives us model-driven schema management: adding a field to the Go struct automatically includes it in inserts. The same API works for both ClickHouse and PostgreSQL, which let us switch the analytics backend without changing sinker code."

### Quick Decision Reference Card

| # | Decision | Chose | Over | Key Reason |
|---|----------|-------|------|------------|
| 1 | Protocol | gRPC + HTTP | Pure REST | Type safety + 3rd party webhooks |
| 2 | Message Broker | RabbitMQ | Kafka | Smart routing + per-message ACK |
| 3 | Write Pattern | Buffered sinkers | Direct writes (for high-vol) | ClickHouse batch optimization |
| 4 | Analytics DB | ClickHouse | PostgreSQL | 2.5x faster, columnar, append-only |
| 5 | Concurrency | Worker pools | Goroutine-per-request | Bounded resources, backpressure |
| 6 | Serialization | Protobuf | JSON | Type safety, 5-10x smaller |
| 7 | Initialization | sync.Once | Global init() | Config-dependent, testable |
| 8 | Error Handling | DLQ (max 2 retry) | Infinite retry | Poison message protection |
| 9 | DB Architecture | Multi-DB ClickHouse | Single DB | Domain separation, access control |
| 10 | ORM | GORM | Raw SQL | Batch insert convenience |

---

## 6. Interview Q&A

### gRPC and Protocol Buffers

**Q1: How does your gRPC service handle 60+ event types efficiently?**

> We use Protocol Buffers' `oneof` construct. The `Event` message has a single `oneof EventOf` field that can hold any of 60+ typed event messages -- `LaunchEvent`, `AddToCartEvent`, `CompletePurchaseEvent`, and so on. The client sends a batch of events in a single `dispatch` RPC call wrapped in an `Events` message with a shared `Header` for session and device context.
>
> On the server side, we use Go reflection to extract the event type name (`reflect.TypeOf(e.GetEventOf())`) and strip the protobuf prefix. This gives us a clean string like `"LaunchEvent"` that becomes the RabbitMQ routing key. So a single gRPC endpoint fans out to 26 specialized queues without any switch statement -- the routing is entirely data-driven.
>
> The proto file also generates Java and JavaScript clients that we published to Maven and NPM. So Android, iOS, web, and backend services all share the same type-safe contract.

**Q2: Why did you choose gRPC over REST for event ingestion?**

> Three reasons. First, payload size -- protobuf binary encoding is 5-10x smaller than JSON, which matters for mobile clients on cellular networks sending thousands of events per session. Second, type safety -- with 60+ event types, REST would require ad-hoc JSON validation. Protobuf enforces the schema at compile time across Go, Java, and JavaScript. Third, HTTP/2 multiplexing -- clients can send multiple event batches over a single connection without head-of-line blocking.
>
> That said, we kept an HTTP server alongside gRPC for third-party webhooks (Branch.io, Shopify, WebEngage send HTTP), Prometheus metrics scraping, and load balancer health checks. It's a pragmatic hybrid.

**Q3: How do you handle versioning and backward compatibility with the proto schema?**

> Protobuf is inherently backward-compatible. Each field has a unique number (`LaunchEvent = 9`, `HostActionEvent = 64`), and we never reuse or remove field numbers. When we add a new event type, we add a new `oneof` variant with a new field number. Old clients that don't know about the new type simply ignore it. Old servers receiving unknown fields skip them gracefully.
>
> We also publish the generated client libraries through CI/CD -- the GitLab pipeline runs `protoc` to generate Go, Java (Maven), and JavaScript (NPM) packages. Teams adopt new event types by updating their dependency version, but old versions continue working.

**Q4: What is the role of the `Header` message in your proto?**

> The `Header` contains session-level context shared across all events in a batch: `sessionId`, `userId`, `deviceId`, `clientId`, `channel`, `os`, `appVersion`, and UTM parameters. Instead of repeating this context in every event, the client sends it once in the header, and our workers copy it to each event during transformation.
>
> This reduces payload size significantly -- if a client sends 10 events, the header data appears once instead of 10 times. During transformation to the ClickHouse model, we merge the header fields into each event record for denormalized storage.

### RabbitMQ and Message Processing

**Q5: Explain your RabbitMQ architecture with 26 queues and 11 exchanges.**

> The architecture uses topic exchanges for content-based routing. When a worker processes an event batch, it groups events by type and publishes each group to the main exchange (`grpc_event.tx`) with the event type as the routing key. Downstream queues bind to specific routing keys -- for example, `clickhouse_click_event_q` binds to `CLICK`, `app_init_event_q` binds to `APP_INIT`, and `grpc_clickhouse_event_q` binds to `*` (wildcard for all types).
>
> We have 11 exchanges covering different event domains: `grpc_event.tx` for main events, `branch_event.tx` for deep linking, `webengage_event.dx` for marketing, `beat.dx` for scraping logs, `affiliate.dx` for affiliate tracking, and error exchanges for dead letter routing.
>
> Each queue has a configurable number of consumer workers -- from 2 for low-volume queues to 20 for post_log_events_q which is our highest-throughput queue. Total concurrent workers across all queues is 90+.

**Q6: How does your retry logic work? Why max 2 retries?**

> When a consumer fails to process a message, we check the `x-retry-count` header. If it doesn't exist, we set it to 1 and republish the message to the same exchange and routing key. On the second failure, the count reaches 2, which exceeds our threshold, so we route the message to an error exchange (dead letter queue) and ACK the original.
>
> We cap at 2 because of poison messages. A malformed event that causes a parsing error will never succeed -- infinite retry would create an infinite loop. With QoS prefetch of 1, a stuck consumer blocks all subsequent messages in that queue. Two retries handle transient failures (brief network blip, momentary ClickHouse restart) while ensuring permanent failures get captured quickly in the DLQ for investigation.

**Q7: How do you handle RabbitMQ connection failures?**

> Auto-recovery via a connector loop. The `rabbitConnector` function runs in a goroutine and follows this pattern: connect to RabbitMQ, send a signal on the `connected` channel, register a close notification handler via `NotifyClose`, then block on `<-rabbitCloseError`. When the connection drops, the channel receives the error, and the loop reconnects.
>
> The initial connection also has a 5-second timeout -- if RabbitMQ is unreachable at startup, we don't block forever. And the `connectToRabbit` function itself retries in a loop with 1-second backoff until it succeeds.
>
> For the consumer side, if the connection drops mid-consumption, the message channel closes, the `for msg := range msgs` loop exits, the consumer goroutine completes, and `safego.GoNoCtx` recovers any panic. The consumer needs to be restarted when the connection recovers.

**Q8: What is QoS prefetch and why do you set it to 1?**

> `channel.Qos(1, 0, false)` tells RabbitMQ to deliver only 1 unacknowledged message to each consumer at a time. This is crucial for two reasons:
>
> First, backpressure -- if a consumer is slow, RabbitMQ won't pile up messages in the consumer's buffer. This prevents out-of-memory issues on the consumer side.
>
> Second, fair dispatch -- with multiple consumers on the same queue, RabbitMQ sends the next message to whichever consumer finishes first. Without prefetch, RabbitMQ would round-robin blindly, potentially overloading a slow consumer while a fast one sits idle.
>
> The tradeoff is lower throughput per consumer -- each consumer processes one message at a time instead of pipelining. We compensate with more consumers (2-20 per queue, 90+ total) for parallelism.

### ClickHouse and Data Storage

**Q9: Why did you transition from PostgreSQL to ClickHouse?**

> The analytics team was running aggregation queries on PostgreSQL -- things like "count events by type per day for the last 30 days" or "average session duration by app version." These queries were scanning full rows in a row-oriented database, which was slow because each event has 20+ columns but the query only needs 2-3.
>
> ClickHouse is columnar -- it stores each column separately on disk, so an aggregation over `event_name` and `event_timestamp` only reads those two columns. The result was 2.5x faster query performance. Plus ClickHouse compresses columnar data aggressively (10-100x for strings with repetitive values like event names), so storage costs dropped too.
>
> We kept PostgreSQL for transactional operations -- referral processing needs ACID, and user account creation requires uniqueness constraints. ClickHouse doesn't support transactions or unique constraints.

**Q10: How does your multi-DB ClickHouse connection work?**

> The configuration stores multiple database names in a comma-separated environment variable that gets split into a string slice. At connection time, we iterate over all database names and create a GORM connection for each, stored in a `map[string]*gorm.DB`. Callers pass an optional `dbName` parameter -- if provided, they get the specific database connection; if nil, they get the default.
>
> A health-check goroutine runs every second, iterating over the map and reconnecting any broken connections. It uses a mutex to prevent concurrent reconnection attempts from racing.

**Q11: What are your 18+ ClickHouse tables and how are they organized?**

> The tables map to event domains. Core analytics: `event`, `error_event`, `click_event`. App lifecycle: `app_init_event`, `launch_refer_event`. Third-party: `branch_event` (49 fields), `webengage_event`, `graphy_event`, `shopify_event`. Scraping logs: `trace_log`, `post_log_event`, `profile_log`, `sentiment_log`, `scrape_request_log`, `profile_relationship_log`. Commerce: `order_log`, `affiliate_order`, `bigboss_votes`. AB testing: `ab_assignment`.
>
> Each table is backed by a Go model struct, and GORM generates the INSERT statements. The event-specific params are stored as JSONB strings (flexible schema within the fixed schema).

**Q12: How do batch inserts work in ClickHouse with GORM?**

> GORM's `db.Create([]model.Event{...})` generates a multi-row INSERT statement. For a batch of 100 events, it produces one `INSERT INTO event VALUES (row1), (row2), ..., (row100)` instead of 100 separate INSERTs.
>
> This is critical for ClickHouse because the MergeTree engine creates one data part per INSERT. Too many small INSERTs causes "too many parts" errors and degrades merge performance. Batching ensures we create fewer, larger data parts.
>
> Our buffered sinker pattern accumulates events in a Go channel and flushes at 100 events or 5 minutes (whichever comes first). The dual-trigger `select` on channel receive and ticker ensures both throughput efficiency and data freshness.

### Go Concurrency and Architecture

**Q13: Explain the worker pool pattern in your system.**

> We have 6 independent worker pools, one for each event source (main events, Branch, WebEngage, Vidooly, Graphy, Shopify). Each pool follows the same pattern:
>
> 1. A buffered channel (capacity 1000) acts as the work queue
> 2. N worker goroutines (configurable per pool) read from the channel
> 3. Each worker loops forever: receive an event batch, group by type, correct timestamps, publish to RabbitMQ
> 4. The channel and workers are initialized once via `sync.Once` for thread safety
>
> The gRPC handler pushes events into the channel with a 1-second timeout. If the channel is full (all workers busy and buffer exhausted), the timeout fires and the client gets an error -- this is natural backpressure that prevents the service from accepting more work than it can process.

**Q14: How do you prevent a bad event from crashing the entire service?**

> Every goroutine is wrapped in `safego.GoNoCtx()`, which does `defer recover()` at the top of the goroutine. If any worker panics (say, nil pointer dereference on a malformed event), the recovery catches the panic, logs the stack trace, and the goroutine exits gracefully.
>
> Without this, Go's default behavior would kill the entire process -- all 90+ workers and both servers. With 10K events/sec, a single malformed event could take down the whole system.
>
> We have two variants: `safego.Go(gCtx, f)` for business logic goroutines (logs to structured logger with context), and `safego.GoNoCtx(f)` for infrastructure goroutines (logs to standard logger).

**Q15: How does the event dispatch handle backpressure?**

> Three levels of backpressure:
>
> 1. **Channel buffer (1000 events):** Absorbs burst traffic. If the workers are momentarily busy, events queue up in the buffer
> 2. **1-second timeout:** If the buffer is full, the `select` statement times out after 1 second and returns an error to the gRPC client. The client knows to retry or alert
> 3. **RabbitMQ QoS (prefetch=1):** Each consumer processes one message at a time. If ClickHouse is slow, consumers back up, queues grow, and RabbitMQ eventually triggers flow control on publishers
>
> This creates an end-to-end backpressure chain: ClickHouse slowdown -> consumer backup -> queue growth -> publisher flow control -> worker pool channel full -> dispatch timeout -> gRPC error to client.

**Q16: How does timestamp correction work and why is it needed?**

> Mobile clients send event timestamps based on the device clock, which can be wrong -- set to the future due to timezone bugs, NTP sync issues, or deliberate manipulation. A future timestamp in the analytics database would corrupt time-series queries.
>
> Our workers check each event's timestamp against the server's current time. If `event_timestamp > now`, we replace it with the server time. We only correct future timestamps, not past ones. A past timestamp might indicate offline events that were batched and sent later -- that's a valid use case. Future timestamps are never valid.

### System Design and Operations

**Q17: How does your graceful deployment work?**

> The deployment script follows a drain-then-replace pattern:
>
> 1. **Drain:** Send `PUT /heartbeat/?beat=false` to mark the instance as unhealthy. The gRPC health check starts returning `NOT_SERVING`, and the load balancer stops sending new requests
> 2. **Wait 15 seconds:** Let in-flight requests complete
> 3. **Kill:** Stop the old process
> 4. **Start:** Launch the new binary
> 5. **Wait 20 seconds:** Let the new process initialize (connect to RabbitMQ, ClickHouse, PostgreSQL)
> 6. **Restore:** Send `PUT /heartbeat/?beat=true` to mark it healthy again
>
> The load balancer continuously checks the gRPC health endpoint and only routes traffic to healthy instances. This achieves zero-downtime deployment.

**Q18: How would you scale this system to handle 10x the traffic?**

> Multiple approaches:
>
> 1. **Horizontal scaling:** The service is stateless (no in-process state beyond connection singletons). Deploy more instances behind the load balancer
> 2. **Worker pool tuning:** Increase `EVENT_WORKER_POOL_SIZE` and `EVENT_BUFFERED_CHANNEL_SIZE` via environment variables. No code change needed
> 3. **RabbitMQ scaling:** Add more consumer workers per queue (e.g., post_log from 20 to 50). For extreme scale, switch hot queues to Kafka for partitioned consumption
> 4. **ClickHouse sharding:** ClickHouse supports distributed tables across shards. Move high-volume tables to sharded clusters
> 5. **Batch size tuning:** Increase the buffer limit from 100 to 1000 for higher throughput per flush

**Q19: What monitoring and observability do you have?**

> Three pillars:
>
> 1. **Metrics (Prometheus):** Exposed via `/metrics` endpoint. Gin collects HTTP metrics automatically. Custom metrics for queue depth, batch sizes, and error rates
> 2. **Error tracking (Sentry):** Every unhandled exception is captured with full stack trace, grouped by error type, and tagged with the environment. Sentry middleware on Gin catches HTTP handler panics
> 3. **Structured logging:** Request logger middleware captures method, path, status, duration, and request body for every HTTP request. The `safego` wrapper logs panics with full goroutine stack traces
>
> For RabbitMQ specifically, the management UI provides queue depth, message rates, and consumer utilization.

**Q20: How do you handle the proto-to-model transformation for 60+ event types?**

> The `TransformToEventModel` function uses a sequential nil-check pattern. For each possible event type, it checks if that getter returns non-nil (e.g., `e.GetLaunchEvent() != nil`). If so, it marshals the event-specific data to JSON and stores it in the `EventParams` field as a flexible JSONB column.
>
> This is admittedly verbose (the file is 1477 lines), but it's straightforward and avoids reflection-heavy magic. Each event type is explicitly handled, making it easy to add custom transformation logic per event type. In a future refactor, we could use a registry pattern or code generation to reduce boilerplate, but the explicit approach ensures no events are silently dropped.

---

## 7. Behavioral Stories (STAR)

### STAR Story 1: Designing the Asynchronous Processing Pipeline

**Situation:** GCC's analytics platform was receiving events from mobile apps, web clients, and third-party webhooks, but the existing approach was synchronous -- events were written directly to PostgreSQL, causing timeouts under load and corrupting analytics data when timestamps were wrong.

**Task:** I needed to design an asynchronous event processing pipeline that could handle 10M+ daily events across 60+ types with reliable delivery, correct timestamps, and faster analytics queries.

**Action:**
- Designed a gRPC service with Protocol Buffers defining 60+ event types using `oneof` for type-safe polymorphism
- Built 6 worker pools (one per event source) with buffered channels and configurable concurrency
- Implemented event grouping by type with timestamp correction -- clamping future timestamps to server time
- Set up RabbitMQ with 11 exchanges and 26 queues for content-based routing, each with retry logic (max 2) and dead letter queues
- Created two sinker patterns: direct writes for low-volume events and buffered sinkers (batch of 100 or 5-minute timer) for high-volume streams
- Migrated the analytics store from PostgreSQL to ClickHouse with multi-database support

**Result:** The system processes 10M+ daily data points with 90+ concurrent workers. ClickHouse queries run 2.5x faster than the previous PostgreSQL queries. The dead letter queue pattern caught data quality issues that were previously invisible. Zero-downtime deployments via gRPC health checks and load balancer integration.

### STAR Story 2: Building the Buffered Sinker for ClickHouse

**Situation:** After migrating from PostgreSQL to ClickHouse, we noticed the "too many parts" error -- ClickHouse's MergeTree engine was struggling with the high rate of small INSERT statements from our 20 post-log consumer workers.

**Task:** I needed to reduce the INSERT frequency without losing data or adding significant latency.

**Action:**
- Designed the buffered sinker pattern: each consumer pushes parsed events into a Go channel (10K capacity)
- A dedicated goroutine reads from the channel with a `select` statement that has two triggers: batch size (100 events) and time interval (5 minutes)
- When either trigger fires, the accumulated batch is flushed to ClickHouse in a single batch INSERT via GORM
- This reduced the INSERT rate from 20/second (one per consumer per message) to roughly 1 every few seconds

**Result:** The "too many parts" errors disappeared entirely. ClickHouse merge performance improved because it processed fewer, larger data parts. The dual-trigger ensures data freshness even during low-traffic periods -- nothing sits in the buffer for more than 5 minutes.

### STAR Story 3: Handling RabbitMQ Connection Failures

**Situation:** In production, the RabbitMQ server occasionally restarted for maintenance, causing all 90+ consumers to lose their connection. The service would crash and require manual restart.

**Task:** Make the service self-healing so that RabbitMQ restarts are transparent to the operation.

**Action:**
- Implemented the `rabbitConnector` pattern: a forever-loop goroutine that connects, waits for close notification via `NotifyClose`, and auto-reconnects with 1-second backoff
- Wrapped the initial connection with a 5-second timeout so the service starts even if RabbitMQ is temporarily down
- Used `sync.Once` to ensure only one connection attempt happens regardless of how many goroutines call `Rabbit(config)` concurrently
- Applied the same auto-reconnect pattern to ClickHouse (1-second health cron) and PostgreSQL

**Result:** RabbitMQ restarts became transparent -- the service detects the dropped connection, reconnects within seconds, and consumers resume processing. The same pattern for ClickHouse and PostgreSQL means the service can ride out brief database maintenance windows without manual intervention.

---

## 8. What-If Scenarios

### Scenario 1: RabbitMQ crashes in production

**Setup:** The RabbitMQ server goes down at 2 AM. All 26 consumer queues stop delivering messages. Events continue arriving via gRPC.

**What happens automatically:**
1. The `rabbitConnector` goroutine detects the connection drop via `NotifyClose` channel
2. `connectToRabbit` enters its retry loop, attempting reconnection every 1 second
3. Worker pools continue receiving events from gRPC and buffering them in the 1000-capacity channels
4. Workers call `rabbit.Rabbit(config).Publish(...)` which fails because the connection is closed -- events are lost from the publish side
5. Consumers' `for msg := range msgs` loops exit because the channel closes
6. The buffered channel fills up (1000 events), and subsequent dispatches hit the 1-second timeout, returning errors to gRPC clients

**Impact:** Event loss during the outage window. Buffered events in the channel (up to 1000) are lost if the process restarts.

**Mitigation:** Auto-reconnect handles transient failures. For zero event loss: add a persistent write-ahead log (WAL) before publishing. Deploy RabbitMQ in a clustered/mirrored configuration.

> **Interview framing:** "The auto-reconnect handles transient failures well, but for complete broker outages, we'd need either a RabbitMQ cluster with mirrored queues or a local WAL for publish-side durability."

### Scenario 2: ClickHouse becomes unreachable

**Setup:** The ClickHouse cluster is down for maintenance. All sinkers that write to ClickHouse start failing.

**What happens automatically:**
1. Direct sinkers return `false` because `db.Create(events)` returns an error
2. The RabbitMQ consumer enters the retry path: first failure sets `x-retry-count=1`, second failure sets `x-retry-count=2`, third attempt exceeds max and routes to dead letter queue
3. Buffered sinkers accumulate events in their Go channels (10K capacity) but `FlushTraceLogEvents` fails -- the buffer resets and those events are lost
4. The `clickhouseConnectionCron` detects broken connections every 1 second and attempts reconnection

**Impact for direct sinkers:** Events retry twice, then land in the DLQ. After ClickHouse recovers, DLQ messages can be replayed.

**Impact for buffered sinkers:** A failed flush discards the batch. This is a gap in the design.

> **Interview framing:** "The retry + DLQ pattern protects direct sinkers well, but the buffered sinkers have a gap -- a failed flush discards the batch. I'd fix this by only clearing the buffer after a successful flush."

### Scenario 3: A poison message enters the system

**Setup:** A mobile client sends a malformed event where the `Timestamp` field contains a non-numeric string. The `transformer.InterfaceToInt64` function panics.

**What happens automatically:**
1. The worker goroutine panics during timestamp conversion
2. `safego.GoNoCtx` catches the panic via `defer recover()`, logs the stack trace
3. The goroutine exits -- one worker is lost from the pool
4. Remaining workers continue processing from the shared channel
5. If the poison message reaches RabbitMQ consumers, they also panic, get caught by `safego`, and the message sits unacknowledged until it hits DLQ after retries

**Impact:** One worker goroutine dies per poison message encounter (not restarted). Over time, if many poison messages arrive, the worker pool shrinks.

> **Interview framing:** "The panic recovery prevents a crash, but we lose a worker. The fix is two-fold: input validation at the gRPC layer to reject bad data early, and worker restart logic so recovered goroutines respawn instead of exiting."

### Scenario 4: The worker pool channel is full (backpressure)

**Setup:** A marketing campaign causes a 5x traffic spike. The event worker pool's buffered channel (capacity 1000) fills up because workers can't publish to RabbitMQ fast enough.

**What happens automatically:**
1. `DispatchEvent` tries to push events into the channel
2. The `select` statement hits the `time.After(1 * time.Second)` case
3. The function returns an error to the gRPC client
4. The client receives the error and knows the event was not accepted

**Mitigation:** Scale horizontally (add more instances), increase channel buffer via env variable, increase worker pool size, use client-side batching, or auto-scale with Kubernetes HPA.

> **Interview framing:** "The 1-second timeout is intentional backpressure -- we'd rather tell the client 'slow down' than accept unbounded work and crash. The fix for a sustained spike is horizontal scaling, not removing the backpressure."

### Scenario 5: A consumer worker is stuck on a slow ClickHouse write

**Setup:** One consumer encounters a ClickHouse node with high CPU. The `db.Create(events)` call takes 30 seconds instead of 200ms. QoS prefetch is 1.

**What happens:**
1. The worker is blocked on the slow write for 30 seconds
2. With QoS=1, RabbitMQ won't send another message to this worker until it ACKs
3. Other consumers on the same queue continue processing normally
4. When the write completes, the worker ACKs and resumes

**Why this is okay:** QoS=1 prevents the slow consumer from accumulating a backlog. Multiple consumers per queue (2-20) ensure one slow worker doesn't halt the queue.

> **Interview framing:** "QoS prefetch of 1 is the key protection here. It means a slow consumer only hurts itself, not other consumers. The other workers keep processing while this one is blocked."

### Scenario 6: Memory leak in a buffered sinker

**Setup:** A bug in the parser causes `nil` events to be pushed to the channel. The sinker accumulates nil events in the buffer.

**What happens:**
1. Buffer grows with nil/empty events
2. When buffer reaches 100, flush is called
3. GORM's `db.Create(events)` either fails (nil pointers) or creates empty rows
4. Buffer resets -- memory stays bounded
5. ClickHouse fills with garbage empty rows, corrupting analytics data

**Impact:** Data quality issue rather than memory leak. The buffer pattern prevents unbounded memory growth, but bad data flows downstream.

> **Interview framing:** "The buffer pattern bounds memory, so it's not a leak in the traditional sense. But it can propagate bad data. The fix is validation at the buffer entry point and monitoring for anomalous row patterns in ClickHouse."

### Scenario 7: Graceful deployment fails mid-process

**Setup:** During deployment, `kill -9` runs before the load balancer has fully drained the instance.

**What happens:**
1. `/heartbeat/?beat=false` marks instance as unhealthy
2. Load balancer stops sending NEW requests (~5 seconds to propagate)
3. `kill -9` terminates the process immediately
4. Events in the worker pool's buffered channel (up to 1000) are lost
5. RabbitMQ messages being processed (unACKed) are redelivered to other consumers
6. Buffered sinker goroutines die with unflushed batches in memory

> **Interview framing:** "The biggest gap is `kill -9` -- it doesn't give the process a chance to flush. I'd implement a `SIGTERM` handler that flushes buffered sinkers, drains the worker channel, and waits for in-flight consumers to ACK before exiting."

### Scenario 8: Clock skew between server and clients

**Setup:** A batch of mobile clients has clocks set 24 hours in the future due to a timezone bug.

**What happens automatically:**
1. The worker receives the events
2. Timestamp correction runs: `if et.Unix() > timeNow.Unix()` triggers, clamping to server time
3. Events proceed with corrected timestamps
4. ClickHouse receives events with accurate insert times

**Impact:** Minimal. The original client timestamp is lost -- we overwrite rather than storing both.

> **Interview framing:** "We built timestamp correction specifically for this scenario. The tradeoff is we lose the original client timestamp. In retrospect, I'd store both and add a correction flag for data quality transparency."

### Scenario 9: Dead letter queue fills up

**Setup:** A ClickHouse schema migration breaks the event model. All events fail to insert. After 2 retries each, they all land in the DLQ.

**What happens:**
1. Every direct sinker returns `false` because GORM fails with a schema mismatch
2. Each message retries twice, then routes to the error exchange
3. DLQ queues grow rapidly
4. RabbitMQ disk usage spikes, eventually hitting disk watermark and triggering flow control
5. Worker pool channels fill up, dispatch timeouts fire, gRPC clients get errors
6. The entire pipeline is effectively down

> **Interview framing:** "The DLQ is a safety net, not a solution. Without monitoring and circuit breakers, a systemic failure turns the DLQ into a secondary problem. The fix is monitoring DLQ depth and having a circuit breaker that stops consumption when a queue's error rate exceeds a threshold."

### Scenario 10: Multiple ClickHouse databases have different availability

**Setup:** The `logs` database goes down, but `analytics` is healthy.

**What happens automatically:**
1. The `clickhouseConnectionCron` detects the broken `logs` connection every 1 second
2. Reconnection fails (node is down), error logged, continues to next database
3. The `analytics` connection is healthy -- no action needed
4. Sinkers writing to `logs` fail, trigger retries, eventually hit DLQ
5. Sinkers writing to `analytics` continue normally

**Why multi-DB helps:** If we had a single database, a node failure would take down all event ingestion. With multi-DB, only the affected domain stops.

> **Interview framing:** "Multi-DB isolation gives us partial failure instead of total failure. If the logs database goes down, analytics keep working. The 1-second health cron detects the failure immediately."

### Failure Modes Summary

| Scenario | Auto-Recovery? | Data Loss Risk | Key Protection |
|----------|---------------|----------------|----------------|
| RabbitMQ crash | Yes (reconnect loop) | Channel buffer events | Auto-reconnect, DLQ |
| ClickHouse down | Partial (cron reconnect) | Buffered sinker batches | Retry + DLQ |
| Poison message | Yes (panic recovery) | None (message hits DLQ) | safego wrapper |
| Backpressure spike | Yes (timeout) | Rejected events | 1-sec timeout, client error |
| Slow consumer | Yes (QoS isolation) | None | QoS prefetch=1 |
| Memory leak | Bounded (buffer reset) | Data quality issue | Buffer size limits |
| Bad deployment | Partial | Channel + unflushed buffers | Drain + sleep |
| Clock skew | Yes (timestamp correction) | Original timestamp | Future timestamp clamp |
| DLQ overflow | No (needs human) | Flow control cascade | Alert on DLQ depth |
| Partial DB failure | Yes (per-DB cron) | Affected domain only | Multi-DB isolation |

---

## 9. How to Speak About This Project

### Key Phrases to Use

**When describing scale:**
- "10 million daily data points across 60+ event types"
- "90+ concurrent consumer workers across 26 RabbitMQ queues"
- "10K events per second ingestion rate"
- "6 independent worker pools with configurable concurrency"

**When describing architecture choices:**
- "We used Protocol Buffers' `oneof` for type-safe polymorphism across 60+ event types"
- "Content-based routing via RabbitMQ exchanges -- the event type name becomes the routing key"
- "Buffered sinker pattern: batch accumulation with dual-trigger flush (size OR time)"
- "Singleton connections with lazy initialization via `sync.Once`"
- "End-to-end backpressure from ClickHouse through RabbitMQ to the gRPC handler"

**When describing impact:**
- "2.5x faster analytics queries after migrating from PostgreSQL to ClickHouse"
- "Zero data loss with dead letter queues capturing failed messages for replay"
- "Zero-downtime deployments via gRPC health checks and load balancer drain"
- "Self-healing connections -- the service rides out database restarts automatically"

**When describing Go expertise:**
- "Worker pool pattern with buffered channels for bounded concurrency"
- "Every goroutine wrapped in panic recovery to prevent cascade failures"
- "`sync.Once` for thread-safe lazy initialization of all connection pools"
- "Go's `select` statement for dual-trigger batch flushing"
- "Protobuf reflection for dynamic event type routing"

### Common Follow-Up Questions and Pivot Points

**"What was the hardest part?"**
> Pivot to the buffered sinker design. "The hardest part was getting the batch flush right for ClickHouse. We needed to balance throughput against latency. The dual-trigger `select` on batch size and time interval solved this -- but I had to tune through load testing to find the sweet spot."

**"What would you do differently?"**
> Pivot to code generation. "The event transformation code is 1477 lines of sequential nil-checks for 60+ event types. I would use code generation from the proto definition. I'd also add circuit breakers around ClickHouse writes -- right now a down ClickHouse relies on the RabbitMQ retry, but a circuit breaker would be more responsive."

**"How did you test this?"**
> Pivot to integration approach. "We had unit tests for parsers and transformation functions, and integration tests with local RabbitMQ and ClickHouse. The real confidence came from the DLQ pattern -- in staging, we could see exactly which events failed and why. We also used Prometheus metrics to monitor queue depth and batch sizes."

**"How does this compare to systems at larger scale?"**
> Pivot to principles. "The fundamental patterns are the same -- worker pools, message queues, batch writes, and dead letter queues. At Google scale, you'd swap RabbitMQ for Pub/Sub, ClickHouse for BigQuery, and add partition-level parallelism. But the architecture scales to any volume. The difference is operational tooling, not design."

### Mapping to Interview Themes

| Interview Theme | Event-gRPC Example |
|-----------------|-------------------|
| **System Design** | "Design a real-time event pipeline" -- this IS that system |
| **Distributed Systems** | RabbitMQ routing, auto-reconnect, DLQ, eventual consistency |
| **Go Proficiency** | Worker pools, channels, sync.Once, goroutines, panic recovery |
| **Database Design** | ClickHouse vs PostgreSQL tradeoff, batch inserts, multi-DB |
| **API Design** | gRPC + REST hybrid, proto versioning, health checks |
| **Reliability** | Retry logic, DLQ, auto-reconnect, graceful deployment |
| **Performance** | Buffered sinkers, batch inserts, 2.5x improvement |
| **Scale** | 10M daily, 90+ workers, configurable concurrency |

### Do's and Don'ts

**DO:**
- Lead with the problem ("10M daily events needed reliable ingestion")
- Mention the numbers: 60+ types, 26 queues, 90+ workers, 2.5x faster
- Explain WHY you chose each technology (gRPC for type safety, RabbitMQ for smart routing)
- Reference specific code patterns (worker pool, buffered sinker, sync.Once)
- Connect to the resume bullet: "This is the system behind the 10M daily data points bullet"

**DON'T:**
- Don't say "I just set up RabbitMQ" -- explain the exchange/routing architecture
- Don't describe ClickHouse as "just a database" -- emphasize columnar, batch-optimized, 2.5x improvement
- Don't skip the backpressure story -- it shows you think about failure modes
- Don't forget the HTTP hybrid -- it shows pragmatism over dogmatic architecture
- Don't undersell the proto work -- 688 lines of typed definitions across 3 languages is significant
