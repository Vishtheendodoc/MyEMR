import pytest

from app.services import rate_limit


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    """The login limiter is in memory, so earlier tests must not lock out later ones."""
    rate_limit._ATTEMPTS.clear()
    yield
    rate_limit._ATTEMPTS.clear()
