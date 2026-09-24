"""Opt-in execution-governance helpers.

This package composes existing Noema contracts and never owns an execution
runtime, external catalog, or domain workflow.
"""

from .plan import build_execution_envelope

__all__ = ["build_execution_envelope"]
