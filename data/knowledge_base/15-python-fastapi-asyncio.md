# Python, FastAPI, and AsyncIO -- Complete Study Guide

**For:** Anshul Garg | Backend Engineer | Google Interview Preparation
**Context:** Built Python scraping engine with 150+ async workers at Good Creator Co, processing 10M+ daily data points across Instagram/YouTube. Architected FastAPI services with dual-database architecture, Redis caching, connection pooling, 3-level stacked rate limiting, and S3 asset pipeline processing 8M daily images. Reduced analytics query latency from 30s to 2s.

---

# TABLE OF CONTENTS

1. [Part 1: Python async/await Fundamentals](#part-1-python-asyncawait-fundamentals)
   - [What Is Asynchronous Programming](#what-is-asynchronous-programming)
   - [Coroutines](#coroutines)
   - [The await Keyword](#the-await-keyword)
   - [Tasks](#tasks)
   - [Futures](#futures)
   - [Awaitable Objects](#awaitable-objects)
   - [Gathering and Waiting](#gathering-and-waiting)
   - [Async Context Managers and Iterators](#async-context-managers-and-iterators)
2. [Part 2: AsyncIO Internals](#part-2-asyncio-internals)
   - [The Event Loop](#the-event-loop)
   - [I/O Multiplexing and Selectors](#io-multiplexing-and-selectors)
   - [Event Loop Lifecycle](#event-loop-lifecycle)
   - [Tasks vs Coroutines vs Futures](#tasks-vs-coroutines-vs-futures)
   - [Callback-Based vs Coroutine-Based](#callback-based-vs-coroutine-based)
   - [Event Loop Internals Diagram](#event-loop-internals-diagram)
3. [Part 3: Async Libraries -- aiohttp, aioboto3, aio-pika](#part-3-async-libraries)
   - [aiohttp -- Async HTTP Client/Server](#aiohttp)
   - [aioboto3 -- Async AWS SDK](#aioboto3)
   - [aio-pika -- Async RabbitMQ Client](#aio-pika)
4. [Part 4: FastAPI Deep Dive](#part-4-fastapi-deep-dive)
   - [Routing and Path Operations](#routing-and-path-operations)
   - [Dependency Injection](#dependency-injection)
   - [Pydantic Models and Validation](#pydantic-models-and-validation)
   - [Middleware](#middleware)
   - [Exception Handlers](#exception-handlers)
   - [Background Tasks](#background-tasks)
   - [FastAPI Request Lifecycle Diagram](#fastapi-request-lifecycle-diagram)
5. [Part 5: FastAPI vs Django vs Flask](#part-5-fastapi-vs-django-vs-flask)
6. [Part 6: Python Concurrency -- Threading vs Multiprocessing vs AsyncIO](#part-6-python-concurrency)
   - [The GIL Explained](#the-gil-explained)
   - [Threading](#threading)
   - [Multiprocessing](#multiprocessing)
   - [AsyncIO](#asyncio)
   - [When to Use What](#when-to-use-what)
7. [Part 7: uvloop](#part-7-uvloop)
8. [Part 8: Connection Pooling in Async Python](#part-8-connection-pooling-in-async-python)
9. [Part 9: Rate Limiting](#part-9-rate-limiting)
   - [Token Bucket](#token-bucket)
   - [Sliding Window](#sliding-window)
   - [Leaky Bucket](#leaky-bucket)
   - [Anshul's 3-Level Stacked Implementation](#anshuls-3-level-stacked-implementation)
10. [Part 10: Pydantic v2](#part-10-pydantic-v2)
11. [Part 11: ASGI vs WSGI](#part-11-asgi-vs-wsgi)
12. [Part 12: How Anshul Used It at Good Creator Co](#part-12-how-anshul-used-it)
13. [Part 13: Interview Q&A (15+ Questions)](#part-13-interview-qa)

---

# Part 1: Python async/await Fundamentals

## What Is Asynchronous Programming

Synchronous code executes one operation at a time. When a function makes an I/O call (network request, file read, database query), the entire thread blocks and waits for the result. In a web scraping engine processing 10M+ data points per day, this is catastrophic -- you spend most of your time waiting for HTTP responses.

Asynchronous programming lets a single thread manage many concurrent I/O operations. While one operation waits for a network response, the thread picks up another operation. This is **concurrency** (multiple tasks making progress) but NOT **parallelism** (multiple tasks executing simultaneously on different cores).

**The key insight:** Most backend workloads are I/O-bound, not CPU-bound. A scraping worker spends 95%+ of its time waiting for HTTP responses. Async lets you use that wait time productively.

```
Synchronous (1 thread, 3 HTTP requests):
Thread: [Request 1]----[wait 200ms]----[Request 2]----[wait 200ms]----[Request 3]----[wait 200ms]
Total: ~600ms

Asynchronous (1 thread, 3 HTTP requests):
Thread: [Req 1][Req 2][Req 3]----[wait ~200ms]----[Process 1][Process 2][Process 3]
Total: ~200ms
```

## Coroutines

A coroutine is a function defined with `async def`. Calling it does NOT execute the function body -- it returns a **coroutine object**. The body only executes when you `await` it or schedule it on the event loop.

```python
import asyncio

# This is a coroutine FUNCTION
async def fetch_creator_data(creator_id: str) -> dict:
    """Fetch creator profile data from the platform API."""
    print(f"Fetching data for creator {creator_id}")
    # Simulate network I/O
    await asyncio.sleep(0.1)  # This yields control back to the event loop
    return {"id": creator_id, "followers": 50000, "platform": "instagram"}

# Calling a coroutine function returns a coroutine OBJECT -- it does NOT run
coro = fetch_creator_data("creator_123")
print(type(coro))  # <class 'coroutine'>

# To actually execute it, you must await it or schedule it
async def main():
    # Option 1: await it directly (sequential)
    result = await fetch_creator_data("creator_123")
    print(result)

asyncio.run(main())
```

**Coroutine states:**

```
CREATED  -->  RUNNING  -->  SUSPENDED  -->  RUNNING  -->  COMPLETED
  |              |             |                             |
  |         (executing)   (hit await,                  (returned or
  |                       yielded to                    raised exception)
  |                       event loop)
(async def
 called)
```

### Native Coroutines vs Generator-Based Coroutines

Python 3.5+ introduced native coroutines with `async def`. Before that, coroutines were built with generators using `@asyncio.coroutine` and `yield from`. Native coroutines are the standard now.

```python
# Modern (Python 3.5+) -- native coroutine
async def fetch_data():
    await asyncio.sleep(1)
    return {"data": "value"}

# Legacy (pre-3.5) -- generator-based coroutine (DO NOT use in new code)
@asyncio.coroutine
def fetch_data_legacy():
    yield from asyncio.sleep(1)
    return {"data": "value"}
```

## The await Keyword

`await` does two things:

1. **Suspends** the current coroutine, yielding control back to the event loop
2. **Resumes** when the awaited operation completes, returning its result

You can only use `await` inside an `async def` function. You can only `await` **awaitable** objects (coroutines, Tasks, Futures, or objects with `__await__`).

```python
import asyncio
import aiohttp

async def scrape_instagram_profile(username: str) -> dict:
    """
    Real-world example: scraping a creator profile.
    Each 'await' is a point where this coroutine suspends and the
    event loop can run other coroutines.
    """
    async with aiohttp.ClientSession() as session:
        # await #1: HTTP request -- coroutine suspends while waiting for response
        async with session.get(
            f"https://api.example.com/instagram/{username}"
        ) as response:
            # await #2: reading response body -- another suspension point
            data = await response.json()

    # await #3: database write -- another suspension point
    await save_to_database(data)

    # await #4: cache update -- another suspension point
    await update_redis_cache(username, data)

    return data
```

**What happens at each await:**

```
scrape_instagram_profile("creator1")
  |
  |--> await session.get(...)      -- SUSPEND, event loop runs other tasks
  |    <-- response received       -- RESUME
  |
  |--> await response.json()       -- SUSPEND, event loop runs other tasks
  |    <-- body parsed             -- RESUME
  |
  |--> await save_to_database(...) -- SUSPEND, event loop runs other tasks
  |    <-- write confirmed         -- RESUME
  |
  |--> await update_redis_cache    -- SUSPEND, event loop runs other tasks
  |    <-- cache updated           -- RESUME
  |
  +--> return data
```

## Tasks

A **Task** wraps a coroutine and schedules it to run on the event loop. Unlike bare `await` (which is sequential), creating Tasks lets coroutines run **concurrently**.

```python
import asyncio
import time

async def fetch_platform_data(platform: str, creator_id: str) -> dict:
    """Simulate fetching data from different platforms."""
    print(f"[{time.strftime('%X')}] Starting {platform} fetch for {creator_id}")
    await asyncio.sleep(1)  # Simulate 1-second API call
    print(f"[{time.strftime('%X')}] Completed {platform} fetch for {creator_id}")
    return {"platform": platform, "creator_id": creator_id, "metrics": {}}

async def main():
    creator_id = "creator_456"

    # SEQUENTIAL -- takes 3 seconds
    print("=== Sequential ===")
    start = time.time()
    ig_data = await fetch_platform_data("instagram", creator_id)
    yt_data = await fetch_platform_data("youtube", creator_id)
    tt_data = await fetch_platform_data("tiktok", creator_id)
    print(f"Sequential time: {time.time() - start:.2f}s\n")

    # CONCURRENT with Tasks -- takes ~1 second
    print("=== Concurrent ===")
    start = time.time()
    task1 = asyncio.create_task(fetch_platform_data("instagram", creator_id))
    task2 = asyncio.create_task(fetch_platform_data("youtube", creator_id))
    task3 = asyncio.create_task(fetch_platform_data("tiktok", creator_id))

    # All three tasks run concurrently on the event loop
    ig_data = await task1
    yt_data = await task2
    tt_data = await task3
    print(f"Concurrent time: {time.time() - start:.2f}s")

asyncio.run(main())
```

**Output:**

```
=== Sequential ===
[14:30:01] Starting instagram fetch for creator_456
[14:30:02] Completed instagram fetch for creator_456
[14:30:02] Starting youtube fetch for creator_456
[14:30:03] Completed youtube fetch for creator_456
[14:30:03] Starting tiktok fetch for creator_456
[14:30:04] Completed tiktok fetch for creator_456
Sequential time: 3.00s

=== Concurrent ===
[14:30:04] Starting instagram fetch for creator_456
[14:30:04] Starting youtube fetch for creator_456
[14:30:04] Starting tiktok fetch for creator_456
[14:30:05] Completed instagram fetch for creator_456
[14:30:05] Completed youtube fetch for creator_456
[14:30:05] Completed tiktok fetch for creator_456
Concurrent time: 1.00s
```

### Task Cancellation

Tasks can be cancelled. This is critical for managing scraping workers that need to be shut down gracefully.

```python
import asyncio

async def long_running_scrape(creator_id: str):
    """A scrape job that might need to be cancelled."""
    try:
        while True:
            print(f"Scraping {creator_id}...")
            await asyncio.sleep(5)  # CancelledError is raised HERE
            print(f"Processing batch for {creator_id}")
    except asyncio.CancelledError:
        # Cleanup: close connections, flush buffers, update status
        print(f"Scrape for {creator_id} cancelled, cleaning up...")
        await cleanup_resources(creator_id)
        raise  # Always re-raise CancelledError

async def main():
    task = asyncio.create_task(long_running_scrape("creator_789"))

    # Let it run for 7 seconds
    await asyncio.sleep(7)

    # Cancel the task
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        print("Task was cancelled successfully")
```

## Futures

A **Future** is a low-level awaitable object representing a result that does not exist yet. Tasks are a subclass of Future. You rarely create Futures directly -- they are used internally by the event loop and by libraries bridging callback-based and coroutine-based code.

```python
import asyncio

async def demonstrate_future():
    loop = asyncio.get_running_loop()

    # Create a Future manually
    future = loop.create_future()

    # Simulate setting the result from a callback (e.g., a C extension)
    async def set_result_later():
        await asyncio.sleep(1)
        future.set_result("Data from callback-based library")

    asyncio.create_task(set_result_later())

    # Await the future -- suspends until set_result is called
    result = await future
    print(result)  # "Data from callback-based library"

# More practical: bridging synchronous code with run_in_executor
async def cpu_intensive_in_thread():
    """Run CPU-bound work in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()

    # run_in_executor returns a Future
    # This is how you integrate sync libraries (like PIL for image processing)
    result = await loop.run_in_executor(
        None,  # Use default ThreadPoolExecutor
        process_image,  # Synchronous function
        image_data       # Arguments
    )
    return result
```

**Inheritance hierarchy:**

```
Awaitable (ABC)
  |
  +-- Coroutine
  |
  +-- Future
       |
       +-- Task (subclass of Future, wraps a Coroutine)
```

## Awaitable Objects

Anything that can be used with `await` is an **awaitable**. There are three kinds:

1. **Coroutines** -- returned by `async def` functions
2. **Tasks** -- created by `asyncio.create_task()`
3. **Futures** -- low-level, usually created by the event loop
4. **Objects with `__await__`** -- custom awaitable classes

```python
import asyncio

class AsyncDatabaseConnection:
    """Custom awaitable: a database connection that initializes asynchronously."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self.connection = None

    def __await__(self):
        return self._connect().__await__()

    async def _connect(self):
        print(f"Connecting to {self.dsn}...")
        await asyncio.sleep(0.5)  # Simulate connection setup
        self.connection = {"status": "connected", "dsn": self.dsn}
        return self

async def main():
    # You can await this custom object directly
    db = await AsyncDatabaseConnection("postgresql://localhost/gcc_analytics")
    print(db.connection)  # {'status': 'connected', 'dsn': '...'}
```

## Gathering and Waiting

`asyncio.gather()` and `asyncio.wait()` are the primary tools for running multiple coroutines concurrently.

### asyncio.gather

Runs awaitables concurrently and returns results in the **same order** as the input. This is what you use most often.

```python
import asyncio
from typing import List

async def scrape_creator_batch(creator_ids: List[str]) -> List[dict]:
    """
    Scrape a batch of creators concurrently.
    At GCC, we processed batches of 50-100 creators at a time.
    """
    tasks = [
        scrape_single_creator(creator_id)
        for creator_id in creator_ids
    ]

    # return_exceptions=True prevents one failure from killing all tasks
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successful = []
    failed = []
    for creator_id, result in zip(creator_ids, results):
        if isinstance(result, Exception):
            failed.append((creator_id, result))
        else:
            successful.append(result)

    print(f"Batch complete: {len(successful)} succeeded, {len(failed)} failed")
    return successful
```

### asyncio.wait

More flexible than `gather`. Returns sets of (done, pending) tasks. Supports timeout and return conditions.

```python
import asyncio

async def scrape_with_timeout(creator_ids: List[str], timeout: float = 30.0):
    """
    Scrape creators with a global timeout.
    If some are still pending after 30s, cancel them.
    """
    tasks = {
        asyncio.create_task(
            scrape_single_creator(cid),
            name=f"scrape-{cid}"  # Named tasks for debugging
        )
        for cid in creator_ids
    }

    done, pending = await asyncio.wait(
        tasks,
        timeout=timeout,
        return_when=asyncio.ALL_COMPLETED  # or FIRST_COMPLETED, FIRST_EXCEPTION
    )

    # Cancel any tasks that didn't finish in time
    for task in pending:
        task.cancel()
        print(f"Cancelled: {task.get_name()}")

    # Collect results from completed tasks
    results = []
    for task in done:
        try:
            results.append(task.result())
        except Exception as e:
            print(f"Task {task.get_name()} failed: {e}")

    return results
```

### asyncio.as_completed

Returns an iterator of futures that yield results as they complete (not in input order).

```python
import asyncio

async def process_as_available(creator_ids: List[str]):
    """Process results as soon as they are available -- useful for streaming."""
    tasks = [
        asyncio.create_task(scrape_single_creator(cid))
        for cid in creator_ids
    ]

    for coro in asyncio.as_completed(tasks):
        result = await coro  # Returns the next completed result
        # Process immediately without waiting for all others
        await publish_to_rabbitmq(result)
```

### Semaphore for Concurrency Limiting

When scraping platforms, you cannot fire 10,000 concurrent requests -- you will get rate-limited or banned. Semaphores limit concurrency.

```python
import asyncio

async def scrape_with_concurrency_limit(
    creator_ids: List[str],
    max_concurrent: int = 150  # GCC used 150 async workers
) -> List[dict]:
    """
    Limit concurrent scraping operations using a semaphore.
    This is how we managed 150+ async workers without overwhelming
    platform APIs.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []

    async def limited_scrape(creator_id: str):
        async with semaphore:
            # At most max_concurrent coroutines are in this block at once
            return await scrape_single_creator(creator_id)

    tasks = [limited_scrape(cid) for cid in creator_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

## Async Context Managers and Iterators

### Async Context Managers (`async with`)

Used for resources that need async setup/teardown: database connections, HTTP sessions, file handles.

```python
import asyncio

class AsyncS3Uploader:
    """
    Async context manager for S3 upload sessions.
    Manages connection pooling and cleanup.
    """
    def __init__(self, bucket: str, max_connections: int = 50):
        self.bucket = bucket
        self.max_connections = max_connections
        self.session = None

    async def __aenter__(self):
        """Async setup: create session and connection pool."""
        self.session = await create_s3_session(
            max_pool_connections=self.max_connections
        )
        print(f"S3 session opened for bucket '{self.bucket}'")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async teardown: close connections gracefully."""
        if self.session:
            await self.session.close()
            print(f"S3 session closed for bucket '{self.bucket}'")
        return False  # Don't suppress exceptions

    async def upload(self, key: str, data: bytes):
        """Upload a single object."""
        await self.session.put_object(
            Bucket=self.bucket, Key=key, Body=data
        )

# Usage
async def upload_creator_images(images: List[tuple]):
    async with AsyncS3Uploader("gcc-creator-assets", max_connections=50) as uploader:
        tasks = [
            uploader.upload(key, data)
            for key, data in images
        ]
        await asyncio.gather(*tasks)
```

### Async Iterators (`async for`)

Used for streaming data: reading from message queues, database cursors, paginated API responses.

```python
import asyncio

class PlatformAPIPaginator:
    """
    Async iterator that paginates through platform API results.
    Used at GCC to iterate through creator lists from Instagram/YouTube APIs.
    """
    def __init__(self, platform: str, endpoint: str, page_size: int = 100):
        self.platform = platform
        self.endpoint = endpoint
        self.page_size = page_size
        self.cursor = None
        self.exhausted = False

    def __aiter__(self):
        return self

    async def __anext__(self) -> List[dict]:
        if self.exhausted:
            raise StopAsyncIteration

        params = {"limit": self.page_size}
        if self.cursor:
            params["cursor"] = self.cursor

        response = await fetch_api_page(self.platform, self.endpoint, params)

        self.cursor = response.get("next_cursor")
        if not self.cursor:
            self.exhausted = True

        items = response.get("items", [])
        if not items:
            raise StopAsyncIteration

        return items

# Usage
async def collect_all_creators(platform: str):
    all_creators = []
    async for page in PlatformAPIPaginator(platform, "/creators"):
        all_creators.extend(page)
        print(f"Fetched {len(all_creators)} creators so far...")
    return all_creators
```

### Async Generators

A simpler way to create async iterators using `async def` + `yield`:

```python
async def stream_rabbitmq_messages(queue_name: str):
    """
    Async generator that yields messages from RabbitMQ.
    Used at GCC to consume scrape job messages.
    """
    connection = await aio_pika.connect_robust("amqp://localhost/")
    channel = await connection.channel()
    queue = await channel.declare_queue(queue_name, durable=True)

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                yield message.body.decode()

# Usage
async def process_scrape_jobs():
    async for job_json in stream_rabbitmq_messages("scrape_jobs"):
        job = json.loads(job_json)
        await execute_scrape_job(job)
```

---

# Part 2: AsyncIO Internals

## The Event Loop

The event loop is the **central execution mechanism** of asyncio. It is a single-threaded loop that:

1. Checks for completed I/O operations
2. Runs callbacks for completed operations
3. Schedules new I/O operations
4. Manages timers and scheduled callbacks

Think of it as a dispatcher: coroutines register their I/O needs, and the event loop notifies them when the I/O is ready.

```python
import asyncio

async def demonstrate_event_loop():
    loop = asyncio.get_running_loop()

    print(f"Loop type: {type(loop).__name__}")
    print(f"Loop is running: {loop.is_running()}")
    print(f"Loop time: {loop.time()}")  # Monotonic clock in seconds

    # Schedule a callback (low-level API)
    def my_callback(future):
        print(f"Callback executed at loop time: {loop.time()}")

    # call_soon: run callback on next iteration of the event loop
    loop.call_soon(lambda: print("call_soon executed"))

    # call_later: run callback after a delay
    loop.call_later(0.5, lambda: print("call_later(0.5s) executed"))

    # call_at: run callback at a specific loop time
    loop.call_at(loop.time() + 1.0, lambda: print("call_at executed"))

    await asyncio.sleep(2)  # Give callbacks time to fire
```

### Event Loop Implementations

Python ships with `SelectorEventLoop` (default on all platforms) and `ProactorEventLoop` (Windows only, uses IOCP). The `uvloop` package provides a drop-in replacement built on libuv (2-4x faster).

```python
# Default event loop
import asyncio
loop = asyncio.new_event_loop()
print(type(loop))  # asyncio.SelectorEventLoop

# Using uvloop (must install: pip install uvloop)
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
loop = asyncio.new_event_loop()
print(type(loop))  # uvloop.Loop
```

## I/O Multiplexing and Selectors

The event loop uses **I/O multiplexing** to monitor multiple file descriptors (sockets, pipes) simultaneously on a single thread. The operating system provides system calls for this:

| System Call | OS        | Mechanism          | Scalability                         |
| ----------- | --------- | ------------------ | ----------------------------------- |
| `select`    | All       | Bitmap of FDs      | O(n), limited to ~1024 FDs          |
| `poll`      | Unix      | Array of FDs       | O(n), no FD limit                   |
| `epoll`     | Linux     | Kernel event table | O(1) for events, scales to millions |
| `kqueue`    | macOS/BSD | Kernel event queue | O(1), similar to epoll              |
| `IOCP`      | Windows   | Completion ports   | True async I/O, proactor model      |

Python's `selectors` module abstracts over these:

```python
import selectors
import socket

# Python automatically picks the best selector for the platform
sel = selectors.DefaultSelector()
print(type(sel))  # selectors.KqueueSelector on macOS, EpollSelector on Linux

# How the event loop uses selectors internally (simplified):
def simplified_event_loop():
    """
    This is roughly what asyncio's event loop does on each iteration.
    """
    sel = selectors.DefaultSelector()

    # Register file descriptors we care about
    server_sock = socket.socket()
    server_sock.setblocking(False)
    server_sock.bind(('localhost', 8080))
    server_sock.listen()

    sel.register(server_sock, selectors.EVENT_READ, data="accept")

    while True:
        # Block until at least one FD is ready (or timeout)
        events = sel.select(timeout=0.1)

        for key, mask in events:
            if key.data == "accept":
                conn, addr = key.fileobj.accept()
                conn.setblocking(False)
                sel.register(conn, selectors.EVENT_READ, data="read")
            elif key.data == "read":
                data = key.fileobj.recv(4096)
                if data:
                    process_data(data)
                else:
                    sel.unregister(key.fileobj)
                    key.fileobj.close()

        # Run any scheduled callbacks
        run_ready_callbacks()

        # Check for completed timers
        run_expired_timers()
```

### How asyncio Uses Selectors

When you `await` a network operation:

1. The coroutine registers the socket FD with the selector for READ or WRITE events
2. The coroutine **suspends** (yields control to the event loop)
3. The event loop calls `selector.select()`, which blocks until an FD is ready
4. When the FD is ready, the event loop **resumes** the coroutine that was waiting on it

This is why async code is efficient: the thread never blocks on individual I/O. It blocks only on `selector.select()`, which can watch thousands of FDs simultaneously.

## Event Loop Lifecycle

```python
import asyncio

# asyncio.run() does all of this for you:
async def main():
    pass

# What asyncio.run(main()) actually does:
def manual_run(coro):
    """Simplified version of asyncio.run()"""
    # 1. Create a new event loop
    loop = asyncio.new_event_loop()

    try:
        # 2. Set it as the current event loop for this thread
        asyncio.set_event_loop(loop)

        # 3. Run the coroutine until it completes
        result = loop.run_until_complete(coro)

        return result
    finally:
        try:
            # 4. Cancel all remaining tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()

            # 5. Give cancelled tasks a chance to run their cleanup
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )

            # 6. Shutdown async generators
            loop.run_until_complete(loop.shutdown_asyncgens())

            # 7. Shutdown the default executor
            loop.run_until_complete(loop.shutdown_default_executor())
        finally:
            # 8. Close the event loop
            asyncio.set_event_loop(None)
            loop.close()
```

### The Event Loop Iteration (One "Tick")

Each iteration of the event loop does the following in order:

```
1. Run all callbacks scheduled with call_soon() (the "ready" queue)
       |
       v
2. Poll for I/O using selector.select(timeout)
   - timeout = time until next scheduled callback (call_later/call_at)
   - Returns list of ready file descriptors
       |
       v
3. For each ready FD, run the associated callback
   - This resumes coroutines that were awaiting I/O on that FD
       |
       v
4. Run callbacks scheduled by step 3 (e.g., task completions)
       |
       v
5. Check for and run expired timers (call_later/call_at)
       |
       v
6. Go back to step 1
```

## Tasks vs Coroutines vs Futures

| Feature              | Coroutine                 | Task                        | Future                   |
| -------------------- | ------------------------- | --------------------------- | ------------------------ |
| **Created by**       | `async def` function call | `asyncio.create_task()`     | `loop.create_future()`   |
| **Is awaitable**     | Yes                       | Yes                         | Yes                      |
| **Runs immediately** | No (lazy)                 | Yes (scheduled on creation) | No (needs set_result)    |
| **Can be cancelled** | No (not scheduled)        | Yes                         | Yes                      |
| **Has result**       | Only after awaited        | Yes (.result())             | Yes (.result())          |
| **Has callbacks**    | No                        | Yes (.add_done_callback)    | Yes (.add_done_callback) |
| **Wraps**            | Nothing                   | A coroutine                 | Nothing                  |
| **Inheritance**      | Coroutine ABC             | Future subclass             | Awaitable ABC            |
| **Use case**         | Define async logic        | Run coroutine concurrently  | Bridge callback APIs     |

```python
import asyncio

async def example():
    # Coroutine: just a definition of async work
    coro = fetch_data()  # Returns coroutine object, nothing runs

    # Task: coroutine scheduled on event loop, starts running immediately
    task = asyncio.create_task(fetch_data())  # Starts running NOW

    # Future: low-level, result set externally
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    # Tasks and Futures can have callbacks
    task.add_done_callback(lambda t: print(f"Task done: {t.result()}"))
    future.add_done_callback(lambda f: print(f"Future done: {f.result()}"))

    # Set future result externally
    future.set_result(42)

    # Await all of them
    result1 = await task
    result2 = await future
```

## Callback-Based vs Coroutine-Based

AsyncIO supports both styles. The coroutine-based style (async/await) is the modern standard. Callback-based is low-level and used primarily in library internals.

```python
import asyncio

# CALLBACK-BASED (low-level, avoid in application code)
def callback_style():
    loop = asyncio.get_event_loop()

    async def connect():
        reader, writer = await asyncio.open_connection('example.com', 80)
        return reader, writer

    future = asyncio.ensure_future(connect())
    future.add_done_callback(lambda f: print(f"Connected: {f.result()}"))
    loop.run_until_complete(future)

# COROUTINE-BASED (modern, preferred)
async def coroutine_style():
    reader, writer = await asyncio.open_connection('example.com', 80)
    print(f"Connected: {reader}, {writer}")
```

## Event Loop Internals Diagram

```mermaid
graph TD
    A[asyncio.run main] --> B[Create Event Loop]
    B --> C[Schedule main as Task]
    C --> D{Event Loop Tick}

    D --> E[1. Run Ready Callbacks<br/>call_soon queue]
    E --> F[2. Poll I/O<br/>selector.select timeout]
    F --> G{Any FDs Ready?}

    G -->|Yes| H[3. Resume Coroutines<br/>waiting on ready FDs]
    G -->|No| I[4. Check Timers]

    H --> I
    I --> J{Any Timers Expired?}
    J -->|Yes| K[5. Run Timer Callbacks]
    J -->|No| L{Any Tasks Pending?}
    K --> L

    L -->|Yes| D
    L -->|No| M[All Tasks Complete]
    M --> N[Cleanup: Cancel Pending,<br/>Shutdown Generators,<br/>Close Loop]

    style A fill:#e1f5fe
    style D fill:#fff3e0
    style F fill:#f3e5f5
    style H fill:#e8f5e9
    style N fill:#ffebee
```

```mermaid
graph LR
    subgraph "Coroutine Lifecycle"
        A[Created] -->|await or create_task| B[Scheduled]
        B -->|event loop picks it| C[Running]
        C -->|hits await| D[Suspended]
        D -->|I/O ready| C
        C -->|return| E[Completed]
        C -->|exception| F[Failed]
        B -->|.cancel| G[Cancelled]
        D -->|.cancel| G
    end

    style A fill:#e3f2fd
    style C fill:#e8f5e9
    style D fill:#fff9c4
    style E fill:#c8e6c9
    style F fill:#ffcdd2
    style G fill:#ffcdd2
```

---

# Part 3: Async Libraries

## aiohttp

`aiohttp` is the async HTTP client/server library for Python. At GCC, it was the backbone of the scraping engine -- every HTTP request to Instagram, YouTube, and TikTok APIs went through aiohttp.

### aiohttp as HTTP Client

```python
import aiohttp
import asyncio
from typing import Optional, Dict, Any

class ScrapingHTTPClient:
    """
    Production HTTP client used at GCC for scraping.
    Key features: connection pooling, timeouts, retry logic, rate limiting.
    """

    def __init__(
        self,
        max_connections: int = 150,
        timeout_seconds: float = 30.0,
        max_retries: int = 3
    ):
        self.max_connections = max_connections
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        # TCPConnector manages the connection pool
        connector = aiohttp.TCPConnector(
            limit=self.max_connections,       # Max total connections
            limit_per_host=30,                # Max connections per host
            ttl_dns_cache=300,                # DNS cache TTL (5 min)
            enable_cleanup_closed=True,       # Clean up closed connections
            keepalive_timeout=30,             # Keep-alive timeout
        )

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout,
            headers={
                "User-Agent": "GCC-Scraper/1.0",
                "Accept": "application/json",
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
            # Allow underlying connections to close gracefully
            await asyncio.sleep(0.25)

    async def get(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """GET request with retry logic."""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                async with self._session.get(
                    url, params=params, headers=headers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        # Rate limited -- exponential backoff
                        retry_after = int(
                            response.headers.get("Retry-After", 2 ** attempt)
                        )
                        print(f"Rate limited, retrying in {retry_after}s")
                        await asyncio.sleep(retry_after)
                    elif response.status >= 500:
                        # Server error -- retry with backoff
                        await asyncio.sleep(2 ** attempt)
                    else:
                        # Client error -- don't retry
                        response.raise_for_status()

            except aiohttp.ClientError as e:
                last_exception = e
                await asyncio.sleep(2 ** attempt)

        raise last_exception or Exception(f"Failed after {self.max_retries} retries")


# Usage in the scraping pipeline
async def scrape_creator_batch(creator_ids: list[str]):
    """Scrape a batch of creators concurrently."""
    async with ScrapingHTTPClient(max_connections=150) as client:
        semaphore = asyncio.Semaphore(100)  # Limit concurrent requests

        async def scrape_one(creator_id: str):
            async with semaphore:
                data = await client.get(
                    f"https://api.instagram.com/v1/users/{creator_id}",
                    params={"fields": "id,username,followers_count,media_count"}
                )
                return data

        tasks = [scrape_one(cid) for cid in creator_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
```

### aiohttp as HTTP Server

```python
from aiohttp import web
import aiohttp

# aiohttp can also serve as a lightweight HTTP server
async def handle_webhook(request: web.Request) -> web.Response:
    """Handle incoming platform webhooks."""
    data = await request.json()
    platform = request.match_info.get("platform")

    # Process webhook asynchronously
    await process_webhook(platform, data)

    return web.json_response({"status": "received"})

async def health_check(request: web.Request) -> web.Response:
    return web.json_response({"status": "healthy"})

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_post("/webhooks/{platform}", handle_webhook)
    return app

# Run: python -m aiohttp.web -H 0.0.0.0 -P 8080 module:create_app
```

## aioboto3

`aioboto3` is the async wrapper around boto3 (AWS SDK). At GCC, it powered the S3 asset pipeline processing 8M daily images.

```python
import aioboto3
import asyncio
from typing import List, Tuple

class AsyncS3Pipeline:
    """
    Async S3 pipeline for processing creator media assets.
    At GCC: 8M images/day, uploaded to S3 with metadata.
    """

    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.bucket = bucket
        self.region = region
        self.session = aioboto3.Session()

    async def upload_batch(
        self,
        items: List[Tuple[str, bytes, str]],  # (key, data, content_type)
        max_concurrent: int = 50
    ) -> dict:
        """Upload a batch of objects to S3 concurrently."""
        semaphore = asyncio.Semaphore(max_concurrent)
        success_count = 0
        error_count = 0

        async with self.session.client(
            "s3",
            region_name=self.region,
            config=aioboto3.session.Config(
                max_pool_connections=max_concurrent,
                retries={"max_attempts": 3, "mode": "adaptive"}
            )
        ) as s3_client:

            async def upload_one(key: str, data: bytes, content_type: str):
                nonlocal success_count, error_count
                async with semaphore:
                    try:
                        await s3_client.put_object(
                            Bucket=self.bucket,
                            Key=key,
                            Body=data,
                            ContentType=content_type,
                            Metadata={
                                "uploaded-by": "gcc-scraper",
                                "pipeline-version": "2.0"
                            }
                        )
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        print(f"Failed to upload {key}: {e}")

            tasks = [
                upload_one(key, data, ct)
                for key, data, ct in items
            ]
            await asyncio.gather(*tasks)

        return {"success": success_count, "errors": error_count}

    async def download_object(self, key: str) -> bytes:
        """Download a single object from S3."""
        async with self.session.client("s3", region_name=self.region) as s3:
            response = await s3.get_object(Bucket=self.bucket, Key=key)
            data = await response["Body"].read()
            return data

    async def list_objects(self, prefix: str, max_keys: int = 1000) -> list:
        """List objects with async pagination."""
        all_keys = []
        async with self.session.client("s3", region_name=self.region) as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(
                Bucket=self.bucket,
                Prefix=prefix,
                PaginationConfig={"MaxItems": max_keys, "PageSize": 100}
            ):
                for obj in page.get("Contents", []):
                    all_keys.append(obj["Key"])
        return all_keys

    async def generate_presigned_url(
        self, key: str, expiration: int = 3600
    ) -> str:
        """Generate a presigned URL for temporary access."""
        async with self.session.client("s3", region_name=self.region) as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expiration
            )
            return url


# Usage in the scraping pipeline
async def process_creator_images(creator_id: str, image_urls: List[str]):
    """Download images from platform and upload to S3."""
    pipeline = AsyncS3Pipeline("gcc-creator-assets")

    # Download all images concurrently
    async with ScrapingHTTPClient() as http_client:
        download_tasks = [
            http_client.get_bytes(url) for url in image_urls
        ]
        image_data_list = await asyncio.gather(
            *download_tasks, return_exceptions=True
        )

    # Prepare upload items
    upload_items = []
    for i, (url, data) in enumerate(zip(image_urls, image_data_list)):
        if isinstance(data, Exception):
            continue
        key = f"creators/{creator_id}/images/{i}.jpg"
        upload_items.append((key, data, "image/jpeg"))

    # Upload all to S3 concurrently
    result = await pipeline.upload_batch(upload_items, max_concurrent=50)
    print(f"Uploaded {result['success']} images for {creator_id}")
```

## aio-pika

`aio-pika` is the async RabbitMQ client. At GCC, RabbitMQ was the message broker between the Python scraping engine and the Go gRPC service.

```python
import aio_pika
import asyncio
import json
from typing import Callable, Awaitable

class AsyncRabbitMQClient:
    """
    Async RabbitMQ client for the GCC scraping pipeline.
    Python scrapers consume jobs from RabbitMQ, process them,
    and publish results back for the Go gRPC service to consume.
    """

    def __init__(self, url: str = "amqp://guest:guest@localhost/"):
        self.url = url
        self._connection = None
        self._channel = None

    async def connect(self):
        """Establish robust connection with automatic reconnection."""
        self._connection = await aio_pika.connect_robust(
            self.url,
            reconnect_interval=5,  # Retry every 5 seconds
        )
        self._channel = await self._connection.channel()
        # Prefetch: process one message at a time per worker
        await self._channel.set_qos(prefetch_count=1)

    async def close(self):
        if self._connection:
            await self._connection.close()

    async def declare_queue(
        self, queue_name: str, durable: bool = True
    ) -> aio_pika.Queue:
        """Declare a queue (idempotent)."""
        return await self._channel.declare_queue(
            queue_name,
            durable=durable,
            arguments={
                "x-message-ttl": 86400000,  # 24h TTL
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": f"{queue_name}.dead",
            }
        )

    async def publish(
        self,
        exchange_name: str,
        routing_key: str,
        body: dict,
        priority: int = 0
    ):
        """Publish a message to an exchange."""
        exchange = await self._channel.declare_exchange(
            exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )

        message = aio_pika.Message(
            body=json.dumps(body).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            priority=priority,
            content_type="application/json",
        )

        await exchange.publish(message, routing_key=routing_key)

    async def consume(
        self,
        queue_name: str,
        handler: Callable[[dict], Awaitable[None]],
    ):
        """
        Consume messages from a queue with manual acknowledgment.
        handler is an async function that processes the message.
        """
        queue = await self.declare_queue(queue_name)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        body = json.loads(message.body.decode())
                        await handler(body)
                        # Message is auto-acked when process() context exits
                    except Exception as e:
                        # Message will be nacked and sent to DLQ
                        print(f"Error processing message: {e}")
                        raise


# Usage: Publishing scrape jobs
async def enqueue_scrape_jobs(creator_ids: list[str]):
    """Enqueue scrape jobs for the worker pool."""
    client = AsyncRabbitMQClient()
    await client.connect()

    for creator_id in creator_ids:
        await client.publish(
            exchange_name="scraping",
            routing_key="jobs.instagram.profile",
            body={
                "creator_id": creator_id,
                "platform": "instagram",
                "job_type": "full_profile_scrape",
                "priority": 1,
            }
        )

    await client.close()


# Usage: Consuming scrape jobs (worker)
async def start_scrape_worker(worker_id: int):
    """Start a single scrape worker."""
    client = AsyncRabbitMQClient()
    await client.connect()

    async def handle_job(job: dict):
        print(f"Worker {worker_id} processing: {job['creator_id']}")
        # Perform the actual scraping
        result = await scrape_creator_profile(
            job["creator_id"], job["platform"]
        )
        # Publish results back
        await client.publish(
            exchange_name="scraping",
            routing_key="results.instagram.profile",
            body=result
        )

    print(f"Worker {worker_id} listening for jobs...")
    await client.consume("scrape_jobs", handle_job)


# Start multiple workers
async def start_worker_pool(num_workers: int = 150):
    """Start a pool of async scrape workers."""
    workers = [
        start_scrape_worker(i) for i in range(num_workers)
    ]
    await asyncio.gather(*workers)
```

```mermaid
graph LR
    subgraph "GCC Scraping Architecture"
        A[Scheduler] -->|Publish Jobs| B[RabbitMQ<br/>scrape_jobs queue]
        B -->|aio-pika consume| C[Python Worker 1]
        B -->|aio-pika consume| D[Python Worker 2]
        B -->|aio-pika consume| E[Python Worker N<br/>150 total]

        C -->|aiohttp| F[Instagram API]
        D -->|aiohttp| G[YouTube API]
        E -->|aiohttp| H[TikTok API]

        C -->|Publish Results| I[RabbitMQ<br/>results queue]
        D -->|Publish Results| I
        E -->|Publish Results| I

        I -->|Go consumer| J[Go gRPC Service]

        C -->|aioboto3| K[S3 Assets]
        D -->|aioboto3| K
        E -->|aioboto3| K
    end

    style B fill:#ff9800
    style I fill:#ff9800
    style J fill:#4caf50
    style K fill:#2196f3
```

---

# Part 4: FastAPI Deep Dive

FastAPI is a modern, high-performance Python web framework built on top of Starlette (ASGI) and Pydantic (data validation). It was the HTTP layer for GCC's internal services.

**Why FastAPI:**

- Async-native (built on ASGI, not WSGI)
- Automatic OpenAPI/Swagger documentation
- Type-safe with Pydantic validation
- Dependency injection system
- Performance comparable to Node.js and Go (when using uvloop)
- First-class support for async/await

## Routing and Path Operations

```python
from fastapi import FastAPI, Path, Query, Body, Header, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

app = FastAPI(
    title="GCC Creator Analytics API",
    description="API for managing creator data and analytics",
    version="2.0.0",
)

# --- Pydantic Models ---
class Platform(str, Enum):
    instagram = "instagram"
    youtube = "youtube"
    tiktok = "tiktok"

class CreatorBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    platform: Platform
    display_name: Optional[str] = None

class CreatorCreate(CreatorBase):
    external_id: str

class CreatorResponse(CreatorBase):
    id: str
    followers_count: int
    media_count: int
    engagement_rate: float
    last_scraped: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2: was orm_mode in v1

class CreatorListResponse(BaseModel):
    creators: List[CreatorResponse]
    total: int
    page: int
    page_size: int


# --- Route Definitions ---

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "service": "gcc-analytics-api"}


@app.get(
    "/creators",
    response_model=CreatorListResponse,
    summary="List creators with filtering and pagination",
    tags=["creators"]
)
async def list_creators(
    platform: Optional[Platform] = Query(None, description="Filter by platform"),
    min_followers: int = Query(0, ge=0, description="Minimum follower count"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("followers_count", description="Sort field"),
    order: str = Query("desc", regex="^(asc|desc)$"),
):
    """
    List creators with filtering, sorting, and pagination.
    Used by the GCC dashboard to browse creator profiles.
    """
    offset = (page - 1) * page_size
    creators, total = await db.get_creators(
        platform=platform,
        min_followers=min_followers,
        offset=offset,
        limit=page_size,
        sort_by=sort_by,
        order=order,
    )
    return CreatorListResponse(
        creators=creators,
        total=total,
        page=page,
        page_size=page_size,
    )


@app.get(
    "/creators/{creator_id}",
    response_model=CreatorResponse,
    tags=["creators"]
)
async def get_creator(
    creator_id: str = Path(..., description="The creator's unique ID"),
):
    """Get a single creator by ID."""
    creator = await db.get_creator(creator_id)
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Creator {creator_id} not found"
        )
    return creator


@app.post(
    "/creators",
    response_model=CreatorResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["creators"]
)
async def create_creator(creator: CreatorCreate = Body(...)):
    """Register a new creator for tracking."""
    existing = await db.get_creator_by_username(
        creator.username, creator.platform
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Creator already exists"
        )
    new_creator = await db.create_creator(creator)
    return new_creator


@app.post(
    "/creators/{creator_id}/scrape",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["scraping"]
)
async def trigger_scrape(
    creator_id: str,
    priority: int = Query(1, ge=1, le=10, description="Job priority"),
):
    """
    Trigger an async scrape job for a creator.
    The job is enqueued to RabbitMQ and processed by scrape workers.
    """
    creator = await db.get_creator(creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    await rabbitmq.publish(
        exchange="scraping",
        routing_key=f"jobs.{creator.platform}.profile",
        body={
            "creator_id": creator_id,
            "platform": creator.platform,
            "job_type": "full_profile_scrape",
            "priority": priority,
        }
    )

    return {"message": "Scrape job enqueued", "creator_id": creator_id}
```

## Dependency Injection

FastAPI's dependency injection system is one of its most powerful features. Dependencies are declared as function parameters and can be nested, cached, and overridden for testing.

```python
from fastapi import Depends, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from functools import lru_cache

# --- Settings (singleton via Depends) ---

class Settings(BaseModel):
    database_url: str
    redis_url: str
    jwt_secret: str
    s3_bucket: str
    rabbitmq_url: str

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()


# --- Database Connection (request-scoped) ---

async def get_db(settings: Settings = Depends(get_settings)):
    """Yield a database session for the duration of the request."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


# --- Redis Connection ---

async def get_redis(settings: Settings = Depends(get_settings)):
    """Get a Redis connection from the pool."""
    redis = await aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True
    )
    try:
        yield redis
    finally:
        await redis.close()


# --- Authentication ---

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    settings: Settings = Depends(get_settings),
    db = Depends(get_db),
):
    """
    Validate JWT token and return the current user.
    Used as a dependency in all authenticated endpoints.
    """
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"]
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_admin(user = Depends(get_current_user)):
    """Dependency that ensures the user has admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return user


# --- Rate Limiter (custom dependency) ---

class RateLimiter:
    """
    Rate limiting dependency using Redis.
    Implements sliding window rate limiting.
    """
    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute

    async def __call__(
        self,
        request: Request,
        redis = Depends(get_redis),
    ):
        client_ip = request.client.host
        key = f"rate_limit:{client_ip}:{request.url.path}"

        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, 60)

        if current > self.rpm:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": "60"}
            )


# --- Using Dependencies in Endpoints ---

@app.get(
    "/analytics/dashboard",
    tags=["analytics"],
    dependencies=[Depends(RateLimiter(requests_per_minute=30))]
)
async def get_dashboard(
    user = Depends(get_current_user),
    db = Depends(get_db),
    redis = Depends(get_redis),
):
    """
    Get dashboard analytics for the current user.
    Demonstrates nested dependency injection:
    - RateLimiter depends on Redis
    - get_current_user depends on Settings and DB
    - This endpoint depends on all of them
    """
    # Check cache first
    cache_key = f"dashboard:{user.id}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # Query database
    analytics = await db.get_dashboard_analytics(user.id)

    # Cache for 5 minutes
    await redis.setex(cache_key, 300, json.dumps(analytics))

    return analytics


@app.delete(
    "/creators/{creator_id}",
    tags=["creators"],
    dependencies=[Depends(require_admin)]
)
async def delete_creator(
    creator_id: str,
    db = Depends(get_db),
):
    """Delete a creator (admin only)."""
    await db.delete_creator(creator_id)
    return {"message": "Creator deleted"}
```

### Dependency Injection Diagram

```mermaid
graph TD
    subgraph "FastAPI Dependency Tree"
        A[GET /analytics/dashboard] --> B[RateLimiter]
        A --> C[get_current_user]
        A --> D[get_db]
        A --> E[get_redis]

        B --> E
        C --> F[HTTPBearer]
        C --> G[get_settings]
        C --> D

        D --> G
        E --> G
    end

    subgraph "Resolution Order"
        H[1. get_settings cached] --> I[2. get_db session]
        I --> J[3. get_redis connection]
        J --> K[4. HTTPBearer extract token]
        K --> L[5. get_current_user validate]
        L --> M[6. RateLimiter check]
        M --> N[7. Execute endpoint handler]
    end

    style A fill:#e1f5fe
    style G fill:#fff9c4
    style D fill:#e8f5e9
    style E fill:#ffcdd2
```

## Pydantic Models and Validation

FastAPI uses Pydantic for request/response validation. Every request body, query parameter, and response is validated automatically.

```python
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class EngagementMetrics(BaseModel):
    """Nested model for engagement data."""
    likes: int = Field(ge=0, description="Total likes")
    comments: int = Field(ge=0, description="Total comments")
    shares: int = Field(ge=0, description="Total shares")
    saves: Optional[int] = Field(None, ge=0, description="Total saves (IG only)")
    engagement_rate: float = Field(ge=0.0, le=100.0)

    @field_validator("engagement_rate", mode="before")
    @classmethod
    def calculate_engagement_rate(cls, v, info):
        """Auto-calculate engagement rate if not provided."""
        if v is not None:
            return v
        data = info.data
        total_interactions = data.get("likes", 0) + data.get("comments", 0)
        # Cannot calculate without followers, return 0
        return 0.0

class CreatorAnalytics(BaseModel):
    """Full analytics response for a creator."""
    creator_id: str
    platform: Platform
    username: str
    followers_count: int = Field(ge=0)
    following_count: int = Field(ge=0)
    post_count: int = Field(ge=0)
    avg_engagement: EngagementMetrics
    recent_posts: List[dict] = Field(default_factory=list, max_length=50)
    growth_rate_30d: float = Field(
        description="Follower growth rate over 30 days as percentage"
    )
    last_scraped: datetime
    data_quality_score: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_data_consistency(self):
        """Validate that the data makes sense."""
        if self.followers_count > 0 and self.post_count == 0:
            # Flag suspicious data
            self.data_quality_score = min(self.data_quality_score, 0.5)
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "creator_id": "creator_123",
                "platform": "instagram",
                "username": "johndoe",
                "followers_count": 150000,
                "following_count": 500,
                "post_count": 1200,
                "avg_engagement": {
                    "likes": 5000,
                    "comments": 200,
                    "shares": 50,
                    "engagement_rate": 3.5,
                },
                "recent_posts": [],
                "growth_rate_30d": 2.3,
                "last_scraped": "2024-01-15T10:30:00Z",
                "data_quality_score": 0.95,
            }
        }
```

## Middleware

```python
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import time
import uuid
import logging

app = FastAPI()

# Built-in middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.goodcreator.co"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Custom middleware
@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    """
    Track request timing and add correlation IDs.
    Used at GCC for observability and debugging.
    """
    # Generate correlation ID
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Record start time
    start_time = time.perf_counter()

    # Process the request
    response: Response = await call_next(request)

    # Calculate duration
    duration_ms = (time.perf_counter() - start_time) * 1000

    # Add headers to response
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

    # Log the request
    logging.info(
        f"{request.method} {request.url.path} "
        f"status={response.status_code} "
        f"duration={duration_ms:.2f}ms "
        f"request_id={request_id}"
    )

    # Alert on slow requests (used for query optimization at GCC)
    if duration_ms > 5000:
        logging.warning(
            f"Slow request: {request.method} {request.url.path} "
            f"took {duration_ms:.2f}ms"
        )

    return response


@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    """Global error handling middleware."""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logging.exception(f"Unhandled error: {e}")
        return Response(
            content=json.dumps({
                "error": "Internal server error",
                "request_id": getattr(request.state, "request_id", "unknown")
            }),
            status_code=500,
            media_type="application/json"
        )
```

## Exception Handlers

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI()

class AppError(Exception):
    """Base application error."""
    def __init__(self, message: str, code: str, status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code

class CreatorNotFoundError(AppError):
    def __init__(self, creator_id: str):
        super().__init__(
            message=f"Creator {creator_id} not found",
            code="CREATOR_NOT_FOUND",
            status_code=404
        )

class RateLimitExceededError(AppError):
    def __init__(self, limit: int, window: str):
        super().__init__(
            message=f"Rate limit of {limit} requests per {window} exceeded",
            code="RATE_LIMIT_EXCEEDED",
            status_code=429
        )

# Register custom exception handlers
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.code,
            "message": exc.message,
            "request_id": getattr(request.state, "request_id", None),
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Custom validation error response."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": [
                {
                    "field": ".".join(str(loc) for loc in err["loc"]),
                    "message": err["msg"],
                    "type": err["type"],
                }
                for err in exc.errors()
            ]
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": exc.detail,
        }
    )
```

## Background Tasks

FastAPI supports running tasks after the response has been sent. Useful for non-critical operations like logging, notifications, and cache invalidation.

```python
from fastapi import BackgroundTasks

async def log_scrape_event(creator_id: str, duration_ms: float):
    """Background task: log scrape event to analytics DB."""
    await analytics_db.insert({
        "event": "scrape_completed",
        "creator_id": creator_id,
        "duration_ms": duration_ms,
        "timestamp": datetime.utcnow(),
    })

async def invalidate_cache(creator_id: str):
    """Background task: invalidate cached data for this creator."""
    cache_keys = [
        f"creator:{creator_id}",
        f"creator:{creator_id}:analytics",
        f"creator:{creator_id}:posts",
    ]
    await redis.delete(*cache_keys)

async def send_notification(user_id: str, message: str):
    """Background task: send notification to user."""
    await notification_service.send(user_id, message)


@app.post("/creators/{creator_id}/scrape")
async def trigger_scrape(
    creator_id: str,
    background_tasks: BackgroundTasks,
    user = Depends(get_current_user),
):
    """
    Trigger a scrape and run post-processing in the background.
    The response is sent immediately; background tasks run after.
    """
    start = time.time()

    # Enqueue scrape job (fast operation)
    await rabbitmq.publish_scrape_job(creator_id)

    duration = (time.time() - start) * 1000

    # These run AFTER the response is sent
    background_tasks.add_task(log_scrape_event, creator_id, duration)
    background_tasks.add_task(invalidate_cache, creator_id)
    background_tasks.add_task(
        send_notification, user.id, f"Scrape started for {creator_id}"
    )

    return {"message": "Scrape job enqueued", "creator_id": creator_id}
```

## FastAPI Request Lifecycle Diagram

```mermaid
sequenceDiagram
    participant C as Client
    participant U as Uvicorn (ASGI Server)
    participant M as Middleware Stack
    participant R as Router
    participant DI as Dependency Injector
    participant H as Handler Function
    participant V as Pydantic Validator
    participant BG as Background Tasks

    C->>U: HTTP Request
    U->>M: ASGI scope + receive + send
    M->>M: Timing Middleware (start timer)
    M->>M: CORS Middleware
    M->>M: GZip Middleware

    M->>R: Route matching
    R->>R: Find matching path operation

    R->>DI: Resolve dependencies
    DI->>DI: get_settings() (cached)
    DI->>DI: get_db() (new session)
    DI->>DI: get_redis() (from pool)
    DI->>DI: get_current_user() (validate JWT)
    DI->>DI: RateLimiter() (check limit)

    DI-->>R: Dependencies resolved

    R->>V: Validate request body/params
    V-->>R: Validated Pydantic model

    R->>H: Call handler with validated args
    H->>H: Business logic
    H-->>R: Return response data

    R->>V: Validate response model
    V-->>R: Serialized response

    R->>BG: Queue background tasks
    R-->>M: Response

    M->>M: Timing Middleware (add headers)
    M-->>U: Final response
    U-->>C: HTTP Response

    BG->>BG: Run background tasks (after response sent)
    BG->>BG: log_scrape_event()
    BG->>BG: invalidate_cache()
    BG->>BG: send_notification()
```

---

# Part 5: FastAPI vs Django vs Flask

## Comprehensive Comparison

| Feature                  | FastAPI                                  | Django                                    | Flask                       |
| ------------------------ | ---------------------------------------- | ----------------------------------------- | --------------------------- |
| **Type**                 | ASGI micro-framework                     | Full-stack framework (batteries-included) | WSGI micro-framework        |
| **Async Support**        | Native async/await                       | Django 3.1+ (partial, async views)        | No native async (use Quart) |
| **Performance**          | Very high (Starlette + uvloop)           | Moderate                                  | Moderate                    |
| **Data Validation**      | Built-in (Pydantic)                      | Django Forms / DRF Serializers            | Manual / Marshmallow        |
| **ORM**                  | None built-in (use SQLAlchemy, Tortoise) | Django ORM (excellent)                    | None (use SQLAlchemy)       |
| **Admin Panel**          | None built-in                            | Django Admin (production-ready)           | None (use Flask-Admin)      |
| **API Docs**             | Auto-generated OpenAPI/Swagger           | DRF has auto-docs                         | Manual / flask-restx        |
| **Dependency Injection** | Built-in, powerful                       | None built-in                             | None built-in               |
| **Authentication**       | Manual / third-party                     | Built-in (sessions, auth)                 | Flask-Login / manual        |
| **Template Engine**      | Jinja2 (optional)                        | Django Templates (built-in)               | Jinja2 (built-in)           |
| **Middleware**           | ASGI middleware                          | Django middleware                         | WSGI middleware             |
| **WebSocket**            | Native support                           | Django Channels (add-on)                  | Flask-SocketIO (add-on)     |
| **Learning Curve**       | Low-Medium                               | High (many conventions)                   | Low                         |
| **Type Safety**          | Excellent (Pydantic + type hints)        | Moderate                                  | Poor                        |
| **Testing**              | pytest + httpx (TestClient)              | Django TestCase                           | pytest + test client        |
| **Community Size**       | Growing fast                             | Very large, mature                        | Large, mature               |
| **Best For**             | APIs, microservices, async workloads     | Full web apps, CMS, monoliths             | Small APIs, prototypes      |

## Performance Benchmarks (Requests/Second)

```
Framework Benchmark (JSON serialization, 4 workers):

FastAPI + uvloop:     ~30,000 req/s
FastAPI (default):    ~22,000 req/s
Flask + Gunicorn:     ~12,000 req/s
Django + Gunicorn:    ~8,000 req/s
Django REST Framework: ~5,000 req/s
Express.js (Node):    ~28,000 req/s
Go net/http:          ~50,000 req/s

Note: Benchmarks vary by hardware, payload size, and use case.
FastAPI's advantage grows with I/O-heavy workloads (database, HTTP calls).
```

## When to Choose Each

### Choose FastAPI when:

- Building **APIs and microservices** (what GCC needed)
- I/O-heavy workloads (scraping, external API calls, database queries)
- Need **async/await** for concurrent operations
- Want automatic API documentation
- Type safety is important
- Building real-time features (WebSocket)

### Choose Django when:

- Building a **full web application** with admin panel
- Need a **built-in ORM** with migrations
- Authentication, sessions, and user management out of the box
- Content management systems
- Team is familiar with Django conventions
- Rapid prototyping of data-driven web apps

### Choose Flask when:

- Building **simple APIs** or prototypes
- Want maximum flexibility (minimal opinions)
- Embedding into larger applications
- Learning web development
- Very small team or solo developer

## Code Comparison: Same Endpoint in All Three

```python
# --- FastAPI ---
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel

app = FastAPI()

class Creator(BaseModel):
    id: str
    username: str
    followers: int

@app.get("/creators/{creator_id}", response_model=Creator)
async def get_creator(creator_id: str):
    creator = await db.get_creator(creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Not found")
    return creator  # Automatically validated and serialized


# --- Django REST Framework ---
from rest_framework import serializers, viewsets, status
from rest_framework.response import Response

class CreatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Creator
        fields = ['id', 'username', 'followers']

class CreatorViewSet(viewsets.ModelViewSet):
    queryset = Creator.objects.all()
    serializer_class = CreatorSerializer

    def retrieve(self, request, pk=None):
        try:
            creator = Creator.objects.get(pk=pk)
        except Creator.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(creator)
        return Response(serializer.data)


# --- Flask ---
from flask import Flask, jsonify, abort

app = Flask(__name__)

@app.route("/creators/<creator_id>", methods=["GET"])
def get_creator(creator_id):
    creator = db.get_creator(creator_id)  # Synchronous!
    if not creator:
        abort(404)
    return jsonify({
        "id": creator.id,
        "username": creator.username,
        "followers": creator.followers,
    })  # Manual serialization, no validation
```

**Why Anshul chose FastAPI at GCC:** The scraping engine was heavily I/O-bound (HTTP requests, S3 uploads, RabbitMQ publishing, database writes). FastAPI's native async support meant a single process with 150 async workers could handle workloads that would have required dozens of Django/Flask processes. The automatic Pydantic validation caught data integrity issues at the API boundary, and the dependency injection system made testing and swapping components trivial.

---

# Part 6: Python Concurrency -- Threading vs Multiprocessing vs AsyncIO

## The GIL Explained

The **Global Interpreter Lock (GIL)** is a mutex in CPython that allows only one thread to execute Python bytecode at a time. Even on a multi-core machine with 16 cores, only one thread runs Python code at any given instant.

**Why does the GIL exist?**

- CPython's memory management (reference counting) is not thread-safe
- The GIL simplifies the implementation of CPython
- It makes single-threaded programs faster (no locking overhead)
- C extensions can release the GIL when doing non-Python work

**What the GIL means in practice:**

```
CPU-bound work (e.g., number crunching):
  Thread 1: [compute]---[GIL wait]---[compute]---[GIL wait]
  Thread 2: [GIL wait]---[compute]---[GIL wait]---[compute]
  Result: SLOWER than single-threaded (GIL contention overhead)

I/O-bound work (e.g., HTTP requests):
  Thread 1: [request]---[waiting for response... GIL released]---[process]
  Thread 2: [request]---[waiting for response... GIL released]---[process]
  Result: FASTER than single-threaded (threads overlap I/O waits)
```

**Key insight:** The GIL is released during I/O operations (network, file, sleep). This is why threading works well for I/O-bound workloads. For CPU-bound work, you need multiprocessing (separate processes, each with its own GIL).

```python
import sys
print(sys.version)

# Check if the GIL is enabled (Python 3.13+ has experimental free-threading)
if hasattr(sys, '_is_gil_enabled'):
    print(f"GIL enabled: {sys._is_gil_enabled()}")
```

### GIL in CPython vs Other Implementations

| Implementation | Has GIL? | Notes                                       |
| -------------- | -------- | ------------------------------------------- |
| CPython        | Yes      | Standard Python, GIL present                |
| PyPy           | Yes      | JIT-compiled, still has GIL                 |
| Jython         | No       | Runs on JVM, true thread parallelism        |
| IronPython     | No       | Runs on .NET CLR                            |
| GraalPython    | No       | Runs on GraalVM                             |
| CPython 3.13+  | Optional | Experimental `--disable-gil` flag (PEP 703) |

## Threading

Python's `threading` module provides OS-level threads. Due to the GIL, they are useful for I/O-bound work but NOT for CPU-bound work.

```python
import threading
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Basic Threading ---
def fetch_url(url: str) -> dict:
    """Synchronous HTTP request (blocks the thread, releases the GIL)."""
    response = requests.get(url, timeout=10)
    return {"url": url, "status": response.status_code, "size": len(response.content)}

# Using threading directly
def threaded_fetch(urls: list[str]) -> list[dict]:
    results = []
    threads = []

    def worker(url):
        result = fetch_url(url)
        results.append(result)

    for url in urls:
        t = threading.Thread(target=worker, args=(url,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return results


# --- ThreadPoolExecutor (preferred) ---
def concurrent_fetch(urls: list[str], max_workers: int = 20) -> list[dict]:
    """
    ThreadPoolExecutor manages a pool of threads.
    Much cleaner than manual thread management.
    """
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_url = {
            executor.submit(fetch_url, url): url
            for url in urls
        }

        # Process results as they complete
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Error fetching {url}: {e}")

    return results


# --- Thread Safety ---
class ThreadSafeCounter:
    """Example of proper thread-safe operations."""
    def __init__(self):
        self._count = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:  # Acquire lock before modifying shared state
            self._count += 1

    @property
    def count(self):
        with self._lock:
            return self._count
```

## Multiprocessing

Python's `multiprocessing` module creates separate OS processes, each with its own Python interpreter and GIL. This achieves true parallelism for CPU-bound work.

```python
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import math

# --- CPU-Bound Work: Perfect for Multiprocessing ---
def compute_heavy(n: int) -> float:
    """CPU-intensive computation: calculate prime factors."""
    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return sum(factors)

def parallel_compute(numbers: list[int]) -> list[float]:
    """Process numbers in parallel across CPU cores."""
    with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        results = list(executor.map(compute_heavy, numbers))
    return results


# --- Real-World Example: Image Processing ---
def process_image(image_path: str) -> dict:
    """
    CPU-bound image processing (PIL operations).
    Each process gets its own GIL, so true parallelism.
    """
    from PIL import Image
    img = Image.open(image_path)
    # Resize, apply filters, extract metadata -- all CPU-bound
    img = img.resize((800, 800))
    img = img.convert("RGB")
    # ... more processing
    return {"path": image_path, "size": img.size}

def batch_process_images(image_paths: list[str]) -> list[dict]:
    """
    Process images in parallel.
    At GCC, we used multiprocessing for CPU-heavy image operations
    before uploading to S3 (the S3 upload itself was async).
    """
    with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        results = list(executor.map(process_image, image_paths))
    return results


# --- Inter-Process Communication ---
def producer(queue: multiprocessing.Queue, items: list):
    """Put items into a shared queue."""
    for item in items:
        queue.put(item)
    queue.put(None)  # Sentinel to signal completion

def consumer(queue: multiprocessing.Queue) -> list:
    """Consume items from a shared queue."""
    results = []
    while True:
        item = queue.get()
        if item is None:
            break
        results.append(process_item(item))
    return results
```

## AsyncIO

AsyncIO provides cooperative multitasking on a single thread. Coroutines explicitly yield control at `await` points. No GIL issues because there is only one thread.

```python
import asyncio
import aiohttp

async def async_fetch(session: aiohttp.ClientSession, url: str) -> dict:
    """Async HTTP request -- no threads needed."""
    async with session.get(url) as response:
        data = await response.read()
        return {"url": url, "status": response.status, "size": len(data)}

async def async_concurrent_fetch(urls: list[str]) -> list[dict]:
    """
    Fetch many URLs concurrently using a single thread.
    This is what GCC used for the scraping engine.
    """
    async with aiohttp.ClientSession() as session:
        tasks = [async_fetch(session, url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]
```

## Comparison Table

| Feature               | Threading                  | Multiprocessing              | AsyncIO                      |
| --------------------- | -------------------------- | ---------------------------- | ---------------------------- |
| **Concurrency Model** | Preemptive (OS-scheduled)  | Preemptive (OS-scheduled)    | Cooperative (explicit yield) |
| **Parallelism**       | No (GIL)                   | Yes (separate processes)     | No (single thread)           |
| **Memory**            | Shared memory              | Separate memory per process  | Shared memory                |
| **Overhead**          | ~8MB per thread            | ~30MB per process            | ~1KB per coroutine           |
| **Max Concurrent**    | ~100-1000 threads          | ~CPU cores                   | ~100,000+ coroutines         |
| **Context Switch**    | OS-level (expensive)       | OS-level (very expensive)    | User-level (cheap)           |
| **Best For**          | I/O-bound + sync libraries | CPU-bound work               | I/O-bound + async libraries  |
| **Communication**     | Shared memory + locks      | Queues, pipes, shared memory | Direct (same thread)         |
| **Debugging**         | Hard (race conditions)     | Moderate (isolated)          | Easy (deterministic)         |
| **Error Handling**    | Complex (thread safety)    | Moderate (process isolation) | Simple (try/except)          |
| **GIL Impact**        | Limits to 1 core           | No impact (separate GILs)    | No impact (1 thread)         |

## When to Use What

```mermaid
graph TD
    A[What kind of work?] --> B{I/O-bound?}
    A --> C{CPU-bound?}
    A --> D{Mixed?}

    B -->|Async libraries available| E[AsyncIO<br/>Best for web scraping,<br/>API calls, database queries]
    B -->|Only sync libraries| F[Threading<br/>ThreadPoolExecutor]

    C --> G[Multiprocessing<br/>ProcessPoolExecutor<br/>Best for number crunching,<br/>image processing]

    D --> H[Hybrid: AsyncIO +<br/>run_in_executor for CPU work]
    D --> I[Hybrid: AsyncIO +<br/>ProcessPoolExecutor for CPU work]

    style E fill:#e8f5e9
    style F fill:#fff9c4
    style G fill:#e3f2fd
    style H fill:#f3e5f5
    style I fill:#f3e5f5
```

### Hybrid Approach (What GCC Used)

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor
from functools import partial

# Create a process pool for CPU-bound work
process_pool = ProcessPoolExecutor(max_workers=4)

def cpu_heavy_image_resize(image_bytes: bytes, width: int, height: int) -> bytes:
    """CPU-bound: runs in a separate process."""
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(image_bytes))
    img = img.resize((width, height), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()

async def process_and_upload_image(
    image_url: str,
    s3_key: str,
    session: aiohttp.ClientSession,
    s3_client
):
    """
    GCC's hybrid approach:
    1. Download image (I/O-bound -> asyncio)
    2. Resize image (CPU-bound -> ProcessPoolExecutor)
    3. Upload to S3 (I/O-bound -> asyncio)
    """
    # Step 1: Async download
    async with session.get(image_url) as response:
        image_bytes = await response.read()

    # Step 2: CPU-bound resize in process pool
    loop = asyncio.get_running_loop()
    resized = await loop.run_in_executor(
        process_pool,
        partial(cpu_heavy_image_resize, image_bytes, 800, 800)
    )

    # Step 3: Async upload to S3
    await s3_client.put_object(
        Bucket="gcc-creator-assets",
        Key=s3_key,
        Body=resized,
        ContentType="image/jpeg"
    )

    return {"key": s3_key, "size": len(resized)}


async def process_image_batch(image_items: list[tuple[str, str]]):
    """Process a batch of images using the hybrid approach."""
    async with aiohttp.ClientSession() as session:
        async with aioboto3.Session().client("s3") as s3:
            tasks = [
                process_and_upload_image(url, key, session, s3)
                for url, key in image_items
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

## Performance Comparison Example

```python
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# I/O-bound benchmark: simulating 100 HTTP requests (each taking 100ms)
async def async_io_benchmark():
    """AsyncIO: 100 I/O tasks, ~100ms each."""
    async def fake_request():
        await asyncio.sleep(0.1)
        return True

    start = time.time()
    tasks = [fake_request() for _ in range(100)]
    await asyncio.gather(*tasks)
    return time.time() - start  # ~0.1 seconds

def threading_io_benchmark():
    """Threading: 100 I/O tasks, ~100ms each."""
    import time as t
    def fake_request():
        t.sleep(0.1)
        return True

    start = time.time()
    with ThreadPoolExecutor(max_workers=100) as executor:
        list(executor.map(lambda _: fake_request(), range(100)))
    return time.time() - start  # ~0.1-0.2 seconds

def sequential_io_benchmark():
    """Sequential: 100 I/O tasks, ~100ms each."""
    import time as t
    start = time.time()
    for _ in range(100):
        t.sleep(0.1)
    return time.time() - start  # ~10 seconds

# Results:
# Sequential:    ~10.0s
# Threading:     ~0.15s (100 threads)
# AsyncIO:       ~0.10s (single thread, 100 coroutines)
# AsyncIO wins because: lower overhead per task, no thread creation/switching cost
```

---

# Part 7: uvloop

## What Is uvloop

`uvloop` is a drop-in replacement for asyncio's default event loop, written in Cython and built on top of **libuv** (the same library that powers Node.js). It makes the asyncio event loop 2-4x faster by replacing Python's pure-Python event loop implementation with a C-level implementation.

### Why uvloop Is Faster

1. **libuv** is a battle-tested, high-performance C library for async I/O
2. The event loop iteration (selector polling, callback scheduling, timer management) is in C, not Python
3. DNS resolution is non-blocking (libuv uses thread pool for DNS)
4. TCP/UDP operations are optimized at the C level
5. Signal handling is more efficient

### Installation and Usage

```python
# Install: pip install uvloop

# Option 1: Set as default event loop policy (recommended for production)
import uvloop
import asyncio

uvloop.install()  # Python 3.12+, simplest approach

# Or for older Python:
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Now asyncio.run() uses uvloop automatically
async def main():
    pass

asyncio.run(main())


# Option 2: Use with FastAPI/Uvicorn (most common in production)
# In your Dockerfile or run command:
# uvicorn app.main:app --loop uvloop --host 0.0.0.0 --port 8000

# Option 3: Create loop explicitly
import uvloop
loop = uvloop.new_event_loop()
asyncio.set_event_loop(loop)
```

### Benchmarks

```
Event Loop Performance (10,000 TCP connections, echo server):

                    Requests/sec    Latency (p99)
uvloop:             ~105,000        0.5ms
asyncio default:    ~35,000         1.8ms
Node.js:            ~95,000         0.6ms
Go net/http:        ~120,000        0.4ms

Improvement: uvloop is ~3x faster than default asyncio
```

```
HTTP Server Performance (FastAPI, JSON response, 4 workers):

                        Requests/sec
Uvicorn + uvloop:       ~30,000
Uvicorn + asyncio:      ~22,000
Gunicorn + Flask:       ~12,000

uvloop gives FastAPI a ~36% throughput boost for free.
```

### When to Use uvloop

| Scenario              | Use uvloop? | Reason                                |
| --------------------- | ----------- | ------------------------------------- |
| FastAPI production    | Yes         | Free 30%+ performance boost           |
| Scraping engine       | Yes         | More concurrent connections           |
| Development/debugging | No          | Default asyncio has better debug mode |
| Windows               | No          | uvloop does not support Windows       |
| CPU-bound workloads   | No benefit  | Event loop is not the bottleneck      |

### uvloop with FastAPI at GCC

```python
# Dockerfile for GCC analytics service
# FROM python:3.11-slim
# RUN pip install fastapi uvicorn[standard] uvloop

# Run with uvloop:
# CMD ["uvicorn", "app.main:app", "--loop", "uvloop",
#       "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# Alternatively, install uvloop programmatically in the app:
from fastapi import FastAPI
import uvloop

uvloop.install()

app = FastAPI(title="GCC Analytics API")

@app.on_event("startup")
async def startup():
    import asyncio
    loop = asyncio.get_running_loop()
    print(f"Event loop: {type(loop).__name__}")  # uvloop.Loop
```

---

# Part 8: Connection Pooling in Async Python

Connection pooling is critical for high-throughput async applications. Without pooling, each coroutine would open a new connection (TCP handshake, TLS negotiation), which is extremely slow at scale.

## Why Connection Pooling Matters

```
Without pooling (150 concurrent scrape workers):
  Worker 1: [TCP handshake 50ms][TLS 100ms][Request][Response][Close]
  Worker 2: [TCP handshake 50ms][TLS 100ms][Request][Response][Close]
  ...
  Worker 150: [TCP handshake 50ms][TLS 100ms][Request][Response][Close]
  Overhead: 150 * 150ms = 22.5 seconds of connection setup!

With pooling (150 concurrent workers, 30 pooled connections):
  Worker 1: [Reuse existing conn][Request][Response][Return to pool]
  Worker 2: [Reuse existing conn][Request][Response][Return to pool]
  ...
  Connection setup: 30 * 150ms = 4.5 seconds (one-time), then zero overhead
```

## aiohttp.ClientSession (HTTP Connection Pool)

```python
import aiohttp
import asyncio

class HTTPConnectionPool:
    """
    Production HTTP connection pool used at GCC.
    aiohttp.ClientSession maintains a connection pool internally via TCPConnector.
    """
    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def start(self):
        """Initialize the connection pool."""
        connector = aiohttp.TCPConnector(
            # Pool settings
            limit=150,              # Max total connections across all hosts
            limit_per_host=30,      # Max connections per host
            keepalive_timeout=30,   # Seconds to keep idle connections alive
            enable_cleanup_closed=True,

            # DNS settings
            ttl_dns_cache=300,      # Cache DNS lookups for 5 minutes
            use_dns_cache=True,

            # SSL settings
            ssl=False,              # Set True for HTTPS (default)

            # TCP settings
            force_close=False,      # Reuse connections (don't close after each request)
        )

        # Timeout configuration
        timeout = aiohttp.ClientTimeout(
            total=30,       # Total timeout for the request
            connect=5,      # Timeout for connection establishment
            sock_read=10,   # Timeout for reading a response
            sock_connect=5, # Timeout for socket connection
        )

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": "GCC-Scraper/2.0"},
        )

    async def stop(self):
        """Close the connection pool gracefully."""
        if self._session:
            await self._session.close()
            # Allow underlying SSL connections to close
            await asyncio.sleep(0.25)

    @property
    def session(self) -> aiohttp.ClientSession:
        if not self._session:
            raise RuntimeError("Connection pool not started")
        return self._session
```

## asyncpg (PostgreSQL Async Connection Pool)

```python
import asyncpg
import asyncio

class AsyncPGPool:
    """
    PostgreSQL connection pool for async Python.
    asyncpg is the fastest PostgreSQL driver for Python.
    """
    def __init__(self, dsn: str, min_size: int = 10, max_size: int = 50):
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self._pool: asyncpg.Pool | None = None

    async def start(self):
        self._pool = await asyncpg.create_pool(
            self.dsn,
            min_size=self.min_size,   # Minimum connections kept open
            max_size=self.max_size,   # Maximum connections allowed
            max_inactive_connection_lifetime=300,  # Close idle connections after 5 min
            command_timeout=30,        # Query timeout
            statement_cache_size=100,  # Cache prepared statements
        )

    async def stop(self):
        if self._pool:
            await self._pool.close()

    async def fetch_one(self, query: str, *args) -> dict | None:
        """Execute a query and return one row."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch_all(self, query: str, *args) -> list[dict]:
        """Execute a query and return all rows."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def execute(self, query: str, *args) -> str:
        """Execute a query (INSERT, UPDATE, DELETE)."""
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def execute_many(self, query: str, args: list) -> None:
        """Execute a query with many sets of arguments (batch insert)."""
        async with self._pool.acquire() as conn:
            await conn.executemany(query, args)


# Usage at GCC: Analytics database queries
async def get_creator_analytics(creator_id: str, pg_pool: AsyncPGPool):
    """Query that was optimized from 30s to 2s at GCC."""
    return await pg_pool.fetch_one(
        """
        SELECT
            c.id, c.username, c.platform,
            c.followers_count, c.engagement_rate,
            COUNT(p.id) as post_count,
            AVG(p.likes) as avg_likes,
            AVG(p.comments) as avg_comments
        FROM creators c
        LEFT JOIN posts p ON p.creator_id = c.id
            AND p.created_at > NOW() - INTERVAL '30 days'
        WHERE c.id = $1
        GROUP BY c.id
        """,
        creator_id
    )
```

## Redis Async Connection Pool (aioredis / redis-py async)

```python
import redis.asyncio as aioredis

class AsyncRedisPool:
    """
    Redis connection pool for caching and rate limiting.
    redis-py 4.2+ has built-in async support.
    """
    def __init__(self, url: str = "redis://localhost:6379"):
        self.url = url
        self._redis: aioredis.Redis | None = None

    async def start(self):
        self._redis = aioredis.from_url(
            self.url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,        # Connection pool size
            socket_timeout=5.0,
            socket_connect_timeout=2.0,
            retry_on_timeout=True,
            health_check_interval=30,  # Periodic health checks
        )

    async def stop(self):
        if self._redis:
            await self._redis.close()

    @property
    def client(self) -> aioredis.Redis:
        if not self._redis:
            raise RuntimeError("Redis pool not started")
        return self._redis

    # Cache operations
    async def get_cached(self, key: str) -> str | None:
        return await self._redis.get(key)

    async def set_cached(self, key: str, value: str, ttl: int = 300):
        await self._redis.setex(key, ttl, value)

    async def invalidate(self, pattern: str):
        """Delete all keys matching a pattern."""
        keys = []
        async for key in self._redis.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            await self._redis.delete(*keys)


# Usage: FastAPI startup/shutdown with connection pools
from fastapi import FastAPI
from contextlib import asynccontextmanager

http_pool = HTTPConnectionPool()
pg_pool = AsyncPGPool("postgresql://user:pass@localhost/gcc_analytics")
redis_pool = AsyncRedisPool("redis://localhost:6379")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage connection pool lifecycle."""
    # Startup: open all pools
    await http_pool.start()
    await pg_pool.start()
    await redis_pool.start()
    print("All connection pools initialized")

    yield  # Application runs here

    # Shutdown: close all pools gracefully
    await http_pool.stop()
    await pg_pool.stop()
    await redis_pool.stop()
    print("All connection pools closed")

app = FastAPI(lifespan=lifespan)
```

---

# Part 9: Rate Limiting

Rate limiting controls how many requests a client can make in a given time window. At GCC, Anshul built a **3-level stacked rate limiter** to avoid getting banned by platform APIs while maximizing scraping throughput.

## Token Bucket Algorithm

The token bucket is the most common rate limiting algorithm. It allows bursts while maintaining an average rate.

**How it works:**

1. A bucket holds tokens up to a maximum capacity
2. Tokens are added at a fixed rate (e.g., 10 tokens/second)
3. Each request consumes one token
4. If the bucket is empty, the request is rejected (or delayed)
5. Unused tokens accumulate up to the capacity (allowing bursts)

```python
import asyncio
import time

class TokenBucket:
    """
    Token bucket rate limiter.
    Allows bursts up to 'capacity', with sustained rate of 'rate' requests/second.
    """
    def __init__(self, rate: float, capacity: int):
        self.rate = rate            # Tokens added per second
        self.capacity = capacity    # Maximum bucket size
        self.tokens = capacity      # Current tokens (start full)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if successful."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill

            # Refill tokens based on elapsed time
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate
            )
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    async def wait_and_acquire(self, tokens: int = 1):
        """Wait until tokens are available, then consume them."""
        while True:
            if await self.acquire(tokens):
                return
            # Calculate wait time for tokens to be available
            async with self._lock:
                wait_time = (tokens - self.tokens) / self.rate
            await asyncio.sleep(wait_time)


# Usage
async def rate_limited_scrape():
    bucket = TokenBucket(rate=10, capacity=30)  # 10 req/s, burst up to 30

    async def scrape_with_limit(creator_id: str):
        await bucket.wait_and_acquire()
        return await scrape_creator(creator_id)

    tasks = [scrape_with_limit(cid) for cid in creator_ids]
    return await asyncio.gather(*tasks)
```

## Sliding Window Algorithm

The sliding window provides smoother rate limiting than fixed windows by tracking requests in a rolling time window.

```python
import asyncio
import time
from collections import deque

class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter.
    Tracks exact timestamps of requests in a rolling window.
    More accurate than fixed window, prevents edge-case bursts.
    """
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Try to make a request. Returns True if within rate limit."""
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds

            # Remove timestamps outside the window
            while self.timestamps and self.timestamps[0] <= cutoff:
                self.timestamps.popleft()

            if len(self.timestamps) < self.max_requests:
                self.timestamps.append(now)
                return True
            return False

    async def wait_and_acquire(self):
        """Wait until a slot is available in the window."""
        while True:
            async with self._lock:
                now = time.monotonic()
                cutoff = now - self.window_seconds

                while self.timestamps and self.timestamps[0] <= cutoff:
                    self.timestamps.popleft()

                if len(self.timestamps) < self.max_requests:
                    self.timestamps.append(now)
                    return

                # Wait until the oldest request exits the window
                wait_time = self.timestamps[0] + self.window_seconds - now
            await asyncio.sleep(wait_time + 0.001)
```

## Leaky Bucket Algorithm

The leaky bucket processes requests at a fixed rate, queuing excess requests. It provides the smoothest output rate.

```python
import asyncio

class LeakyBucket:
    """
    Leaky bucket rate limiter.
    Requests queue up and are processed at a fixed rate.
    Excess requests beyond queue capacity are dropped.
    """
    def __init__(self, rate: float, capacity: int):
        self.rate = rate            # Requests processed per second
        self.capacity = capacity    # Max queue size
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=capacity)
        self._processor_task = None

    async def start(self):
        """Start the leak processor."""
        self._processor_task = asyncio.create_task(self._processor())

    async def stop(self):
        """Stop the leak processor."""
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

    async def _processor(self):
        """Process queued requests at a fixed rate."""
        interval = 1.0 / self.rate
        while True:
            item = await self._queue.get()
            callback, args = item
            await callback(*args)
            self._queue.task_done()
            await asyncio.sleep(interval)

    async def submit(self, callback, *args) -> bool:
        """Submit a request to the leaky bucket. Returns False if queue is full."""
        try:
            self._queue.put_nowait((callback, args))
            return True
        except asyncio.QueueFull:
            return False
```

## Anshul's 3-Level Stacked Rate Limiting

At GCC, Anshul implemented a 3-level stacked rate limiter to comply with platform API limits while maximizing throughput. Each level controlled a different scope.

```python
import asyncio
import time
from typing import Dict

class StackedRateLimiter:
    """
    GCC's 3-level stacked rate limiter for platform API scraping.

    Level 1: Per-endpoint limit (e.g., 30 req/min to /users/{id})
    Level 2: Per-platform limit (e.g., 200 req/min to Instagram overall)
    Level 3: Global limit (e.g., 1000 req/min across ALL platforms)

    A request must pass ALL THREE levels to proceed.
    """

    def __init__(self):
        # Level 1: Per-endpoint limits
        self.endpoint_limiters: Dict[str, SlidingWindowRateLimiter] = {}
        self.endpoint_configs = {
            "instagram/user_profile": (30, 60),    # 30 req/min
            "instagram/user_media": (20, 60),       # 20 req/min
            "instagram/media_details": (60, 60),    # 60 req/min
            "youtube/channel": (100, 60),            # 100 req/min
            "youtube/videos": (50, 60),              # 50 req/min
            "tiktok/user_info": (25, 60),            # 25 req/min
        }

        # Level 2: Per-platform limits
        self.platform_limiters: Dict[str, TokenBucket] = {
            "instagram": TokenBucket(rate=3.0, capacity=200),   # ~180 req/min
            "youtube": TokenBucket(rate=2.5, capacity=150),     # ~150 req/min
            "tiktok": TokenBucket(rate=1.5, capacity=100),      # ~90 req/min
        }

        # Level 3: Global limit
        self.global_limiter = TokenBucket(rate=15.0, capacity=1000)  # ~900 req/min

    def _get_endpoint_limiter(self, endpoint: str) -> SlidingWindowRateLimiter:
        """Get or create an endpoint-specific limiter."""
        if endpoint not in self.endpoint_limiters:
            config = self.endpoint_configs.get(endpoint, (60, 60))
            self.endpoint_limiters[endpoint] = SlidingWindowRateLimiter(*config)
        return self.endpoint_limiters[endpoint]

    async def acquire(self, platform: str, endpoint: str) -> bool:
        """
        Check all 3 levels. Request proceeds only if ALL levels allow it.
        Returns True if the request is allowed.
        """
        # Level 3: Global check (cheapest, check first)
        if not await self.global_limiter.acquire():
            return False

        # Level 2: Platform check
        platform_limiter = self.platform_limiters.get(platform)
        if platform_limiter and not await platform_limiter.acquire():
            return False

        # Level 1: Endpoint check (most granular)
        endpoint_key = f"{platform}/{endpoint}"
        endpoint_limiter = self._get_endpoint_limiter(endpoint_key)
        if not await endpoint_limiter.acquire():
            return False

        return True

    async def wait_and_acquire(self, platform: str, endpoint: str):
        """Wait until all 3 levels allow the request."""
        backoff = 0.1
        max_backoff = 5.0

        while True:
            if await self.acquire(platform, endpoint):
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, max_backoff)

    async def get_status(self) -> dict:
        """Get current rate limiting status (for monitoring dashboard)."""
        return {
            "global": {
                "tokens_remaining": self.global_limiter.tokens,
                "capacity": self.global_limiter.capacity,
            },
            "platforms": {
                platform: {
                    "tokens_remaining": limiter.tokens,
                    "capacity": limiter.capacity,
                }
                for platform, limiter in self.platform_limiters.items()
            }
        }


# Usage in the scraping engine
rate_limiter = StackedRateLimiter()

async def scrape_instagram_profile(creator_id: str):
    """Rate-limited Instagram profile scrape."""
    # Wait until all rate limit levels allow the request
    await rate_limiter.wait_and_acquire("instagram", "user_profile")

    async with http_pool.session.get(
        f"https://api.instagram.com/v1/users/{creator_id}"
    ) as response:
        return await response.json()
```

```mermaid
graph TD
    subgraph "3-Level Stacked Rate Limiter"
        A[Scrape Request] --> B{Level 3: Global Limit<br/>1000 req/min total}
        B -->|Allowed| C{Level 2: Platform Limit<br/>IG: 200 req/min<br/>YT: 150 req/min}
        B -->|Denied| D[Wait + Backoff]

        C -->|Allowed| E{Level 1: Endpoint Limit<br/>user_profile: 30 req/min<br/>user_media: 20 req/min}
        C -->|Denied| D

        E -->|Allowed| F[Execute API Request]
        E -->|Denied| D

        D -->|Retry| A
    end

    style B fill:#ffecb3
    style C fill:#c8e6c9
    style E fill:#bbdefb
    style F fill:#e8f5e9
    style D fill:#ffcdd2
```

---

# Part 10: Pydantic v2

Pydantic v2 (released July 2023) is a complete rewrite with a Rust core (`pydantic-core`), making it 5-50x faster than v1. FastAPI 0.100+ requires Pydantic v2.

## Key Changes from v1 to v2

| Feature             | Pydantic v1                     | Pydantic v2                                             |
| ------------------- | ------------------------------- | ------------------------------------------------------- |
| **Performance**     | Pure Python                     | Rust core (5-50x faster)                                |
| **Validation**      | `@validator`                    | `@field_validator`                                      |
| **Root validators** | `@root_validator`               | `@model_validator`                                      |
| **Config**          | `class Config: orm_mode = True` | `model_config = ConfigDict(from_attributes=True)`       |
| **JSON Schema**     | `schema_extra`                  | `json_schema_extra`                                     |
| **Serialization**   | `.dict()`, `.json()`            | `.model_dump()`, `.model_dump_json()`                   |
| **Parsing**         | `.parse_obj()`                  | `.model_validate()`                                     |
| **Field aliases**   | `Field(alias=...)`              | Same, plus `validation_alias` and `serialization_alias` |
| **Strict mode**     | Not available                   | `model_config = ConfigDict(strict=True)`                |

## BaseModel and Fields

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

class Platform(str, Enum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"

class CreatorProfile(BaseModel):
    """
    Pydantic v2 model for creator profiles.
    Used at GCC for validating scrape results and API responses.
    """
    model_config = ConfigDict(
        from_attributes=True,      # Enable ORM mode (was orm_mode in v1)
        strict=False,              # Allow type coercion
        str_strip_whitespace=True, # Strip whitespace from strings
        validate_default=True,     # Validate default values too
        json_schema_extra={
            "example": {
                "creator_id": "ig_12345",
                "platform": "instagram",
                "username": "creator_name",
                "followers": 150000,
            }
        }
    )

    creator_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique creator identifier"
    )
    platform: Platform
    username: str = Field(..., min_length=1, max_length=50)
    display_name: Optional[str] = Field(None, max_length=100)
    followers: int = Field(ge=0, description="Follower count")
    following: int = Field(ge=0, default=0)
    post_count: int = Field(ge=0, default=0)
    engagement_rate: float = Field(ge=0.0, le=100.0, default=0.0)
    bio: Optional[str] = Field(None, max_length=1000)
    is_verified: bool = False
    profile_url: Optional[str] = None
    last_scraped: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list, max_length=20)
```

## Validators

```python
from pydantic import BaseModel, Field, field_validator, model_validator
import re

class ScrapedCreatorData(BaseModel):
    """Model with comprehensive validation for scraped data."""

    username: str
    platform: Platform
    followers: int
    engagement_rate: float
    email: Optional[str] = None
    website: Optional[str] = None
    raw_bio: Optional[str] = None
    cleaned_bio: Optional[str] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str, info) -> str:
        """Validate username format per platform."""
        v = v.strip().lower()
        if not re.match(r'^[a-z0-9._]+$', v):
            raise ValueError("Username contains invalid characters")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize email."""
        if v is None:
            return None
        v = v.strip().lower()
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("followers", mode="before")
    @classmethod
    def parse_followers(cls, v) -> int:
        """Handle followers as string (e.g., '1.5M', '500K')."""
        if isinstance(v, str):
            v = v.strip().upper()
            multipliers = {"K": 1000, "M": 1000000, "B": 1000000000}
            for suffix, mult in multipliers.items():
                if v.endswith(suffix):
                    return int(float(v[:-1]) * mult)
            return int(v.replace(",", ""))
        return int(v)

    @model_validator(mode="after")
    def validate_data_quality(self):
        """Cross-field validation after all fields are set."""
        # Clean bio from raw bio
        if self.raw_bio and not self.cleaned_bio:
            self.cleaned_bio = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', self.raw_bio)

        # Flag suspicious engagement rates
        if self.followers > 100000 and self.engagement_rate > 20.0:
            # Likely fake engagement
            self.engagement_rate = 0.0

        return self


# Serialization (v2 API)
creator = ScrapedCreatorData(
    username="johndoe",
    platform=Platform.INSTAGRAM,
    followers="1.5M",  # Parsed by validator to 1500000
    engagement_rate=3.5,
    email="john@example.com",
    raw_bio="Creator | Tech \x00 Influencer",
)

# v2 serialization methods
print(creator.model_dump())                          # dict
print(creator.model_dump(exclude_none=True))         # dict without None fields
print(creator.model_dump_json(indent=2))             # JSON string
print(creator.model_dump(include={"username", "followers"}))  # partial dict
print(creator.model_dump(by_alias=True))             # use field aliases

# v2 parsing methods
data = {"username": "janedoe", "platform": "instagram", "followers": "500K", "engagement_rate": 2.1}
creator2 = ScrapedCreatorData.model_validate(data)   # from dict
creator3 = ScrapedCreatorData.model_validate_json('{"username":"janedoe","platform":"instagram","followers":500000,"engagement_rate":2.1}')  # from JSON
```

## Generic Models and Reusable Patterns

```python
from pydantic import BaseModel
from typing import TypeVar, Generic, List, Optional

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    """Reusable paginated response model."""
    items: List[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool

    @model_validator(mode="after")
    def compute_navigation(self):
        total_pages = (self.total + self.page_size - 1) // self.page_size
        self.has_next = self.page < total_pages
        self.has_prev = self.page > 1
        return self

class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""
    success: bool = True
    data: Optional[T] = None
    error: Optional[str] = None
    request_id: Optional[str] = None

# Usage in FastAPI
@app.get("/creators", response_model=APIResponse[PaginatedResponse[CreatorProfile]])
async def list_creators(page: int = 1, page_size: int = 20):
    creators = await db.get_creators(page=page, page_size=page_size)
    return APIResponse(
        data=PaginatedResponse(
            items=creators,
            total=await db.count_creators(),
            page=page,
            page_size=page_size,
            has_next=False,  # computed by validator
            has_prev=False,  # computed by validator
        )
    )
```

---

# Part 11: ASGI vs WSGI

## WSGI (Web Server Gateway Interface)

WSGI is the traditional Python web interface standard (PEP 3333, 2003). It is **synchronous** -- each request is handled by a single thread, and the thread blocks during I/O.

```python
# WSGI application: a callable that takes environ and start_response
def wsgi_app(environ, start_response):
    """Simplest possible WSGI application."""
    status = "200 OK"
    headers = [("Content-Type", "text/plain")]
    start_response(status, headers)
    return [b"Hello, World!"]

# WSGI is synchronous: one request per thread/process
# Gunicorn runs multiple worker processes, each handling one request at a time:
# gunicorn --workers 4 --threads 2 myapp:wsgi_app
# = 4 processes * 2 threads = 8 concurrent requests maximum
```

**WSGI Frameworks:** Flask, Django, Bottle, Pyramid, Falcon (sync mode)

## ASGI (Asynchronous Server Gateway Interface)

ASGI is the async successor to WSGI (2018). It supports **async/await**, **WebSocket**, **HTTP/2**, and **long-lived connections**. It is an evolution, not a replacement -- ASGI can serve WSGI apps.

```python
# ASGI application: an async callable that takes scope, receive, and send
async def asgi_app(scope, receive, send):
    """Simplest possible ASGI application."""
    assert scope["type"] == "http"

    # Receive the request body (if any)
    body = await receive()

    # Send the response
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
            [b"content-type", b"text/plain"],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": b"Hello, World!",
    })

# ASGI is async: thousands of concurrent connections on a single process
# Uvicorn runs async workers:
# uvicorn myapp:asgi_app --workers 4 --loop uvloop
# = 4 processes * ~1000s of coroutines each = massive concurrency
```

**ASGI Frameworks:** FastAPI, Starlette, Django 3.1+ (partial), Quart, Sanic

## Comparison Table

| Feature                         | WSGI                           | ASGI                        |
| ------------------------------- | ------------------------------ | --------------------------- |
| **Protocol**                    | Synchronous                    | Asynchronous                |
| **PEP**                         | PEP 3333 (2003)                | ASGI Spec (2018)            |
| **Concurrency**                 | Thread/process per request     | Coroutine per request       |
| **WebSocket**                   | Not supported                  | Native support              |
| **HTTP/2**                      | Not supported                  | Supported                   |
| **Long-lived connections**      | Not supported                  | Supported (SSE, streaming)  |
| **Server**                      | Gunicorn, uWSGI, mod_wsgi      | Uvicorn, Hypercorn, Daphne  |
| **Max concurrent (per worker)** | ~threads (10-100)              | ~coroutines (1000s-10000s)  |
| **Interface**                   | `app(environ, start_response)` | `app(scope, receive, send)` |
| **Streaming responses**         | Limited                        | Native                      |
| **Background tasks**            | Not natively                   | Supported                   |

## Uvicorn

Uvicorn is the most popular ASGI server. It is a lightning-fast ASGI server built on uvloop and httptools.

```bash
# Basic usage
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Production configuration
uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \                  # Number of worker processes
    --loop uvloop \                # Use uvloop for better performance
    --http httptools \             # Use httptools for faster HTTP parsing
    --access-log \                 # Enable access logging
    --log-level info \
    --limit-concurrency 1000 \     # Max concurrent connections
    --limit-max-requests 10000 \   # Restart workers after N requests
    --timeout-keep-alive 5         # Keep-alive timeout
```

## Gunicorn with Uvicorn Workers

For production, use Gunicorn as the process manager with Uvicorn workers. Gunicorn handles process management (respawning crashed workers, graceful shutdown) while Uvicorn handles async I/O.

```bash
# Production deployment at GCC
gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \                  # Usually 2*CPU_CORES + 1
    --bind 0.0.0.0:8000 \
    --max-requests 10000 \         # Restart workers to prevent memory leaks
    --max-requests-jitter 1000 \   # Add jitter to prevent all workers restarting at once
    --timeout 120 \                # Worker timeout
    --graceful-timeout 30 \        # Graceful shutdown timeout
    --access-logfile - \           # Log to stdout
    --error-logfile -              # Log errors to stdout
```

```python
# gunicorn.conf.py -- Gunicorn configuration file
import multiprocessing

# Worker configuration
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"

# Timeouts
timeout = 120
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Worker recycling (prevent memory leaks)
max_requests = 10000
max_requests_jitter = 1000

# Security
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190
```

```mermaid
graph TD
    subgraph "Production Deployment"
        A[Client Requests] --> B[Nginx / Load Balancer]
        B --> C[Gunicorn Master Process]

        C --> D[Uvicorn Worker 1<br/>uvloop event loop<br/>1000s of coroutines]
        C --> E[Uvicorn Worker 2<br/>uvloop event loop<br/>1000s of coroutines]
        C --> F[Uvicorn Worker 3<br/>uvloop event loop<br/>1000s of coroutines]
        C --> G[Uvicorn Worker 4<br/>uvloop event loop<br/>1000s of coroutines]

        D --> H[PostgreSQL Pool]
        D --> I[Redis Pool]
        E --> H
        E --> I
        F --> H
        F --> I
        G --> H
        G --> I
    end

    style B fill:#e1f5fe
    style C fill:#fff9c4
    style D fill:#e8f5e9
    style E fill:#e8f5e9
    style F fill:#e8f5e9
    style G fill:#e8f5e9
```

---

# Part 12: How Anshul Used It at Good Creator Co

## System Overview

At Good Creator Co (GCC), Anshul built the entire backend data pipeline from scratch using Python with AsyncIO and FastAPI. The system processed **10M+ daily data points** across Instagram and YouTube, handling everything from data collection to analytics serving.

## Component 1: Python Scraping Engine with 150+ Async Workers

**Problem:** GCC needed to continuously collect creator profile data, post metrics, and engagement statistics from Instagram and YouTube. The data had to be fresh (scraped at least daily) for thousands of creators.

**Solution:** An async Python scraping engine using `aiohttp` for HTTP requests, `aio-pika` for RabbitMQ job distribution, and `asyncio.Semaphore` for concurrency control.

**Architecture:**

```
Job Scheduler (cron-based)
    |
    v
RabbitMQ (scrape_jobs queue)
    |
    +---> Worker 1  (asyncio event loop + aiohttp session)
    +---> Worker 2
    +---> ...
    +---> Worker 150
    |
    v
RabbitMQ (scrape_results queue)
    |
    v
Go gRPC Service (data normalization + storage)
```

**Key Technical Decisions:**

- **150 async workers on a single process** rather than 150 threads or processes. Each coroutine consumes approximately 1KB of memory versus 8MB for a thread. Total memory: ~150KB for coroutines versus ~1.2GB for threads.
- **aiohttp with TCPConnector pooling** (limit=150, limit_per_host=30) so we reused TCP/TLS connections across requests instead of establishing new connections for each scrape.
- **Semaphore-based concurrency limiting** to ensure we never exceeded platform API limits. The semaphore was the first line of defense; the stacked rate limiter was the second.
- **aio-pika with prefetch_count=1** so each worker pulled one job at a time from RabbitMQ, ensuring even distribution across workers and preventing fast workers from starving slow ones.
- **Graceful shutdown handling** using `asyncio.CancelledError` to cleanly close connections and acknowledge in-flight messages before shutting down.

**Results:**

- Processed 10M+ data points daily
- Single Python process handled the workload that would have needed 20-30 threaded processes
- Average scrape latency: 200ms per creator (down from 2s with sequential processing)
- Zero platform API bans thanks to the stacked rate limiter

## Component 2: FastAPI Analytics Service

**Problem:** The GCC dashboard needed real-time analytics data: creator rankings, engagement trends, campaign performance. Initial queries took 30 seconds.

**Solution:** A FastAPI service with async database queries, Redis caching, and query optimization.

**Key Technical Decisions:**

- **FastAPI with Pydantic v2** for automatic request/response validation. The Pydantic models caught malformed data before it reached the database.
- **Dependency injection** for database connections, Redis clients, and authentication. This made testing trivial -- we could swap real dependencies with mocks.
- **asyncpg connection pool** (min_size=10, max_size=50) for PostgreSQL. The pool eliminated connection setup overhead for every request.
- **Redis caching with TTL** for frequently accessed analytics. Dashboard data was cached for 5 minutes, reducing database load by 80%.
- **Background tasks** for non-critical operations like logging analytics events, invalidating stale caches, and sending notifications.

**Query Optimization (30s to 2s):**

- Added materialized views for expensive aggregation queries
- Created composite indexes on (creator_id, platform, created_at)
- Moved time-series data to ClickHouse for analytics queries
- Used Redis to cache computed metrics (engagement rates, growth rates)

**Results:**

- Query latency reduced from 30s to 2s (15x improvement)
- Dashboard loaded in under 500ms with Redis cache hits
- Auto-generated OpenAPI docs reduced frontend-backend integration time by 50%

## Component 3: Async S3 Asset Pipeline

**Problem:** 8M images per day needed to be downloaded from platform CDNs and uploaded to S3 with metadata.

**Solution:** Hybrid async/multiprocessing pipeline using `aioboto3` for S3 operations and `ProcessPoolExecutor` for CPU-heavy image processing.

**Architecture:**

```
aiohttp download (I/O-bound, async)
    |
    v
ProcessPoolExecutor resize (CPU-bound, multiprocessing)
    |
    v
aioboto3 S3 upload (I/O-bound, async)
    |
    v
PostgreSQL metadata write (I/O-bound, async)
```

**Key Technical Decisions:**

- **aioboto3 with max_pool_connections=50** for S3 uploads. The connection pool reused existing HTTPS connections to S3, eliminating TLS handshake overhead.
- **ProcessPoolExecutor for image resizing** because PIL/Pillow operations are CPU-bound and would block the event loop. We used `loop.run_in_executor()` to bridge async and sync code.
- **Batch uploads with asyncio.gather()** to upload 50 images concurrently. Each batch completed in ~2 seconds instead of ~100 seconds sequentially.
- **S3 presigned URLs** for serving images to the frontend, avoiding the need to proxy image data through our API.

**Results:**

- 8M images processed daily
- Average throughput: ~93 images/second
- P99 upload latency: under 500ms
- Zero data loss (S3's 99.999999999% durability)

## Component 4: 3-Level Stacked Rate Limiting

**Problem:** Platform APIs had complex rate limits at multiple levels. Exceeding them meant temporary bans, which could halt data collection for hours.

**Solution:** A custom 3-level stacked rate limiter that checked global, per-platform, and per-endpoint limits before every API call.

**The Three Levels:**

1. **Level 1 (Endpoint):** Sliding window rate limiter per API endpoint. Example: Instagram user_profile endpoint limited to 30 requests/minute.
2. **Level 2 (Platform):** Token bucket rate limiter per platform. Example: Instagram overall limited to 200 requests/minute.
3. **Level 3 (Global):** Token bucket for total outbound API calls across all platforms. Limited to 1000 requests/minute.

**Why this order matters:** Checking is done from cheapest to most expensive (global first, endpoint last). If the global limit is hit, we skip the more expensive per-platform and per-endpoint checks.

**Results:**

- Zero API bans after implementing the stacked limiter
- Sustained throughput within 95% of platform limits
- Monitoring dashboard showed real-time token availability per level
- Automatic backoff with exponential wait when limits were approached

## Complete Architecture Diagram

```mermaid
graph TD
    subgraph "GCC Data Pipeline - Anshul's Architecture"
        A[Cron Scheduler] -->|Publish Jobs| B[RabbitMQ<br/>aio-pika]

        subgraph "Python Scraping Engine"
            B --> C[150 Async Workers<br/>asyncio + aiohttp]
            C --> D[3-Level Rate Limiter<br/>Token Bucket + Sliding Window]
            D --> E[Platform APIs<br/>Instagram, YouTube]
        end

        E --> F[Raw Data]

        subgraph "Data Processing"
            F --> G[Pydantic Validation<br/>Data Quality Checks]
            G --> H[ProcessPoolExecutor<br/>Image Resize]
            G --> I[RabbitMQ Results<br/>aio-pika]
        end

        H --> J[S3 Asset Storage<br/>aioboto3, 8M images/day]
        I --> K[Go gRPC Service<br/>Data Normalization]

        subgraph "Storage Layer"
            K --> L[PostgreSQL<br/>asyncpg pool]
            K --> M[ClickHouse<br/>Time-series analytics]
            K --> N[Redis Cache<br/>TTL-based]
        end

        subgraph "FastAPI Analytics Service"
            O[Dashboard Client] --> P[FastAPI<br/>Uvicorn + uvloop]
            P --> Q[Dependency Injection<br/>Auth, DB, Redis, Rate Limit]
            Q --> L
            Q --> M
            Q --> N
        end
    end

    style B fill:#ff9800
    style C fill:#4caf50
    style D fill:#f44336
    style J fill:#2196f3
    style K fill:#4caf50
    style L fill:#3f51b5
    style M fill:#9c27b0
    style N fill:#f44336
    style P fill:#009688
```

---

# Part 13: Interview Q&A

## Q1: What is the difference between concurrency and parallelism?

**Answer:** Concurrency means multiple tasks are **making progress** during overlapping time periods. Parallelism means multiple tasks are **executing simultaneously** on different CPU cores. AsyncIO provides concurrency (one thread juggling many tasks by switching at await points) but not parallelism. Multiprocessing provides both concurrency and parallelism (separate processes on separate cores). At GCC, our 150 async workers were concurrent but not parallel -- a single thread managed all of them by switching between them at I/O wait points.

## Q2: Explain the Python event loop. What happens when you call asyncio.run()?

**Answer:** `asyncio.run()` creates a new event loop, schedules the provided coroutine as a Task, and runs the loop until the task completes. The event loop repeatedly: (1) runs ready callbacks from the call_soon queue, (2) polls for I/O using the OS selector (epoll on Linux, kqueue on macOS), (3) resumes coroutines whose I/O operations are ready, (4) processes expired timers. When all tasks complete, it cancels remaining tasks, shuts down async generators, closes the default executor, and closes the loop. This is the core mechanism -- a single-threaded dispatch loop that monitors file descriptors and schedules coroutine resumption.

## Q3: What is the GIL, and how does it affect async programming?

**Answer:** The Global Interpreter Lock is a mutex in CPython that ensures only one thread executes Python bytecode at any time. It exists because CPython's reference counting memory management is not thread-safe. The GIL does NOT affect async programming because asyncio uses a single thread -- there is no contention. The GIL primarily impacts multi-threaded Python code doing CPU-bound work (threads cannot achieve true parallelism). For I/O-bound work, the GIL is released during system calls, so threading can still be effective. At GCC, we used asyncio for I/O (scraping, database, S3) and multiprocessing for CPU-bound work (image resizing), avoiding GIL issues entirely.

## Q4: What is the difference between asyncio.gather() and asyncio.wait()?

**Answer:** `asyncio.gather(*awaitables)` runs multiple awaitables concurrently and returns their results **in the same order** as the input. It is the most common choice. `asyncio.wait(tasks)` is more flexible: it returns two sets (done, pending), supports a timeout parameter, and supports return_when conditions (ALL_COMPLETED, FIRST_COMPLETED, FIRST_EXCEPTION). I used `gather` for batch scraping (where I wanted all results in order) and `wait` with timeout for operations that needed a hard deadline (cancel pending tasks if they did not finish in 30 seconds).

## Q5: How does FastAPI's dependency injection work?

**Answer:** FastAPI inspects the type hints and default values of endpoint function parameters. When a parameter has `Depends(some_function)` as its default, FastAPI calls that function (or coroutine) before the endpoint handler, passes the result as the argument, and handles cleanup (for generator dependencies using `yield`). Dependencies can be nested -- a dependency can itself declare dependencies via Depends. FastAPI resolves the entire dependency tree, caches shared dependencies within a request, and executes them in the correct order. At GCC, we used this for database sessions (yield-based, cleaned up after request), Redis connections, authentication (JWT validation), and rate limiting (custom callable class).

## Q6: Why did you choose FastAPI over Django or Flask?

**Answer:** Three reasons. First, **async-native**: our workload was heavily I/O-bound (database queries, Redis lookups, RabbitMQ operations), and FastAPI's native async/await support meant we could handle hundreds of concurrent requests on a single process. Django's async support was partial at the time, and Flask is entirely synchronous. Second, **Pydantic validation**: automatic request/response validation caught data integrity issues at the API boundary, which was critical when serving scraped data that could be inconsistent. Third, **auto-generated API documentation**: the OpenAPI/Swagger docs halved the integration time with the frontend team. We did not need Django's ORM (we used asyncpg directly) or admin panel, so Django's batteries-included philosophy would have been unnecessary overhead.

## Q7: Explain connection pooling in async Python. Why is it important?

**Answer:** Connection pooling maintains a set of pre-established connections that are reused across requests instead of creating a new connection for each operation. In async Python, this is critical because establishing a connection involves TCP handshake (1 RTT), TLS negotiation (2 RTTs), and protocol setup -- about 150ms of overhead per connection. With 150 concurrent workers, that is 22.5 seconds of cumulative connection setup without pooling. With a pool of 30 connections, setup happens once, and workers borrow and return connections as needed. At GCC, we used aiohttp.TCPConnector (limit=150 total, limit_per_host=30), asyncpg.Pool (min_size=10, max_size=50), and redis-py's async connection pool (max_connections=50).

## Q8: Describe your 3-level stacked rate limiter. Why three levels?

**Answer:** Three levels because platform APIs enforce limits at multiple scopes. Level 1 (endpoint): specific API endpoints have individual limits (e.g., Instagram user_profile at 30 req/min). Level 2 (platform): each platform has an overall API call budget (e.g., Instagram at 200 req/min total). Level 3 (global): our infrastructure has a total outbound request budget. A request must pass ALL three levels. We check cheapest first (global token bucket) to fail fast. The stacked approach prevents scenarios where you are within the per-endpoint limit but exceed the platform limit, or within both but exceed global capacity. I used sliding window for endpoint limits (precise, prevents edge-case bursts) and token bucket for platform/global limits (allows controlled bursts).

## Q9: What is the difference between ASGI and WSGI?

**Answer:** WSGI (2003) is synchronous: the interface is `app(environ, start_response)` and each request blocks a thread. ASGI (2018) is asynchronous: the interface is `async app(scope, receive, send)` where scope describes the connection, receive/send are async callables for bidirectional communication. ASGI supports WebSocket, HTTP/2, and long-lived connections natively because the async interface can hold open connections without blocking threads. In practice, a WSGI server like Gunicorn handles concurrency with 4 processes x 2 threads = 8 concurrent requests. An ASGI server like Uvicorn handles 4 processes x thousands of coroutines = massive concurrency. At GCC, we ran FastAPI on Gunicorn with Uvicorn workers to get Gunicorn's process management with Uvicorn's async performance.

## Q10: How did you reduce query latency from 30s to 2s?

**Answer:** Four strategies. First, **materialized views** for expensive aggregation queries that joined creators with their posts and computed engagement metrics -- precomputed every 5 minutes. Second, **composite indexes** on (creator_id, platform, created_at) to eliminate full table scans on the posts table. Third, **ClickHouse for time-series analytics** -- we moved historical metric data from PostgreSQL to ClickHouse, which is optimized for column-oriented analytics queries. Fourth, **Redis caching** with 5-minute TTL for dashboard data, so repeated queries for the same creator or time range hit cache instead of database. The cache alone reduced database load by 80%.

## Q11: What happens when a coroutine hits an await? Walk through the entire process.

**Answer:** When a coroutine hits `await some_operation()`: (1) The coroutine is suspended -- its execution frame is saved including local variables and instruction pointer. (2) Control returns to the event loop. (3) The event loop registers the I/O operation's file descriptor with the OS selector (epoll/kqueue). (4) The event loop continues running other ready coroutines or polls the selector for other ready operations. (5) When the OS signals that the file descriptor is ready (data available, write buffer empty), the selector returns it. (6) The event loop creates a callback to resume the suspended coroutine. (7) On the next loop iteration, the callback runs, the coroutine's frame is restored, and execution continues from the line after the await.

## Q12: What is uvloop, and when should you use it?

**Answer:** uvloop is a drop-in replacement for asyncio's default event loop, written in Cython on top of libuv (the same C library powering Node.js). It replaces Python-level event loop operations with C-level implementations, making it 2-4x faster. The performance gain comes from faster I/O polling, callback scheduling, and timer management -- all in C instead of Python. Use it in production for any async Python application (FastAPI, aiohttp). Do not use it in development (asyncio's debug mode is more helpful), on Windows (not supported), or for CPU-bound workloads (the event loop is not the bottleneck). At GCC, adding `--loop uvloop` to our Uvicorn command gave us a 30%+ throughput boost for free.

## Q13: How do you handle errors in an async worker pool? What happens if one worker fails?

**Answer:** Using `asyncio.gather(*tasks, return_exceptions=True)`. With `return_exceptions=True`, a failed task returns its exception object in the results list instead of propagating it and cancelling other tasks. We then iterate through results, separate successes from failures, log failures, and optionally retry them. For the scraping engine specifically: each worker consumed from RabbitMQ with manual acknowledgment. If a worker threw an exception, the message was nacked and sent to a dead-letter queue for later investigation. The worker itself was wrapped in a try/except that caught everything except CancelledError, logged the error, and continued processing the next message.

## Q14: Explain the difference between a Task and a Coroutine in asyncio.

**Answer:** A coroutine is a function defined with `async def`. Calling it returns a coroutine object but does NOT start execution -- it is lazy. A Task is a wrapper around a coroutine that schedules it on the event loop for execution. Creating a Task with `asyncio.create_task(coro)` starts the coroutine running immediately (on the next event loop iteration). Tasks are a subclass of Future, so they have additional capabilities: result tracking, cancellation, done callbacks. The key practical difference: `await coro1(); await coro2()` runs sequentially (coro2 starts after coro1 finishes), while `t1 = create_task(coro1); t2 = create_task(coro2); await t1; await t2` runs concurrently (both start immediately, await collects results).

## Q15: How did you bridge sync and async code at GCC?

**Answer:** Two patterns. For I/O-bound sync code (legacy libraries without async support), we used `loop.run_in_executor(None, sync_function, args)` which runs the function in a ThreadPoolExecutor and returns a Future that can be awaited. The GIL is released during I/O, so this works well. For CPU-bound sync code (image processing with PIL), we used `loop.run_in_executor(process_pool, cpu_function, args)` with a ProcessPoolExecutor to achieve true parallelism. The key insight is that `run_in_executor` returns an awaitable Future, so it integrates seamlessly into async code. Our image pipeline was a perfect example: async download, sync resize in process pool via run_in_executor, then async upload to S3.

## Q16: What is Pydantic v2's biggest improvement, and how did it affect your system?

**Answer:** The biggest improvement is the Rust core (`pydantic-core`), which makes validation 5-50x faster than v1. For our FastAPI analytics service processing thousands of requests per second, each request involved validating both the incoming request and the outgoing response through Pydantic models. With v1, Pydantic validation was a measurable portion of request latency (1-5ms per validation). With v2, it dropped to microseconds. The API changes (field_validator instead of validator, model_dump instead of dict, model_validate instead of parse_obj) required a migration effort, but the ConfigDict and from_attributes were cleaner than the old class Config approach.

## Q17: If you had to scrape 10M data points daily but could only use synchronous Python (no asyncio), how would you architect it?

**Answer:** I would use multiprocessing with a process pool. Each process would have its own Python interpreter and GIL, so they can truly run in parallel. Using ProcessPoolExecutor with, say, 16 workers (one per CPU core), each worker would use the `requests` library with Session (connection pooling) and ThreadPoolExecutor internally for concurrent I/O within each process. So the architecture would be: 16 processes x 20 threads each = 320 concurrent HTTP requests. This is less efficient than asyncio (320 concurrent vs. thousands of coroutines, and much higher memory usage), but it works. The rate limiter would need to use Redis or shared memory (multiprocessing.Manager) instead of in-process data structures, since each process has its own memory space. RabbitMQ would still distribute jobs, with each process consuming independently.

## Q18: What are the common pitfalls of async Python programming?

**Answer:** (1) **Blocking the event loop** -- calling a sync function without run_in_executor freezes ALL coroutines. Common culprits: `time.sleep()` instead of `asyncio.sleep()`, synchronous database drivers, file I/O without aiofiles. (2) **Forgetting to await** -- calling `async_func()` without `await` returns a coroutine object that is never executed, often without any error. Python 3.12+ warns about this. (3) **Creating tasks without keeping references** -- tasks can be garbage collected if you do not store a reference. Use `task = create_task(coro)` and keep `task` alive. (4) **Not handling CancelledError** -- during shutdown, tasks receive CancelledError. If you catch it and do not re-raise, the task never actually cancels. (5) **Mixing sync and async code incorrectly** -- calling `asyncio.run()` inside an already-running event loop raises RuntimeError.

---

**End of Study Guide**
