import threading

from tracked_lock import DeadlockDetected, TrackedLock

lock_a = TrackedLock("A")
lock_b = TrackedLock("B")
barrier = threading.Barrier(2)
errors: list[str] = []


def worker_a():
    try:
        with lock_a:
            print("worker_a: acquired A", flush=True)
            barrier.wait()
            print("worker_a: requesting B", flush=True)
            with lock_b:
                print("worker_a: acquired B", flush=True)
    except DeadlockDetected as exc:
        errors.append(f"worker_a: {exc}")
        print(errors[-1], flush=True)


def worker_b():
    try:
        with lock_b:
            print("worker_b: acquired B", flush=True)
            barrier.wait()
            print("worker_b: requesting A", flush=True)
            with lock_a:
                print("worker_b: acquired A", flush=True)
    except DeadlockDetected as exc:
        errors.append(f"worker_b: {exc}")
        print(errors[-1], flush=True)


t1 = threading.Thread(target=worker_a, name="worker-a")
t2 = threading.Thread(target=worker_b, name="worker-b")
t1.start()
t2.start()
t1.join(timeout=3)
t2.join(timeout=3)

if t1.is_alive() or t2.is_alive():
    raise RuntimeError("TrackedLock failed: a thread is still blocked")
if not errors:
    raise RuntimeError("Expected DeadlockDetected, but no cycle was reported")
print("Finished without hanging: TrackedLock rejected the cyclic acquire.")
