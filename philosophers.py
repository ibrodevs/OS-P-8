from __future__ import annotations

import argparse
import random
import threading
import time


N = 5


def format_stats(title: str, counts: list[int]) -> None:
    print(f"\n{title}")
    for i, count in enumerate(counts):
        print(f"P{i}: ate {count} times")
    print(f"Total: {sum(counts)}, min={min(counts)}, max={max(counts)}")


def run_deadlock(observe_seconds: float) -> list[int]:
    """Deterministic classic deadlock: every philosopher holds left then waits right."""
    forks = [threading.Lock() for _ in range(N)]
    barrier = threading.Barrier(N)
    counts = [0] * N

    def philosopher(i: int) -> None:
        left = forks[i]
        right = forks[(i + 1) % N]
        left.acquire()
        print(f"P{i} acquired left fork {i}", flush=True)
        barrier.wait()
        print(f"P{i} waits for right fork {(i + 1) % N}", flush=True)
        right.acquire()  # blocks forever in the intentional deadlock
        counts[i] += 1

    threads = [
        threading.Thread(target=philosopher, args=(i,), daemon=True, name=f"deadlock-P{i}")
        for i in range(N)
    ]
    for thread in threads:
        thread.start()
    time.sleep(observe_seconds)
    alive = sum(thread.is_alive() for thread in threads)
    print(f"Intentional deadlock observed: {alive}/{N} philosopher threads are blocked.")
    return counts


def run_fixed(mode: str, duration: float) -> list[int]:
    forks = [threading.Lock() for _ in range(N)]
    waiter = threading.Semaphore(N - 1) if mode == "waiter" else None
    stop = threading.Event()
    counts = [0] * N

    def philosopher(i: int) -> None:
        rng = random.Random(1000 + i)
        left_index = i
        right_index = (i + 1) % N

        while not stop.is_set():
            time.sleep(rng.uniform(0.0005, 0.0020))
            if mode == "ordered":
                first_index, second_index = sorted((left_index, right_index))
                with forks[first_index]:
                    with forks[second_index]:
                        counts[i] += 1
                        time.sleep(rng.uniform(0.0003, 0.0010))
            elif mode == "waiter":
                assert waiter is not None
                with waiter:
                    with forks[left_index]:
                        with forks[right_index]:
                            counts[i] += 1
                            time.sleep(rng.uniform(0.0003, 0.0010))
            else:
                raise ValueError(mode)

    threads = [threading.Thread(target=philosopher, args=(i,), name=f"{mode}-P{i}") for i in range(N)]
    for thread in threads:
        thread.start()
    time.sleep(duration)
    stop.set()
    for thread in threads:
        thread.join(timeout=2)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError(f"{mode}: a philosopher failed to stop")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Dining philosophers: deadlock and two fixes")
    parser.add_argument(
        "--mode",
        choices=("deadlock", "ordered", "waiter", "all"),
        default="all",
    )
    parser.add_argument("--duration", type=float, default=2.0)
    args = parser.parse_args()

    if args.duration <= 0:
        raise SystemExit("--duration must be positive")

    if args.mode in {"deadlock", "all"}:
        counts = run_deadlock(min(args.duration, 1.0))
        format_stats("Naive left-then-right (deadlock)", counts)
    if args.mode in {"ordered", "all"}:
        counts = run_fixed("ordered", args.duration)
        format_stats("Fix 1: globally ordered fork acquisition", counts)
    if args.mode in {"waiter", "all"}:
        counts = run_fixed("waiter", args.duration)
        format_stats("Fix 2: waiter semaphore (N-1 philosophers)", counts)


if __name__ == "__main__":
    main()
