from app.config import settings
from app.main import app


def test_expected_routes_are_registered():
    paths = {route.path for route in app.routes}

    assert "/" in paths
    assert "/health" in paths
    assert "/models" in paths
    assert "/activate" in paths
    assert "/deactivate" in paths
    assert "/generate-code" in paths
    assert "/fix-code" in paths


def test_allowed_origins_are_parsed_from_env_string():
    assert settings.ALLOWED_ORIGINS
    assert isinstance(settings.ALLOWED_ORIGINS, str)
