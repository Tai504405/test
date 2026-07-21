"""Content Agent System package.

The AI modules are intentionally independent from the platform/orchestrator so
they can be merged into the shared repository without taking over ownership of
the CLI, database, or policy parser.
"""

__all__ = ["ai"]
