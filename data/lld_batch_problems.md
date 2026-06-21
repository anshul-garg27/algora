# LLD Batch — 17 Problems

> **Goal:** Build 17 Low-Level Design interview sessions in parallel using Workflow / multi-agent orchestration. Quality must match the rate-limiter reference (`c9c3ad9d-...lld`) — full §1–§9 markdown, runnable code with main.py + pytest both green, conversation JSON written and verified, opens at `https://localhost:8002/?s=<session_id>`.
>
> **Reference spec files:**
> - `/Users/anshullkgarg/Desktop/projects/claude-gpt/lld_prompt.md`
> - `/Users/anshullkgarg/Desktop/projects/claude-gpt/agent_prompts/lld_session_builder.md`

---

## 1. Connect Four Game

**Type:** LLD · **Difficulty:** Medium

### Requirements

- **Board:** 6 rows, 7 columns.
- **Players:** Two players (Red and Yellow tokens).
- **Moves:** Make valid drops in columns.
- **Win condition:** Detect four connected tokens (horizontal, vertical, diagonal). Optimize with sliding window / 4 directions.

---

## 2. Multi-Threaded Topic-Based Message Broker (Pub-Sub / Kafka-style)

**Type:** LLD · **Difficulty:** Medium

Design a thread-safe, topic-based message broker supporting publish-subscribe semantics in a multi-threaded concurrent environment.

### Requirements

- **Topic Queues:** Maintain separate queues for each topic.
- **Publish & Subscribe:** Support publishing and subscribing concurrently.
- **Offset Replay:** Track subscriber offsets per topic and support resetting offsets to any previous position.
- **Concurrency & Parallelism:** Safeguard against race conditions, ensuring subscribers consume in parallel without blocking each other.
- Assume messages are simple strings; persistence and replication are out of scope.

---

## 3. File System APIs (mkdir, pwd, cd) with Wildcard `cd`

**Type:** LLD · **Difficulty:** Medium

### Problem Statement

Design and implement a set of basic file system APIs that simulate common directory operations:

- `mkdir /path` — Creates a directory at the specified path. Intermediate directories should be created if they don't exist. Returns true if successful, false otherwise (e.g., if a file already exists at the path).
- `pwd` — Returns the current working directory as an absolute path. The root directory is `/`.
- `cd /path` — Changes the current working directory.
    - Path can be absolute or relative. Handles `.` (current dir) and `..` (parent dir).
    - Path can include a wildcard `*` matching any single directory component (`.`, `..`, or any child).
    - If multiple matches exist for a wildcard, decide the behavior (pick any, or throw error).

Focus on a working solution with proper error handling.

#### Input / Output

A sequence of commands. Each command is a string followed by arguments. Output is the result of `pwd` or the boolean from `mkdir`.

#### Example 1
```
Input:
mkdir /a/b
cd /a/*
pwd

Output:
true
/a/b
```

`cd /a/*` changes to `/a/b` because `*` matches `b`.

#### Example 2
```
Input:
mkdir /foo/bar
mkdir /foo/baz
cd /foo/*
pwd

Output:
true
true
/foo/bar (or /foo/baz, depending on tie-break choice)
```

#### Constraints

- Paths consist of lowercase letters, `/`, `.`, `..`, and `*`.
- Directory names cannot contain `*`.
- Maximum path length: 100 characters.

---

## 4. Voter Management System

**Type:** LLD · **Difficulty:** Medium

Design an object-oriented voter management system that manages hierarchical geographical units: states, constituencies, districts, and Electronic Voting Machines (EVMs).

### Requirements

- **Creation & Configuration:** Set up the election system by defining states, constituencies, districts, and assigning EVMs.
- **Voter Registration:** Register voters and associate them with districts/EVMs.
- **Voting Process:** Simulate voters casting ballots through EVMs.
- **Result Aggregation:** Count votes from EVMs, aggregate at district, constituency, and state levels.

---

## 5. Train Platform Management System

**Type:** LLD · **Difficulty:** Medium

Design a system that manages the assignment of trains to platforms in a railway station and supports time-based queries.

### Functional Requirements

- The station has a configurable number of platforms.
- Each train arrives at a specific start time and departs at a specific end time.
- When a train arrives, the system assigns it an available platform for the entire duration of its stay.
- If all platforms are occupied, the train must wait until a platform becomes free.
- Provide a method to query which train is occupying a given platform at any timestamp.
- Provide a method to query which platform a given train occupies at any timestamp.

### Non-Functional Expectations

- Implementable in Java with runnable code.
- Explain the design patterns applied (e.g., Factory, Strategy, Observer).
- Walk through the main steps of the implementation, highlighting how objects interact.

### Assumptions

- Train identifiers are unique.
- Time is represented as an integer (e.g., minutes from start of day).
- Platform numbers are 1-based.

### Deliverables

- Class diagram or description of core classes and their responsibilities.
- Brief justification of chosen design patterns and how they address the requirements.
- Sample usage showing assignment and query operations.

---

## 6. In-Memory Concurrent Task Scheduler

**Type:** LLD · **Difficulty:** Medium

Design and implement an in-memory task scheduler library that schedules tasks at specific times or fixed intervals — without using external scheduling libraries.

### Functional Requirements

1. **Task Submission with Execution Time**
    - `schedule(task, time)` — submit a task to be executed at a specific future time.
2. **Task Scheduling at Fixed Intervals**
    - `scheduleAtFixedInterval(task, interval)` — executed immediately, then re-runs every `interval` seconds AFTER the previous execution completes.
3. **Configurable Worker Threads**
    - Core thread-pool size must be configurable.
4. **Modularity & OOP Principles**
    - Modular design using appropriate concurrency primitives (e.g., `DelayQueue`, custom locks/thread safety).

---

## 7. Thread-Safe Leaderboard System

**Type:** LLD · **Difficulty:** Medium

Design and implement an in-memory leaderboard for a gaming system. Maintain player scores and rankings.

### Requirements

**Player Updates**
- Players can update scores; the system ranks players by score.
- Always return top N players sorted by score descending.

**Precomputed Rankings**
- Rankings should be precomputed efficiently on update so retrieving the top players is fast.

**Efficiency**
- Handle frequent updates and queries efficiently. A player's score can change multiple times; updates must not degrade performance.

**Thread Safety**
- Multiple threads may access and modify concurrently. Must handle concurrent updates and queries without data inconsistency or crashes.

---

## 8. Multi-Threaded Concurrent Stock Exchange

**Type:** LLD · **Difficulty:** Medium · **Company:** Uber

Design and implement an efficient in-memory trading system similar to a stock exchange, where registered users place, execute, and cancel trades in a concurrent multi-threaded environment.

### Requirements

- **Trade Execution:** Match buy and sell orders when prices are equal (FIFO for oldest orders).
- **Concurrent Safety:** Handle placement, modification, cancellation, and execution concurrently.
- **Order Book:** Maintain an in-memory order book per symbol.
- **Data Models:** Track user details, orders, and execution trade details.

---

## 9. Single Elevator Control System

**Type:** LLD · **Difficulty:** Medium · **Company:** Stable Money

Design the software system for a single-shaft residential elevator serving Ground + 10 floors (floors 0 to 10).

### Key Specifications & Constraints

1. **Floor Request Inputs:** Up/Down buttons at each floor (Ground has Down disabled; Top has Up disabled).
2. **Car Request Inputs:** Floor selection buttons (0-10) inside the car.
3. **Displays:** Real-time location and state (UP, DOWN, STOPPED) inside the car and on all floors.
4. **Physical Constraint (Deceleration Distance):** The elevator requires at least 2 floors of deceleration distance to halt from full speed — it cannot stop instantly at adjacent floors when at speed.
5. **Safety Requirements:**
    - Doors must remain closed while moving.
    - Elevator must not move beyond bounds (floor 0 or 10).
    - Support emergency stop handling and a safe halted state under fault/power failure.
6. **Maintenance Mode:** Rejects new requests, completes current trip safely, parks at the nearest floor with doors open.

### Component Design

- **ElevatorController** — Core orchestrator processing requests.
- **RequestQueue / Scheduling Strategy** — e.g., SCAN algorithm to efficiently process requests, avoid starvation, minimize wait times.
- **State Machine** — Manages states `UP`, `DOWN`, `STOPPED`, `MAINTENANCE`, `EMERGENCY_HALT`.

---

## 10. Vending Machine Leasing System

**Type:** LLD · **Difficulty:** Medium

Design a low-level system for managing vending machine leases. Handle different leasing agreements and support multiple payment strategies. The vending machine itself should transition through states such as Idle, Out of Stock, and Maintenance.

---

## 11. Meeting Room Reservation System

**Type:** LLD · **Difficulty:** Medium

Design the low-level system for a Meeting Room Reservation Platform that allows employees to book rooms for meetings, check availability, and manage bookings.

### Functional Requirements

1. View all available meeting rooms for a given time interval.
2. Book a meeting room if it is free during the requested time.
3. Cancel an existing meeting.
4. Handle overlapping meeting requests gracefully.
5. List all meetings scheduled for a given room or employee.
6. Support recurring meetings (optional enhancement).

### Entities

- `Employee`
- `MeetingRoom`
- `Booking`
- `TimeSlot` / `Interval`

### Operations

- `bookRoom(employeeId, roomId, startTime, endTime)`
- `getAvailableRooms(startTime, endTime)`
- `cancelBooking(bookingId)`
- `listBookingsForRoom(roomId)`
- `listBookingsForEmployee(employeeId)`

### Constraints

- No double-booking of the same room at overlapping times.
- Extensible for many rooms and bookings.
- Concurrency: handle race conditions where two users try to book the same room at the same time.

### Example

```
- Room A is booked from 10:00 AM to 11:00 AM.
- User X tries to book Room A from 10:30 AM to 11:30 AM → Booking should fail due to overlap.
- User Y books Room B from 10:30 AM to 11:30 AM → Booking successful.
```

---

## 12. Notification Router for E-commerce Platform

**Type:** LLD · **Difficulty:** Medium

Design a notification router for an e-commerce website.

### Functional Requirements

- Each user has a preferred channel (EMAIL, SMS, PUSH).
- Each notification has a priority (URGENT, NORMAL).
- If URGENT — sent to ALL channels for the user.
- If NORMAL — sent only to the user's preferred channel.
- Notification handlers themselves need NOT be implemented; only routing logic is needed.

### Guidelines & Design

- Extensible for new channels or routing rules.
- Clean code, SOLID principles, appropriate design patterns.

---

## 13. Coupon / Offer / Discount Management System

**Type:** LLD · **Difficulty:** Medium · **Company:** DE Shaw

Design an in-memory coupon management system where sellers can create coupons, and buyers can apply coupons to their shopping carts.

### Core Flows

1. **Seller Operations:** Create coupons with a validity period and specific applicability rules.
2. **Buyer Operations:** Apply a coupon code to a cart and compute the discounted total.

### Coupon Requirements

- **Discount Types:** Flat amount discount or Percentage (%) discount.
- **Scope:** Global (all items), Seller-specific, or Product-specific.
- **Rules / Criteria:**
    - Applicable only if the buyer purchases more than X products.
    - Applicable only if the cart value exceeds a minimum threshold.

### Class Design & Guidelines

- **Strategy Pattern:** For applying different types of discount calculations (`FlatDiscountStrategy`, `PercentDiscountStrategy`).
- **Composite / Specification Pattern:** For validating coupon eligibility (e.g., `CartValueSpecification`, `ProductQuantitySpecification`).
- **Separation of Concerns:** Distinct data-access layers (in-memory repositories) and service layers (`CouponService`, `CartService`).

---

## 14. Idempotent Order Processing Engine

**Type:** LLD · **Difficulty:** Medium

Design a low-level system for an order processing engine that ensures reliability in a distributed environment.

### Requirements

1. Handle orders being submitted multiple times (idempotency) due to network retries or client-side issues.
2. Define core classes and their relationships.
3. Mechanism to track order states (`Created`, `Processing`, `Completed`, `Failed`) to prevent duplicate execution.
4. Use a unique request ID / token to ensure the same order is not processed more than once even if the request is repeated.
5. Discuss how the system would interact with a database to maintain consistency during these retries.

---

## 15. Notification System (multi-channel, with preferences)

**Type:** LLD · **Difficulty:** Medium

Design a notification system that allows users to send and receive notifications through various channels. Goal: an efficient and modular class hierarchy adhering to OO design principles.

### Requirements

1. **Users:** Each identified by a unique user ID. Users can subscribe to different notification types and manage preferences.
2. **Notification Channels:** Multiple channels — email, SMS, push, in-app — each with its own delivery mechanism.
3. **Notification Types:** Users subscribe to types — new messages, friend requests, system alerts, custom events. Each type may have specific content/delivery requirements.

### Bonus

1. **Personalization:** Notifications personalized with user-specific info (name, type-specific details).
2. **Opt-out & Preferences:** Users can opt out of types or unsubscribe entirely; manage preferences (frequency, channels).

### Design Goals

- Identify classes/interfaces; define relationships and responsibilities.
- Encapsulation, inheritance, polymorphism.
- SOLID; loose coupling, high cohesion.
- Extensibility for future changes.

---

## 16. Amazon Locker System

**Type:** LLD · **Difficulty:** Medium

Design a highly scalable and reliable Amazon Locker system. Consider how users interact with lockers, how packages are delivered and picked up, inventory management for locker compartments, security, notifications, and integration with delivery services. Discuss key components such as API gateway, microservices, database choices, and concurrency for locker access.

### Requirements

1. **Package Drop-off** — Allow delivery personnel to drop packages into available locker compartments.
2. **Package Pick-up** — Users pick up using a unique code or mobile app.
3. **Locker Management** — Maintain state and availability of each compartment across locations.
4. **Notifications** — Real-time notifications about delivery, pick-up codes, expirations.
5. **Proximity Service** — Efficiently locate nearby locker stations based on user location.
6. **Concurrency** — Handle multiple users and delivery agents interacting concurrently.
7. **Scalability** — Support a large number of lockers, users, transactions globally.
8. **Security** — Secure access; protect user/package data.

---

## 17. Customer Issue Resolution System (Ticket / Jira / Trello-style)

**Type:** LLD · **Difficulty:** Medium

PhonePe processes a vast number of transactions; some FAIL or remain PENDING. A resolution system is needed where customers log unsuccessful transactions and raise complaints.

The system categorizes issues into types: Payment-related, Mutual Fund-related, Gold-related, Insurance-related. Different agents have specific expertise based on issue type; the system assigns issues to matching agents (waitlist if all are busy). Agents work on one issue at a time and update its status; once resolved, the agent receives the next.

### Features

- Customers can log a complaint against any unsuccessful transaction.
- Agents can search for issues by issue ID or customer email.
- Agents can view their assigned issues and mark them resolved.
- System assigns issues to agents based on an assigning strategy.
- Admin can onboard new agents.
- Admin can view an agent's work history.

### Functions (in decreasing order of importance)

```
createIssue(transactionId, issueType, subject, description, email)
addAgent(agentEmail, agentName, List<issueType>)
assignIssue(issueId)             // assign to any one of the free agents
getIssues(filter)                // issues against the provided filter
updateIssue(issueId, status, resolution)
resolveIssue(issueId, resolution)
viewAgentsWorkHistory()          // list of issues each agent worked on
```

### Example

```
createIssue("T1", "Payment Related", "Payment Failed", "My payment failed but money is debited", "testUser1@test.com");
>>> Issue I1 created against transaction "T1"

createIssue("T2", "Mutual Fund Related", "Purchase Failed", "Unable to purchase Mutual Fund", "testUser2@test.com");
>>> Issue I2 created against transaction "T2"

createIssue("T3", "Payment Related", "Payment Failed", "My payment failed but money is debited", "testUser2@test.com");
>>> Issue I3 created against transaction "T3"

addAgent("agent1@test.com", "Agent 1", Arrays.asList("Payment Related", "Gold Related"));
>>> Agent A1 created

addAgent("agent2@test.com", "Agent 2", Arrays.asList("Payment Related"));
>>> Agent A2 created

assignIssue("I1")  >>> Issue I1 assigned to agent A1
assignIssue("I2")  >>> Issue I2 assigned to agent A2
assignIssue("I3")  >>> Issue I3 added to waitlist of Agent A1

getIssue({"email": "testUser2@test.com"});
>>> I2 {"T2", "Mutual Fund Related", "Purchase Failed", ..., "testUser2@test.com", "Open"},
    I3 {"T3", "Payment Related", "Payment Failed", ..., "testUser2@test.com", "Open"}

getIssue({"type": "Payment Related"});
>>> I1 {"T1", "Payment Related", ..., "testUser1@test.com", "Open"},
    I3 {"T3", "Payment Related", ..., "testUser2@test.com", "Open"}

updateIssue("I3", "In Progress", "Waiting for payment confirmation");
>>> I3 status updated to In Progress

resolveIssue("I3", "PaymentFailed debited amount will get reversed");
>>> I3 issue marked resolved

viewAgentsWorkHistory()
>>> A1 -> {I1, I3},
    A2 -> {I2}
```
