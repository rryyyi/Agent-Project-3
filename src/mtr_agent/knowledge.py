"""Load versioned synthetic data and resolve multilingual station aliases."""

import hashlib
import json
import re
from importlib.resources import files

from .models import Network


class Knowledge:
    def __init__(self, network: dict, documents: list[dict]):
        self.network = Network.model_validate(network)
        self.documents = documents
        self.stations = {s.id: s for s in self.network.stations}
        payload = json.dumps([network, documents], sort_keys=True, ensure_ascii=False)
        self.version = hashlib.sha256(payload.encode()).hexdigest()[:16]
        self._aliases = []
        for station in self.network.stations:
            for alias in {station.id, station.name, station.en, *station.aliases}:
                pattern = re.escape(alias.casefold())
                if alias.isascii():
                    pattern = r"(?<![a-z0-9])" + pattern + r"(?![a-z0-9])"
                self._aliases.append((re.compile(pattern), station.id))

    @classmethod
    def load(cls):
        root = files("mtr_agent").joinpath("data")
        return cls(
            json.loads(root.joinpath("network.json").read_text(encoding="utf-8")),
            json.loads(root.joinpath("faq.json").read_text(encoding="utf-8")),
        )

    def mentions(self, text: str) -> list[dict]:
        candidates = []
        for pattern, station in self._aliases:
            for match in pattern.finditer(text.casefold()):
                candidates.append((match.start(), match.end(), station))
        selected = []
        for start, end, station in sorted(candidates, key=lambda x: (-(x[1] - x[0]), x[0])):
            if not any(start < old[1] and end > old[0] for old in selected):
                selected.append((start, end, station))
        return [
            {"start": start, "end": end, "id": station} for start, end, station in sorted(selected)
        ]

    def resolve(self, text: str) -> list[str]:
        return list(dict.fromkeys(mention["id"] for mention in self.mentions(text)))

    def station_id(self, value: str) -> str:
        if value in self.stations:
            return value
        normalized = value.strip().casefold()
        matches = {station for pattern, station in self._aliases if pattern.fullmatch(normalized)}
        if len(matches) != 1:
            raise ValueError(f"Unknown station or ambiguous name: {value}")
        return matches.pop()
