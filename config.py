"""Carga config.yaml y .env en objetos tipados.

Un único módulo (no un paquete) porque el loader es pequeño; ver la sección
"Guardrail de coste vs cron" en CLAUDE.md para el rol que juega config.yaml
como punto de confirmación explícita del gasto recurrente de scheduler/capture.py.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv as _load_dotenv

REPO_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Target:
    name: str
    active: bool
    sport_key: str
    markets: list[str]
    sharp_book: str
    soft_books: list[str]
    poll_interval_hours: float

    @property
    def bookmakers(self) -> list[str]:
        return [self.sharp_book, *self.soft_books]


@dataclass(frozen=True)
class AppConfig:
    db_path: str
    min_remaining_credits: int
    targets: list[Target]

    def active_targets(self) -> list[Target]:
        return [t for t in self.targets if t.active]


def load_dotenv(path: Path = REPO_ROOT / ".env") -> None:
    """Carga variables de entorno usando python-dotenv."""
    _load_dotenv(dotenv_path=path)


def load_config(path: Path = REPO_ROOT / "config.yaml") -> AppConfig:
    raw = yaml.safe_load(path.read_text())
    targets = [
        Target(
            name=t["name"],
            active=t["active"],
            sport_key=t["sport_key"],
            markets=t["markets"],
            sharp_book=t["sharp_book"],
            soft_books=t["soft_books"],
            poll_interval_hours=t["poll_interval_hours"],
        )
        for t in raw["targets"]
    ]
    return AppConfig(
        db_path=raw["storage"]["db_path"],
        min_remaining_credits=raw["min_remaining_credits"],
        targets=targets,
    )
