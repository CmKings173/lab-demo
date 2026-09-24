"""Deterministic local expansion sources for the Lab 1 dataset."""

from .generator import GeneratedExample, build_expanded_examples
from .spec import EXPANSION_FAMILY_SPECS, EXPANSION_SEED, EXPANSION_TARGET

__all__ = [
    "EXPANSION_FAMILY_SPECS",
    "EXPANSION_SEED",
    "EXPANSION_TARGET",
    "GeneratedExample",
    "build_expanded_examples",
]
