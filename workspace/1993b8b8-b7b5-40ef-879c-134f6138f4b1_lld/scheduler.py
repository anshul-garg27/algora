import heapq
import threading
import time
import itertools
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Optional


class TaskType(Enum):
    ONE_SHOT = "ONE_SHOT"
    FIXED_INTERVAL = "FIXED_INTERVAL"


class TaskStatus(Enum):
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


_counter = itertools.count()


@dataclass(order=True)
class ScheduledTask:
    # ordering key first so heapq orders by (next_run_time, seq)
    next_run_time: float
    seq: int = field(compare=True)
    task_id: int = field(compare=False, default=0)
    fn: Callable = field(compare=False, default=None)
    task_type: TaskType = field(compare=False, default=TaskType.ONE_SHOT)
    interval: Optional[float] = field(compare=False, default=None)
    status: TaskStatus = field(compare=False, default=TaskStatus.SCHEDULED)
    cancelled: bool = field(compare=False, default=False)


class TaskScheduler:
    """In-memory scheduler. A dispatcher thread waits until the earliest task
    is due, then hands it to a fixed pool of worker threads. Fixed-interval
    tasks are re-enqueued AFTER they finish (completion-based interval)."""

    def __init__(self, num_workers: int = 4, clock=time.time):
        if num_workers < 1:
            raise ValueError("num_workers must be >= 1")
        self._clock = clock
        self._heap = []                      # min-heap of ScheduledTask by (time, seq)
        self._registry = {}                  # task_id -> ScheduledTask (the orchestrator's truth)
        self._ready = []                      # FIFO list of tasks due to run now
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)        # signals dispatcher (heap changes)
        self._ready_cond = threading.Condition(threading.Lock())  # signals workers (ready queue)
        self._id_gen = itertools.count(1)
        self._shutdown = False

        self._workers = [threading.Thread(target=self._worker_loop, daemon=True,
                                           name=f"worker-{i}") for i in range(num_workers)]
        self._dispatcher = threading.Thread(target=self._dispatch_loop, daemon=True,
                                            name="dispatcher")
        for w in self._workers:
            w.start()
        self._dispatcher.start()

    # ---------- public API ----------
    def schedule(self, task: Callable, exec_time: float) -> int:
        """Run `task` once at absolute epoch `exec_time`."""
        if task is None:
            raise ValueError("task must not be None")
        if not callable(task):
            raise ValueError("task must be callable")
        st = ScheduledTask(next_run_time=exec_time, seq=next(_counter),
                           task_id=next(self._id_gen), fn=task,
                           task_type=TaskType.ONE_SHOT)
        self._enqueue(st)
        return st.task_id

    def schedule_after(self, task: Callable, delay_seconds: float) -> int:
        return self.schedule(task, self._clock() + delay_seconds)

    def schedule_at_fixed_interval(self, task: Callable, interval: float) -> int:
        """First run immediately; each subsequent run `interval` s after the
        previous run COMPLETES."""
        if task is None or not callable(task):
            raise ValueError("task must be callable")
        if interval <= 0:
            raise ValueError("interval must be > 0")
        st = ScheduledTask(next_run_time=self._clock(), seq=next(_counter),
                           task_id=next(self._id_gen), fn=task,
                           task_type=TaskType.FIXED_INTERVAL, interval=interval)
        self._enqueue(st)
        return st.task_id

    def cancel(self, task_id: int) -> bool:
        with self._lock:
            st = self._registry.get(task_id)
            if st is None or st.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
                return False
            st.cancelled = True
            if st.status == TaskStatus.SCHEDULED:
                st.status = TaskStatus.CANCELLED
            return True

    def get_status(self, task_id: int) -> Optional[TaskStatus]:
        with self._lock:
            st = self._registry.get(task_id)
            return st.status if st else None

    def shutdown(self):
        with self._cond:
            self._shutdown = True
            self._cond.notify_all()
        with self._ready_cond:
            self._ready_cond.notify_all()

    # ---------- internals ----------
    def _enqueue(self, st: ScheduledTask):
        with self._cond:
            if self._shutdown:
                raise RuntimeError("scheduler is shut down")
            self._registry[st.task_id] = st
            heapq.heappush(self._heap, st)
            self._cond.notify()      # wake dispatcher: earliest may have changed

    def _dispatch_loop(self):
        while True:
            with self._cond:
                while not self._shutdown and not self._heap:
                    self._cond.wait()
                if self._shutdown and not self._heap:
                    return
                now = self._clock()
                head = self._heap[0]
                if head.cancelled:
                    heapq.heappop(self._heap)
                    continue
                wait = head.next_run_time - now
                if wait > 0:
                    # sleep until due OR until a closer task arrives / shutdown
                    self._cond.wait(timeout=wait)
                    continue
                st = heapq.heappop(self._heap)
                if st.cancelled:
                    continue
            # hand off to workers
            with self._ready_cond:
                self._ready.append(st)
                self._ready_cond.notify()

    def _worker_loop(self):
        while True:
            with self._ready_cond:
                while not self._ready and not self._shutdown:
                    self._ready_cond.wait()
                if self._shutdown and not self._ready:
                    return
                st = self._ready.pop(0)
            self._run_task(st)

    def _run_task(self, st: ScheduledTask):
        with self._lock:
            if st.cancelled:
                st.status = TaskStatus.CANCELLED
                return
            st.status = TaskStatus.RUNNING
        try:
            st.fn()
            failed = False
        except Exception:
            failed = True
        with self._lock:
            if st.task_type == TaskType.FIXED_INTERVAL and not st.cancelled:
                # re-schedule interval after completion
                st.status = TaskStatus.SCHEDULED
                st.next_run_time = self._clock() + st.interval
                st.seq = next(_counter)
            else:
                st.status = TaskStatus.FAILED if failed else TaskStatus.COMPLETED
        if st.task_type == TaskType.FIXED_INTERVAL and not st.cancelled:
            self._enqueue(st)


# ----------------- driver / tests -----------------
if __name__ == "__main__":
    results = []
    rlock = threading.Lock()

    def record(tag):
        def _f():
            with rlock:
                results.append((tag, time.time()))
        return _f

    sched = TaskScheduler(num_workers=3)
    t0 = time.time()

    # 1. validation / boundary
    try:
        sched.schedule(None, t0)
        assert False
    except ValueError:
        pass
    try:
        sched.schedule_at_fixed_interval(record("x"), 0)
        assert False
    except ValueError:
        pass
    try:
        TaskScheduler(num_workers=0)
        assert False
    except ValueError:
        pass

    # 2. one-shot ordering: schedule out of order, expect time order
    sched.schedule(record("late"), t0 + 0.6)
    sched.schedule(record("early"), t0 + 0.2)
    sched.schedule(record("mid"), t0 + 0.4)

    # 3. past-time task should run ASAP
    sched.schedule(record("past"), t0 - 100)

    # 4. cancellation before run
    cid = sched.schedule(record("cancelled"), t0 + 0.5)
    assert sched.cancel(cid) is True
    assert sched.cancel(cid) is False          # double cancel
    assert sched.cancel(999999) is False       # unknown id

    # 5. fixed interval: immediate first run then repeats
    iid = sched.schedule_at_fixed_interval(record("interval"), 0.25)

    time.sleep(1.2)
    sched.cancel(iid)
    time.sleep(0.3)

    tags = [t for t, _ in results]
    print("execution order:", tags)

    assert "cancelled" not in tags, "cancelled task must not run"
    assert "past" in tags
    order = [t for t in tags if t in ("early", "mid", "late")]
    assert order == ["early", "mid", "late"], order
    interval_runs = tags.count("interval")
    assert interval_runs >= 3, interval_runs        # immediate + repeats
    assert sched.get_status(cid) == TaskStatus.CANCELLED
    print("interval runs:", interval_runs)
    print("ALL ASSERTIONS PASSED")
    sched.shutdown()
