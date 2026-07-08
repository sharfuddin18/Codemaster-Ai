from backend.app.config import settings
from backend.app.main import app
from fastapi.routing import APIRoute

def test_expected_routes_are_registered():
    # We filter specifically for APIRoute objects to avoid _IncludedRouter errors
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}

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
