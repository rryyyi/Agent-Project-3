"""Line-state Dijkstra, with explicit transfers and auditable graph triples."""

import heapq
from collections import defaultdict
from itertools import count

from .knowledge import Knowledge


class Router:
    def __init__(self, knowledge: Knowledge):
        self.kb = knowledge
        self.adjacency = defaultdict(list)
        for edge in knowledge.network.edges:
            self.adjacency[edge.a].append((edge.b, edge.line, edge.minutes))
            self.adjacency[edge.b].append((edge.a, edge.line, edge.minutes))

    def route(self, origin: str, destination: str, objective: str = "fastest") -> dict:
        if objective not in {"fastest", "fewest_transfers"}:
            raise ValueError("Invalid objective")
        if origin not in self.kb.stations or destination not in self.kb.stations:
            raise ValueError("Unknown station")
        serial = count()
        start = (origin, "")
        distances = {start: (0.0, 0)}
        previous = {}
        queue = [((0.0, 0), next(serial), start)]
        final = None
        while queue:
            cost, _, state = heapq.heappop(queue)
            if distances.get(state) != cost:
                continue
            station, current_line = state
            if station == destination:
                final = state
                break
            for neighbor, line, minutes in self.adjacency[station]:
                transfer = int(bool(current_line) and current_line != line)
                duration = minutes + transfer * self.kb.network.transfer_minutes
                delta = (duration, transfer) if objective == "fastest" else (transfer, duration)
                candidate = (cost[0] + delta[0], cost[1] + delta[1])
                next_state = (neighbor, line)
                if candidate < distances.get(next_state, (float("inf"), float("inf"))):
                    distances[next_state] = candidate
                    previous[next_state] = (state, minutes)
                    heapq.heappush(queue, (candidate, next(serial), next_state))
        if final is None:
            raise ValueError("No route in the demo graph")
        steps = []
        cursor = final
        while cursor != start:
            prior, minutes = previous[cursor]
            steps.append((prior[0], cursor[0], cursor[1], minutes))
            cursor = prior
        steps.reverse()
        segments = []
        triples = []
        for a, b, line, minutes in steps:
            triples.append(
                {
                    "subject": a,
                    "relation": "NEXT_ON_LINE",
                    "object": b,
                    "line": line,
                    "minutes": minutes,
                    "source": self.kb.network.source,
                }
            )
            if segments and segments[-1]["line"] == line:
                segments[-1]["stations"].append(b)
                segments[-1]["minutes"] += minutes
            else:
                segments.append({"line": line, "stations": [a, b], "minutes": minutes})
        transfers = max(0, len(segments) - 1)
        return {
            "origin": origin,
            "destination": destination,
            "objective": objective,
            "stations": [origin] + [step[1] for step in steps],
            "station_names": [
                self.kb.stations[s].name for s in [origin] + [step[1] for step in steps]
            ],
            "segments": segments,
            "transfers": transfers,
            "transfer_stations": [s["stations"][0] for s in segments[1:]],
            "minutes": sum(step[3] for step in steps)
            + transfers * self.kb.network.transfer_minutes,
            "triples": triples,
            "citations": [{"source": self.kb.network.source, "version": self.kb.network.version}],
            "disclaimer": "Synthetic demo travel times; not a timetable or live routing service.",
        }
