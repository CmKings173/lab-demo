from typing import Protocol


class ModelClient(Protocol):
    def generate(self, prompt: str) -> str: ...
