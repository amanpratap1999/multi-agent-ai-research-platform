import os
import sys
from pathlib import Path

import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Enforce test environment flags before app import
os.environ["ENVIRONMENT"] = "test"
os.environ["USE_BEDROCK_MOCK"] = "true"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["REDIS_HOST"] = "localhost"

from app.defense.bedrock_guardrail import guardrail_client


@pytest.fixture(autouse=True)
def ensure_mock_bedrock():
    """Ensure Bedrock guardrail client is in mock mode for zero-credential test runs."""
    guardrail_client.use_mock = True
    yield
