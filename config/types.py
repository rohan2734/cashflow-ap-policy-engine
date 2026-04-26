from dataclasses import dataclass

@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    temperature: float
    max_tokens: int

@dataclass(frozen=True)
class ConcurrencyConfig:
    max_parallel_clauses: int

@dataclass(frozen=True)
class NotificationConfig:
    endpoint: str

@dataclass(frozen=True)
class AppConfig:
    llm: LLMConfig
    concurrency: ConcurrencyConfig
    notifications: NotificationConfig
    pipeline_id: str
    confidence_threshold: float