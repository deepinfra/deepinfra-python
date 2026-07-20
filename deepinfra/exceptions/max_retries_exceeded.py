"""Backward-compat re-export; the class now lives in deepinfra._exceptions."""

from deepinfra._exceptions import MaxRetriesExceededError

__all__ = ["MaxRetriesExceededError"]
