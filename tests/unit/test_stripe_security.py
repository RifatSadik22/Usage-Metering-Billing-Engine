import pytest

from app.core.config import Settings
from app.services.stripe_service import StripeService


def test_live_secret_key_is_rejected() -> None:
    settings = Settings(stripe_secret_key="sk_live_forbidden")
    with pytest.raises(RuntimeError, match="test-mode"):
        StripeService(settings)


def test_live_restricted_key_is_rejected() -> None:
    settings = Settings(stripe_secret_key="rk_live_forbidden")
    with pytest.raises(RuntimeError, match="test-mode"):
        StripeService(settings)
