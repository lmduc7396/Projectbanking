"""Utilities package initialisation."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# Proactively load environment variables for any module that depends on them.
# Resolves issues where Streamlit or scripts import utilities.* before load_dotenv
# is called elsewhere.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

# Re-export load_dotenv for modules that may need to refresh it manually.
__all__ = ["load_dotenv"]
