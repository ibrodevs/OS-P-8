import unittest

from banker import parse_bank_file
from tracked_lock import DeadlockDetected, TrackedLock
from wait_graph_detector import find_cycle, parse_journal


class BankerTests(unittest.TestCase):
    def test_bank1_is_safe_with_reference_sequence(self):
        state = parse_bank_file("bank1.txt")
        safe, sequence = state.safety_check()
        self.assertTrue(safe)
        self.assertEqual(
            [state.process_names[i] for i in sequence],
            ["P1", "P3", "P4", "P2", "P0"],
        )

    def test_bank2_is_unsafe(self):
        state = parse_bank_file("bank2.txt")
        safe, _ = state.safety_check()
        self.assertFalse(safe)

    def test_reference_request_is_granted(self):
        state = parse_bank_file("bank1.txt")
        pid = state.process_names.index("P1")
        accepted, _, _ = state.request(pid, [1, 0, 2])
        self.assertTrue(accepted)
        self.assertEqual(state.available, [2, 3, 0])

    def test_unsafe_request_rolls_back(self):
        state = parse_bank_file("bank1.txt")
        before_available = state.available.copy()
        before_allocation = [row.copy() for row in state.allocation]
        pid = state.process_names.index("P0")
        accepted, reason, _ = state.request(pid, [0, 0, 2])
        self.assertFalse(accepted)
        self.assertIn("rolled back", reason)
        self.assertEqual(state.available, before_available)
        self.assertEqual(state.allocation, before_allocation)


class WaitGraphTests(unittest.TestCase):
    def test_deadlock_journal_has_cycle(self):
        state = parse_journal(__import__("pathlib").Path("journal_deadlock.txt"))
        cycle = find_cycle(state.wait_for_graph())
        self.assertIsNotNone(cycle)
        self.assertEqual(set(cycle[:-1]), {"P0", "P1"})

    def test_safe_journal_has_no_cycle(self):
        state = parse_journal(__import__("pathlib").Path("journal_safe.txt"))
        self.assertIsNone(find_cycle(state.wait_for_graph()))


class TrackedLockTests(unittest.TestCase):
    def test_self_deadlock_is_rejected(self):
        lock = TrackedLock("self-test")
        lock.acquire()
        try:
            with self.assertRaises(DeadlockDetected):
                lock.acquire()
        finally:
            lock.release()


if __name__ == "__main__":
    unittest.main()
