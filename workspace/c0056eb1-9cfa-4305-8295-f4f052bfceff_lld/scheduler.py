import threading
import heapq
import time
import itertools
from enum import Enum


class TaskType(Enum):
    ONE_TIME = "ONE_TIME"
    FIXED_INTERVAL = "FIXED_INTERVAL"


class TaskStatus(Enum):
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class ScheduledTask:
    """A unit of work plus its scheduling metadata. Never collapse this to a bare callable."""
    def __init__(self, task_id, runnable, task_type, next_run_at, interval=None):
        self.task_id = task_id
        self.runnable = runnable
        self.task_type = task_type
        self.next_run_at = next_run_at          # absolute epoch seconds
        self.interval = interval                # seconds, for FIXED_INTERVAL
        self.status = TaskStatus.SCHEDULED
        self.lock = threading.Lock()

    def is_recurring(self):
        return self.task_type == TaskType.FIXED_INTERVAL


class TaskScheduler:
    """
    In-memory scheduler.
    - A delay queue (min-heap by next_run_at) is the orchestrator's source of truth.
    - One dispatcher thread waits until the earliest task is due, then hands it to a worker pool.
    - A fixed pool of N worker threads pulls ready tasks off a ready-queue and executes them.
    """
    def __init__(self, num_workers=4, time_fn=time.time):
        if num_workers < 1:
            raise ValueError("num_workers must be >= 1")
        self._time = time_fn
        self._heap = []                          # (next_run_at, seq, task)
        self._counter = itertools.count()        # tie-breaker -> stable, avoids comparing tasks
        self._tasks = {}                         # task_id -> ScheduledTask (registry)
        self._cv = threading.Condition()         # guards heap + tasks, signals dispatcher
        self._ready = []                         # list used as a queue of due tasks
        self._ready_cv = threading.Condition()   # guards ready queue
        self._shutdown = False
        self._id_gen = itertools.count(1)

        self._dispatcher = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._workers = [threading.Thread(target=self._worker_loop, daemon=True)
                         for _ in range(num_workers)]
        self._dispatcher.start()
        for w in self._workers:
            w.start()

    # ---------- public API ----------
    def schedule(self, task, exec_time):
        """Run `task` once at absolute epoch `exec_time`."""
        if task is None:
            raise ValueError("task must not be None")
        if exec_time is None:
            raise ValueError("exec_time must not be None")
        st = ScheduledTask(next(self._id_gen), task, TaskType.ONE_TIME, exec_time)
        return self._add(st)

    def schedule_after(self, task, delay_seconds):
        return self.schedule(task, self._time() + delay_seconds)

    def schedule_at_fixed_interval(self, task, interval):
        """First run immediate, then every `interval` seconds after completion."""
        if task is None:
            raise ValueError("task must not be None")
        if interval is None or interval <= 0:
            raise ValueError("interval must be > 0")
        st = ScheduledTask(next(self._id_gen), task, TaskType.FIXED_INTERVAL,
                           self._time(), interval)
        return self._add(st)

    def cancel(self, task_id):
        with self._cv:
            st = self._tasks.get(task_id)
            if st is None:
                return False
            with st.lock:
                if st.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
                    return False
                st.status = TaskStatus.CANCELLED
            return True

    def shutdown(self):
        with self._cv:
            self._shutdown = True
            self._cv.notify_all()
        with self._ready_cv:
            self._ready_cv.notify_all()

    # ---------- internals ----------
    def _add(self, st):
        with self._cv:
            if self._shutdown:
                raise RuntimeError("scheduler is shut down")
            self._tasks[st.task_id] = st
            heapq.heappush(self._heap, (st.next_run_at, next(self._counter), st))
            self._cv.notify_all()   # wake dispatcher: a new (possibly earlier) task arrived
        return st.task_id

    def _dispatch_loop(self):
        while True:
            with self._cv:
                while not self._shutdown and not self._heap:
                    self._cv.wait()
                if self._shutdown:
                    return
                run_at, _, st = self._heap[0]
                now = self._time()
                if run_at > now:
                    # wait until due OR until a new/earlier task or shutdown wakes us
                    self._cv.wait(timeout=run_at - now)
                    continue
                heapq.heappop(self._heap)
                with st.lock:
                    if st.status == TaskStatus.CANCELLED:
                        continue
            # hand the due task to the worker pool
            with self._ready_cv:
                self._ready.append(st)
                self._ready_cv.notify()

    def _worker_loop(self):
        while True:
            with self._ready_cv:
                while not self._shutdown and not self._ready:
                    self._ready_cv.wait()
                if self._shutdown and not self._ready:
                    return
                st = self._ready.pop(0)
            self._execute(st)

    def _execute(self, st):
        with st.lock:
            if st.status == TaskStatus.CANCELLED:
                return
            st.status = TaskStatus.RUNNING
        try:
            st.runnable()
            failed = False
        except Exception:
            failed = True
        # decide next outcome
        with st.lock:
            if st.status == TaskStatus.CANCELLED:
                return
            if st.is_recurring() and not failed:
                st.status = TaskStatus.SCHEDULED
                st.next_run_at = self._time() + st.interval
                reschedule = True
            else:
                st.status = TaskStatus.FAILED if failed else TaskStatus.COMPLETED
                reschedule = False
        if reschedule:
            with self._cv:
                if not self._shutdown:
                    heapq.heappush(self._heap, (st.next_run_at, next(self._counter), st))
                    self._cv.notify_all()


if __name__ == "__main__":
    results = []
    rlock = threading.Lock()

    def make(tag):
        def run():
            with rlock:
                results.append(tag)
        return run

    sch = TaskScheduler(num_workers=3)

    # 1. validation / boundary
    try:
        sch.schedule(None, time.time()); assert False
    except ValueError: pass
    try:
        sch.schedule_at_fixed_interval(make("x"), 0); assert False
    except ValueError: pass

    # 2. one-time, out-of-order submission (later first, earlier second)
    sch.schedule_after(make("later"), 0.40)
    sch.schedule_after(make("earlier"), 0.15)

    # 3. immediate task
    sch.schedule(make("now"), time.time())

    # 4. fixed interval: immediate + repeats
    fid = sch.schedule_at_fixed_interval(make("tick"), 0.2)

    # 5. cancel before it runs
    cid = sch.schedule_after(make("cancelled"), 0.3)
    assert sch.cancel(cid) is True
    assert sch.cancel(99999) is False        # unknown id

    # 6. a failing task must not kill the worker
    def boom():
        raise RuntimeError("boom")
    sch.schedule(boom, time.time())

    time.sleep(0.75)
    sch.cancel(fid)                          # stop the recurring task
    time.sleep(0.1)

    with rlock:
        snap = list(results)
    print("results:", snap)
    assert "cancelled" not in snap                       # cancel worked
    assert snap.index("earlier") < snap.index("later")   # ordering by time, not submission
    assert snap.count("tick") >= 2                        # recurring fired multiple times
    assert "now" in snap
    sch.shutdown()
    print("ALL ASSERTIONS PASSED")
