from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path


def find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    """Return one directed cycle, with the first node repeated at the end."""
    color: dict[str, int] = {}  # 0 unseen, 1 active, 2 done
    stack: list[str] = []
    position: dict[str, int] = {}

    def dfs(node: str) -> list[str] | None:
        color[node] = 1
        position[node] = len(stack)
        stack.append(node)
        for neighbor in sorted(graph.get(node, ())):
            state = color.get(neighbor, 0)
            if state == 0:
                cycle = dfs(neighbor)
                if cycle:
                    return cycle
            elif state == 1:
                start = position[neighbor]
                return stack[start:] + [neighbor]
        stack.pop()
        position.pop(node, None)
        color[node] = 2
        return None

    nodes = set(graph)
    for targets in graph.values():
        nodes.update(targets)
    for node in sorted(nodes):
        if color.get(node, 0) == 0:
            cycle = dfs(node)
            if cycle:
                return cycle
    return None


class JournalState:
    def __init__(self) -> None:
        self.owner: dict[str, str] = {}
        self.waiting_for: dict[str, set[str]] = defaultdict(set)

    def apply(self, action: str, process: str, resource: str) -> None:
        action = action.lower()
        if action == "acquire":
            current = self.owner.get(resource)
            if current is not None and current != process:
                raise ValueError(
                    f"{process} cannot acquire {resource}: currently owned by {current}; use wait"
                )
            self.owner[resource] = process
            self.waiting_for[process].discard(resource)
        elif action == "release":
            current = self.owner.get(resource)
            if current != process:
                raise ValueError(
                    f"{process} cannot release {resource}: owner is {current or '<none>'}"
                )
            del self.owner[resource]
        elif action == "wait":
            current = self.owner.get(resource)
            if current is None:
                raise ValueError(f"{process} waits for free resource {resource}")
            if current == process:
                raise ValueError(f"{process} already owns {resource}")
            self.waiting_for[process].add(resource)
        else:
            raise ValueError(f"unknown action: {action}")

    def wait_for_graph(self) -> dict[str, set[str]]:
        graph: dict[str, set[str]] = defaultdict(set)
        for process, resources in self.waiting_for.items():
            for resource in resources:
                owner = self.owner.get(resource)
                if owner is not None and owner != process:
                    graph[process].add(owner)
        return dict(graph)


def parse_journal(path: Path) -> JournalState:
    state = JournalState()
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 3:
            raise ValueError(f"{path}:{line_no}: expected '<action> <process> <resource>'")
        state.apply(*parts)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Deadlock detector using a wait-for graph")
    parser.add_argument("journal", help="event journal with acquire/release/wait lines")
    args = parser.parse_args()

    state = parse_journal(Path(args.journal))
    graph = state.wait_for_graph()
    print("Wait-for graph:")
    if graph:
        for process in sorted(graph):
            print(f"  {process} -> {', '.join(sorted(graph[process]))}")
    else:
        print("  <empty>")

    cycle = find_cycle(graph)
    if cycle:
        participants = cycle[:-1]
        print(f"DEADLOCK: {' -> '.join(cycle)}")
        print(f"Participants: {', '.join(participants)}")
        raise SystemExit(2)
    print("NO DEADLOCK")


if __name__ == "__main__":
    main()
