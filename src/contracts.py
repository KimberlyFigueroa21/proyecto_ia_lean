"""Contratos I/O (RNF-4). Un modelo Pydantic por agente; exportables a JSON Schema."""
from enum import Enum
from pydantic import BaseModel, Field


class Action(str, Enum):
    RETRY = "RETRY"
    REPLAN = "REPLAN"
    FAIL = "FAIL"


class RunConfig(BaseModel):
    """Una configuración de ablación = un RunConfig. El grafo NO cambia de forma."""
    name: str = "full"
    use_planner: bool = True
    use_rag: bool = True
    use_critic: bool = True
    top_k: int = 5            # lemas recuperados
    k_max: int = 3            # intentos por subobjetivo (3-5 en sistema completo)
    r_max: int = 1            # replanificaciones permitidas por problema
    max_llm_calls: int = 30   # tope de seguridad; NFR-3 se reporta como promedio
    seed: int = 0
    temperature: float = 0.0


class PlannerIn(BaseModel):
    problem: str
    domain: str | None = None

class PlannerOut(BaseModel):
    subgoals: list[str] = Field(min_length=1)


class RetrieverIn(BaseModel):
    subgoal: str
    k: int

class Lemma(BaseModel):
    name: str
    signature: str
    score: float = 0.0

class RetrieverOut(BaseModel):
    lemmas: list[Lemma]


class GeneratorIn(BaseModel):
    subgoal: str
    lemmas: list[Lemma] = []
    hint: str | None = None   # corrección sugerida por el Crítico

class GeneratorOut(BaseModel):
    sketch: str


class FormalizerIn(BaseModel):
    sketch: str
    lemmas: list[Lemma] = []

class FormalizerOut(BaseModel):
    lean_code: str


class VerifierIn(BaseModel):
    lean_code: str

class VerifierOut(BaseModel):
    verdict: bool
    trace: str = ""


class CriticIn(BaseModel):
    trace: str
    history: list[dict]

class CriticOut(BaseModel):
    action: Action
    hint: str = ""
