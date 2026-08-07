import os

import pytest

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["LLM_PROVIDER"] = "mock"

from app.core.database import engine
from app.models import Base


@pytest.fixture(autouse=True)
def reset_application_database():  # type: ignore[no-untyped-def]
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
