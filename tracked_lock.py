from __future__ import annotations

import threading
from collections import defaultdict


class DeadlockDetected(RuntimeError):
    pass


class _WaitGraphTracker:
    def __init__(self) -> None:
        self.guard = threading.RLock()
        self.owners: dict["TrackedLock", int] = {}
        self.waiting: dict[int, "TrackedLock"] = {}
        self.names: dict[int, str] = {}

    def _thread_name(self, tid: int) -> str:
        return self.names.get(tid, f"thread-{tid}")

    def _graph(self) -> dict[int, set[int]]:
        graph: dict[int, set[int]] = defaultdict(set)
        for waiter, lock in self.waiting.items():
            owner = self.owners.get(lock)
            if owner is not None:
                graph[waiter].add(owner)
        return dict(graph)

    def _cycle_from(self, start: int) -> list[int] | None:
        graph = self._graph()
        color: dict[int, int] = {}
        stack: list[int] = []
        positions: dict[int, int] = {}

        def dfs(node: int) -> list[int] | None:
            color[node] = 1
            positions[node] = len(stack)
            stack.append(node)
            for nxt in graph.get(node, ()):
                state = color.get(nxt, 0)
                if state == 0:
                    cycle = dfs(nxt)
                    if cycle:
                        return cycle
                elif state == 1:
                    return stack[positions[nxt] :] + [nxt]
            stack.pop()
            positions.pop(node, None)
            color[node] = 2
            return None

        return dfs(start)

    def start_wait(self, lock: "TrackedLock") -> None:
        tid = threading.get_ident()
        with self.guard:
            self.names[tid] = threading.current_thread().name
            self.waiting[tid] = lock
            cycle = self._cycle_from(tid)
            if cycle:
                self.waiting.pop(tid, None)
                names = [self._thread_name(x) for x in cycle]
                raise DeadlockDetected("wait-for cycle detected: " + " -> ".join(names))

    def acquired(self, lock: "TrackedLock") -> None:
        tid = threading.get_ident()
        with self.guard:
            self.names[tid] = threading.current_thread().name
            self.waiting.pop(tid, None)
            self.owners[lock] = tid

    def cancel_wait(self) -> None:
        tid = threading.get_ident()
        with self.guard:
            self.waiting.pop(tid, None)

    def released(self, lock: "TrackedLock") -> None:
        tid = threading.get_ident()
        with self.guard:
            owner = self.owners.get(lock)
            if owner != tid:
                raise RuntimeError(f"{lock.name} is not owned by current thread")
            self.owners.pop(lock, None)


_TRACKER = _WaitGraphTracker()


class TrackedLock:
    """threading.Lock wrapper that refuses an acquire creating a wait-for cycle."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._lock = threading.Lock()

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        # Fast path: if it is free, acquire it without creating a wait edge.
        if self._lock.acquire(blocking=False):
            _TRACKER.acquired(self)
            return True
        if not blocking:
            return False

        _TRACKER.start_wait(self)
        try:
            if timeout == -1:
                acquired = self._lock.acquire()
            else:
                acquired = self._lock.acquire(timeout=timeout)
            if acquired:
                _TRACKER.acquired(self)
            else:
                _TRACKER.cancel_wait()
            return acquired
        except BaseException:
            _TRACKER.cancel_wait()
            raise

    def release(self) -> None:
        # Update metadata before waking the next waiter.
        _TRACKER.released(self)
        self._lock.release()

    def locked(self) -> bool:
        return self._lock.locked()

    def __enter__(self) -> "TrackedLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
