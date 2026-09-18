"""Target adapters. One module per autonomous modification system."""

from .ghost import GhostToolsAdapter
from .pydantic_v2 import PydanticV2MigratorAdapter

__all__ = ["GhostToolsAdapter", "PydanticV2MigratorAdapter"]
