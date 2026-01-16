from dataclasses import dataclass


@dataclass
class Queue:
    name: str


@dataclass
class Job:
    id: str
    name: str
    state: str
    data_preview: str
    timestamp: str = ""

