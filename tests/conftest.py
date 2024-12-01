
import pytest
from pathlib import Path

@pytest.fixture
def output_dir(tmp_path):
    """Provide a temporary directory for test outputs"""
    output = tmp_path / "output"
    output.mkdir()
    return output