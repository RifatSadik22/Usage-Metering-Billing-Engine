import pytest

from scripts.seed import seed


@pytest.fixture(scope="session")
def seeded_database():
    yield seed()
