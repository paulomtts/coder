# tests/conftest.py
import pytest
from pygents.registry import AgentRegistry, HookRegistry, ToolRegistry


@pytest.fixture(autouse=True)
def clean_registries():
    """Clear all pygents registries before each test."""
    ToolRegistry.clear()
    AgentRegistry.clear()
    HookRegistry.clear()
    yield
    ToolRegistry.clear()
    AgentRegistry.clear()
    HookRegistry.clear()
