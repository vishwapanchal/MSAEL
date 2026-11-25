import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    # DATA_DIR is read on every request, so each test gets a fresh database.
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return TestClient(app)
