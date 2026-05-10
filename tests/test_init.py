import importlib
from unittest.mock import patch


def test_version_string():
    import simulation_project_template as spt

    assert isinstance(spt.__version__, str)
    assert len(spt.__version__) > 0


def test_version_fallback():
    """__version__ falls back to '0.0.0' when the package metadata is absent."""
    import simulation_project_template as spt

    with patch("importlib.metadata.version", side_effect=Exception("not found")):
        reloaded = importlib.reload(spt)
        assert reloaded.__version__ == "0.0.0"

    # Restore the module after the patch context.
    importlib.reload(spt)
