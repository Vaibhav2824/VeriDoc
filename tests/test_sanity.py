"""Sanity checks: Python version and core deps are importable."""

import sys


def test_python_version() -> None:
    assert sys.version_info >= (3, 11), "Python 3.11+ required"


def test_pydantic_v2() -> None:
    import pydantic

    assert int(pydantic.VERSION.split(".")[0]) >= 2, "Pydantic v2+ required"


def test_google_genai_importable() -> None:
    from google import genai  # noqa: F401  # google-genai SDK


def test_pypdfium2_importable() -> None:
    import pypdfium2  # noqa: F401


def test_pillow_importable() -> None:
    from PIL import Image  # noqa: F401
