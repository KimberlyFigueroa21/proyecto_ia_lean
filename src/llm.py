"""Interfaz mínima de LLM. Cambiar de proveedor = escribir otra clase con .call()."""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMResult:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0


class LLM(Protocol):
    def call(self, agent: str, prompt: str) -> LLMResult: ...


class MockLLM:
    """Respuestas guionadas por agente, en orden. Para pruebas unitarias y de integración."""
    def __init__(self, script: dict[str, list[str]]):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[tuple[str, str]] = []

    def call(self, agent: str, prompt: str) -> LLMResult:
        self.calls.append((agent, prompt))
        queue = self.script[agent]
        text = queue.pop(0) if len(queue) > 1 else queue[0]  # repite la última
        return LLMResult(text, tokens_in=len(prompt.split()), tokens_out=len(text.split()))
