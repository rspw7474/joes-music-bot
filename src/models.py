from dataclasses import dataclass


@dataclass(slots=True)
class Track:
    url: str
    title: str
    text_channel_id: int
