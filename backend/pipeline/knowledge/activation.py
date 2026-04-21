"""Composable activation adaptors for knowledge elements.

ACT-R/python_actr inspired activation pipeline: base-level decay,
context spreading, and stochastic noise composed into a chain that
computes derived activation from TruthValue.

Does NOT modify TruthValue — computes a separate activation float
used for ranking and prioritization.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from backend.pipeline.knowledge.truth import TruthValue


class ActivationContext(BaseModel):
    """Context passed through the activation adaptor chain."""

    entity_id: str
    current_truth: TruthValue
    access_count: int = 0
    time_since_last_access: float = 0.0  # seconds
    neighbor_activations: dict[str, float] = Field(default_factory=dict)


class ActivationAdaptor(ABC):
    """Base class for activation modifiers."""

    @abstractmethod
    def adjust(self, base_activation: float, context: ActivationContext) -> float:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class BaseLevelDecay(ActivationAdaptor):
    """ACT-R base-level activation decay.

    activation = base / (1.0 + decay_rate * time_since_last_access)
    """

    def __init__(self, decay_rate: float = 0.5):
        self._decay_rate = decay_rate

    def adjust(self, base_activation: float, context: ActivationContext) -> float:
        if context.time_since_last_access <= 0:
            return base_activation
        return base_activation / (1.0 + self._decay_rate * context.time_since_last_access)

    @property
    def name(self) -> str:
        return f"base_level_decay(rate={self._decay_rate})"


class ContextSpreading(ActivationAdaptor):
    """Hebbian-like activation spreading through graph neighbors.

    spreading = sum(neighbor_activation * weight) * spreading_rate
    """

    def __init__(self, spreading_rate: float = 0.1):
        self._spreading_rate = spreading_rate

    def adjust(self, base_activation: float, context: ActivationContext) -> float:
        if not context.neighbor_activations:
            return base_activation
        spreading = sum(context.neighbor_activations.values()) * self._spreading_rate
        return base_activation + spreading

    @property
    def name(self) -> str:
        return f"context_spreading(rate={self._spreading_rate})"


class StochasticNoise(ActivationAdaptor):
    """Gaussian noise to prevent deterministic lock-in."""

    def __init__(self, noise_std: float = 0.02):
        self._noise_std = noise_std

    def adjust(self, base_activation: float, context: ActivationContext) -> float:
        return base_activation + random.gauss(0, self._noise_std)

    @property
    def name(self) -> str:
        return f"stochastic_noise(std={self._noise_std})"


class ActivationPipeline:
    """Composes activation adaptors into a sequential chain."""

    def __init__(self, adaptors: list[ActivationAdaptor] | None = None):
        self._adaptors = adaptors or []

    def compute(self, context: ActivationContext) -> float:
        activation = context.current_truth.expectation
        for adaptor in self._adaptors:
            activation = adaptor.adjust(activation, context)
        return max(0.0, activation)

    @property
    def adaptor_count(self) -> int:
        return len(self._adaptors)

    @property
    def adaptor_names(self) -> list[str]:
        return [a.name for a in self._adaptors]
