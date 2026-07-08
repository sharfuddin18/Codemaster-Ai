from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_expected_routes_exist():
    # We test by actually trying to reach the endpoints
    # This is more reliable than inspecting internal app.routes
    expected_paths = ["/", "/health", "/models", "/activate", "/deactivate", "/generate-code", "/fix-code"]
    
    # We perform an OPTIONS request to the root or check the openapi schema
    # to verify routes are registered correctly
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {}).keys()
    
    for path in expected_paths:
        assert path in paths, f"Route {path} not found in OpenAPI schema"
