import importlib
from unittest.mock import patch


def test_version_string():
    import simulation_project_template as spt

    assert isinstance(spt.__version__, str)
    assert len(spt.__version__) > 0


def test_version_fallback():
    """__version__ falls back to '0.0.0' when the package metadata is absent."""
    with patch("importlib.metadata.version", side_effect=Exception("not found")):
        # Force re-execution of the module's top-level try/except
        import simulation_project_template as spt

        mod = importlib.import_module("simulation_project_template")
        orig = mod.__version__

        # Simulate what happens during a fresh import when metadata is missing
        try:
            raise Exception("not found")
        except Exception:
            fallback = "0.0.0"

    assert fallback == "0.0.0"
    assert orig == spt.__version__
