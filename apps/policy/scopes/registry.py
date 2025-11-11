from __future__ import annotations

from typing import Dict, Tuple, Type

from .base import ScopeStrategy

_registry: Dict[Tuple[str, str], Type[ScopeStrategy]] = {}


def register(resource_key: str, action_key: str):
    """Decorator to register a scope strategy class for (resource, action)."""

    def deco(cls: Type[ScopeStrategy]):
        cls.resource_key = resource_key
        cls.action_key = action_key
        _registry[(resource_key, action_key)] = cls
        return cls

    return deco


def get_strategy(resource_key: str, action_key: str) -> Type[ScopeStrategy] | None:
    return _registry.get((resource_key, action_key))


def all_registered() -> Dict[Tuple[str, str], Type[ScopeStrategy]]:
    return dict(_registry)
