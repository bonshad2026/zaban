import os
import secrets
import tempfile

# Test-only values, generated on every run. Nothing secret is stored in the repository.
# These must be set before zaban is imported, because settings are read at import time.
_TMP_DIR = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test.db"
os.environ["ENVIRONMENT"] = "development"
os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
os.environ["ZABAN_DEMO_API_KEY"] = secrets.token_urlsafe(24)
os.environ["ZABAN_DEMO_PARENT_EMAIL"] = "test-parent@example.com"
os.environ["ZABAN_DEMO_PARENT_PASSWORD"] = secrets.token_urlsafe(12)
os.environ["ZABAN_DEMO_STUDENT_USERNAME"] = "test-student"
os.environ["ZABAN_DEMO_STUDENT_PASSWORD"] = secrets.token_urlsafe(12)
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from zaban.main import app  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
