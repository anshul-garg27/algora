# Event-gRPC: Technical Implementation (Actual Code)

All code snippets below are taken directly from the repository source files with annotations explaining the design patterns and engineering decisions.

---

## 1. gRPC Service Definition (proto/eventservice.proto)

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

---

## 2. gRPC Server + HTTP Hybrid (main.go)

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

    // ... 26 consumer configurations (see section 5) ...

    // HTTP server on port 8019 (Gin) -- blocks main goroutine
    err := router.SetupRouter(config).Run(":" + config.GinPort)
    if err != nil {
        log.Fatal("Error starting server")
    }
}
```

---

## 3. Event Dispatch with Timeout Protection (event/event.go)

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

---

## 4. Worker Pool Pattern (eventworker/eventworker.go)

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

---

## 5. 26 RabbitMQ Consumer Configurations (main.go)

All 26 consumers are configured declaratively in `main.go`. Here are representative examples showing both direct and buffered patterns:

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

---

## 6. RabbitMQ Connection Management (rabbit/rabbit.go)

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

---

## 7. Retry Logic with Dead Letter Queues (rabbit/rabbit.go)

The consumer implements a max-2-retry pattern: on failure, republish with incremented `x-retry-count` header. After 2 failures, route to error exchange (dead letter queue).

```go
// File: rabbit/rabbit.go -- Consume method (simplified for clarity)

func (rabbit *RabbitConnection) Consume(rabbitConsumerConfig RabbitConsumerConfig) error {
    channel, _ := rabbit.connection.Channel()
    defer channel.Close()

    // Declare durable queue
    channel.QueueDeclare(rabbitConsumerConfig.QueueName,
        true,   // durable
        false,  // auto-delete
        false,  // exclusive
        false,  // no-wait
        nil)

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

**Retry flow:**
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

---

## 8. Buffered Sinker Pattern (sinker/tracelogeventsinker.go)

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

---

## 9. Direct Event Sinker (sinker/eventsinker.go)

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

---

## 10. ClickHouse Multi-DB Connection (clickhouse/clickhouse.go)

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

---

## 11. Safe Goroutine Execution (safego/safego.go)

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

---

## 12. PostgreSQL Connection with Schema Routing (pg/pg.go)

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

---

## 13. HTTP Router with Observability (router/router.go)

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

---

## 14. Configuration Management (config/config.go)

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

---

## Summary of Source Files Referenced

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
