from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


Vector = list[int]


@dataclass
class BankerState:
    available: Vector
    allocation: list[Vector]
    maximum: list[Vector]
    process_names: list[str]

    @property
    def resource_count(self) -> int:
        return len(self.available)

    @property
    def need(self) -> list[Vector]:
        return [
            [maximum[j] - allocation[j] for j in range(self.resource_count)]
            for allocation, maximum in zip(self.allocation, self.maximum)
        ]

    def safety_check(self) -> tuple[bool, list[int]]:
        """Return (is_safe, safe_sequence_indices)."""
        work = self.available.copy()
        finish = [False] * len(self.process_names)
        need = self.need
        sequence: list[int] = []

        while len(sequence) < len(self.process_names):
            progressed = False
            for pid in range(len(self.process_names)):
                if finish[pid]:
                    continue
                if all(need[pid][j] <= work[j] for j in range(self.resource_count)):
                    # Simulate completion: the process returns its allocated resources.
                    for j in range(self.resource_count):
                        work[j] += self.allocation[pid][j]
                    finish[pid] = True
                    sequence.append(pid)
                    progressed = True
            if not progressed:
                break

        return all(finish), sequence

    def request(self, pid: int, vector: Vector) -> tuple[bool, str, list[int]]:
        """Try a Banker's request; rollback if the tentative state is unsafe."""
        if not 0 <= pid < len(self.process_names):
            return False, f"unknown process id: {pid}", []
        if len(vector) != self.resource_count:
            return False, f"expected {self.resource_count} resource values", []
        if any(value < 0 for value in vector):
            return False, "request values must be non-negative", []

        need = self.need[pid]
        if any(vector[j] > need[j] for j in range(self.resource_count)):
            return False, "request exceeds process Need", []
        if any(vector[j] > self.available[j] for j in range(self.resource_count)):
            return False, "resources are not currently Available", []

        # Tentative allocation.
        for j in range(self.resource_count):
            self.available[j] -= vector[j]
            self.allocation[pid][j] += vector[j]

        safe, sequence = self.safety_check()
        if safe:
            return True, "request granted", sequence

        # Roll back exactly what was tentatively allocated.
        for j in range(self.resource_count):
            self.available[j] += vector[j]
            self.allocation[pid][j] -= vector[j]
        return False, "request would make the state UNSAFE; rolled back", sequence


def _clean_lines(path: Path) -> list[str]:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            lines.append(line)
    return lines


def parse_bank_file(path: str | Path) -> BankerState:
    lines = _clean_lines(Path(path))
    if not lines or not lines[0].lower().startswith("available:"):
        raise ValueError("first non-comment line must be 'Available: ...'")

    available = [int(x) for x in lines[0].split(":", 1)[1].split()]
    if not available:
        raise ValueError("Available vector cannot be empty")

    try:
        allocation_start = lines.index("Allocation:") + 1
        max_marker = lines.index("Max:")
    except ValueError as exc:
        raise ValueError("file must contain Allocation: and Max: sections") from exc

    allocation_rows = lines[allocation_start:max_marker]
    max_rows = lines[max_marker + 1 :]
    if not allocation_rows or not max_rows:
        raise ValueError("Allocation and Max sections cannot be empty")

    def parse_rows(rows: Iterable[str]) -> tuple[list[str], list[Vector]]:
        names: list[str] = []
        matrix: list[Vector] = []
        for row in rows:
            parts = row.split()
            if len(parts) != len(available) + 1:
                raise ValueError(f"bad row: {row!r}")
            names.append(parts[0])
            matrix.append([int(x) for x in parts[1:]])
        return names, matrix

    allocation_names, allocation = parse_rows(allocation_rows)
    maximum_names, maximum = parse_rows(max_rows)
    if allocation_names != maximum_names:
        raise ValueError("process order/names must match in Allocation and Max")

    for pid, (alloc, max_row) in enumerate(zip(allocation, maximum)):
        if any(a < 0 or m < 0 for a, m in zip(alloc, max_row)):
            raise ValueError("resource values must be non-negative")
        if any(a > m for a, m in zip(alloc, max_row)):
            raise ValueError(f"Allocation exceeds Max for {allocation_names[pid]}")

    return BankerState(available, allocation, maximum, allocation_names)


def format_sequence(state: BankerState, sequence: list[int]) -> str:
    return " -> ".join(state.process_names[pid] for pid in sequence)


def print_state(state: BankerState) -> None:
    print(f"Available: {tuple(state.available)}")
    print("Process | Allocation | Max       | Need")
    print("--------+------------+-----------+-----------")
    for name, alloc, maximum, need in zip(
        state.process_names, state.allocation, state.maximum, state.need
    ):
        print(f"{name:<7} | {str(tuple(alloc)):<10} | {str(tuple(maximum)):<9} | {tuple(need)}")


def parse_request_line(state: BankerState, line: str) -> tuple[int, Vector]:
    parts = line.split()
    if parts and parts[0].lower() == "request":
        parts = parts[1:]
    if len(parts) != state.resource_count + 1:
        raise ValueError(
            f"use: request <pid> {' '.join(f'R{i}' for i in range(state.resource_count))}"
        )

    process_token = parts[0]
    if process_token in state.process_names:
        pid = state.process_names.index(process_token)
    elif process_token.lower().startswith("p") and process_token[1:].isdigit():
        pid = int(process_token[1:])
    elif process_token.isdigit():
        pid = int(process_token)
    else:
        raise ValueError(f"unknown process: {process_token}")

    return pid, [int(x) for x in parts[1:]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Full Banker's algorithm")
    parser.add_argument("file", help="bank input file")
    parser.add_argument(
        "--once",
        action="store_true",
        help="only print the initial safety result and exit",
    )
    args = parser.parse_args()

    state = parse_bank_file(args.file)
    print_state(state)
    safe, sequence = state.safety_check()
    if safe:
        print(f"\nSAFE: {format_sequence(state, sequence)}")
    else:
        partial = format_sequence(state, sequence) or "<none>"
        print(f"\nUNSAFE (only finishable prefix: {partial})")

    if args.once:
        return

    print(
        "\nEnter requests as 'request P1 1 0 2'. Commands: status, safety, quit"
    )
    while True:
        try:
            line = input("banker> ").strip()
        except EOFError:
            print()
            break
        if not line:
            continue
        command = line.lower()
        if command in {"quit", "exit", "q"}:
            break
        if command == "status":
            print_state(state)
            continue
        if command == "safety":
            safe, sequence = state.safety_check()
            label = "SAFE" if safe else "UNSAFE"
            print(f"{label}: {format_sequence(state, sequence) or '<none>'}")
            continue

        try:
            pid, vector = parse_request_line(state, line)
            accepted, reason, sequence = state.request(pid, vector)
            name = state.process_names[pid] if 0 <= pid < len(state.process_names) else f"P{pid}"
            print(f"{'GRANTED' if accepted else 'DENIED'} {name} {tuple(vector)}: {reason}")
            if accepted:
                print(f"Safe sequence: {format_sequence(state, sequence)}")
        except (ValueError, IndexError) as exc:
            print(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
