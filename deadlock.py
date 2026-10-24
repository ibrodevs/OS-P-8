"""Intentional deadlock: use only for demonstration (terminate with Ctrl+C/timeout)."""

import threading

lock_a = threading.Lock()
lock_b = threading.Lock()
barrier = threading.Barrier(2)


def worker_a():
    with lock_a:
        print("worker_a: acquired A", flush=True)
        barrier.wait()
        print("worker_a: waiting for B", flush=True)
        with lock_b:
            print("worker_a: acquired B", flush=True)


def worker_b():
    with lock_b:
        print("worker_b: acquired B", flush=True)
        barrier.wait()
        print("worker_b: waiting for A", flush=True)
        with lock_a:
            print("worker_b: acquired A", flush=True)


t1 = threading.Thread(target=worker_a, name="worker-a")
t2 = threading.Thread(target=worker_b, name="worker-b")
t1.start()
t2.start()
t1.join()
t2.join()
