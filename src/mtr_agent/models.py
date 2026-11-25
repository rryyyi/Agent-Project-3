"""Validated, explicit domain contracts; graph order is not a timetable."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Station(StrictModel):
    id: str
    name: str
    en: str
    aliases: list[str] = Field(default_factory=list)


class Edge(StrictModel):
    a: str
    b: str
    line: str
    minutes: float = Field(gt=0, allow_inf_nan=False)


class Network(StrictModel):
    version: str
    source: str
    transfer_minutes: float = Field(ge=0, allow_inf_nan=False)
    lines: dict[str, str]
    stations: list[Station]
    edges: list[Edge]

    @model_validator(mode="after")
    def validate_references(self):
        ids = {s.id for s in self.stations}
        if len(ids) != len(self.stations):
            raise ValueError("Duplicate station IDs")
        for edge in self.edges:
            if edge.a not in ids or edge.b not in ids or edge.line not in self.lines:
                raise ValueError("Invalid edge reference")
            if edge.a == edge.b:
                raise ValueError("Self edge is not allowed")
        return self


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")

    @model_validator(mode="after")
    def no_blank_message(self):
        if not self.message.strip():
            raise ValueError("message cannot be blank")
        return self


class RouteArguments(StrictModel):
    origin: str = Field(min_length=1, max_length=100)
    destination: str = Field(min_length=1, max_length=100)
    objective: str = Field(default="fastest", pattern="^(fastest|fewest_transfers)$")


class SearchArguments(StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=3, ge=1, le=10)
