"""Versioned run configuration and validation. No solver is implemented here."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SUPPORTED_SELECTION_METHODS = {"fitness", "diversity"}
SUPPORTED_INITIALIZATION_SOURCES = {"grid_mutations", "random_valid", "file", "agent"}
SCHEMA_VERSION = "gerit-run-config-0.1"


@dataclass(frozen=True)
class SelectionGroup:
    """A selection allocation. New strategies can be registered later."""

    method: str
    share: float
    options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.method not in SUPPORTED_SELECTION_METHODS:
            raise ValueError(f"Unknown selection method: {self.method}; register it before use")
        if isinstance(self.share, bool) or not isinstance(self.share, (int, float)):
            raise ValueError("Selection share must be numeric")
        if not 0 <= self.share <= 1:
            raise ValueError("Selection share must be between 0 and 1")


@dataclass(frozen=True)
class RunConfig:
    """Parameters are intentionally independent: initial parents != survivors."""

    n_squares: int = 5
    initial_population: int = 20
    next_generation_population: int = 20
    offspring_per_parent: int = 5
    selection_groups: tuple[SelectionGroup, ...] = (
        SelectionGroup("fitness", 0.75),
        SelectionGroup("diversity", 0.25),
    )
    initialization_source: str = "grid_mutations"
    initialization_file: str | None = None
    agent_adapter: str | None = None
    max_generations: int = 100
    max_evaluations: int = 100_000
    seed: int = 17
    diversity_metric: str = "center_distances_angles"
    initial_container_side: float = 3.0

    def __post_init__(self) -> None:
        for name in (
            "n_squares", "initial_population", "next_generation_population",
            "offspring_per_parent", "max_generations", "max_evaluations",
        ):
            val = getattr(self, name)
            if type(val) is not int or val < 1:
                raise ValueError(f"{name} must be a positive integer")
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")
        if self.initial_container_side <= 0:
            raise ValueError("initial_container_side must be positive")
        if self.initialization_source not in SUPPORTED_INITIALIZATION_SOURCES:
            raise ValueError("Unknown initialization_source")
        if self.initialization_source == "file" and not self.initialization_file:
            raise ValueError("initialization_file is required for file source")
        if self.initialization_source == "agent" and not self.agent_adapter:
            raise ValueError("agent_adapter is required for agent source")
        if not self.selection_groups:
            raise ValueError("selection_groups cannot be empty")
        if len({g.method for g in self.selection_groups}) != len(self.selection_groups):
            raise ValueError("Duplicate selection methods in selection_groups")
        if abs(sum(g.share for g in self.selection_groups) - 1.0) > 1e-9:
            raise ValueError("selection group shares must sum to 1")
        if self.diversity_metric not in {"center_distances_angles"}:
            raise ValueError("Unsupported diversity metric; implement and register it first")

    def selection_slots(self) -> dict[str, int]:
        """Hamilton/largest-remainder apportionment; exact sum with stable ties."""
        slots = self.next_generation_population
        raw = [slots * g.share for g in self.selection_groups]
        base = [int(x) for x in raw]
        remaining = slots - sum(base)
        ordering = sorted(range(len(raw)), key=lambda i: (-(raw[i] - base[i]), i))
        for i in ordering[:remaining]:
            base[i] += 1
        return {g.method: count for g, count in zip(self.selection_groups, base)}


def load_config(path: str | Path) -> RunConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Configuration must be an object")
    if data.pop("schema_version", None) != SCHEMA_VERSION:
        raise ValueError(f"Expected schema_version: {SCHEMA_VERSION}")
    allowed = set(RunConfig.__dataclass_fields__)
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"Unknown config keys: {sorted(unknown)}")
    if "selection_groups" in data:
        groups = data["selection_groups"]
        if not isinstance(groups, list) or not all(isinstance(g, dict) for g in groups):
            raise ValueError("selection_groups must be a list of objects")
        for g in groups:
            unknown_fields = set(g) - {"method", "share", "options"}
            if unknown_fields:
                raise ValueError(f"Unknown selection group fields: {sorted(unknown_fields)}")
        data["selection_groups"] = tuple(SelectionGroup(**g) for g in groups)
    return RunConfig(**data)
