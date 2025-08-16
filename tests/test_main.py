"""Test main application module."""

import pytest
from fastapi .testclient import TestClient

from src .main import create_app

@pytest .fixture
def client ():
    """Create test client."""
    app =create_app ()
    return TestClient (app )

def test_health_check (client ):
    """Test health check endpoint."""
    response =client .get ("/health")
    assert response .status_code ==200

    data =response .json ()
    assert data ["status"]=="healthy"
    assert "environment"in data

def test_app_creation ():
    """Test that app can be created successfully."""
    app =create_app ()
    assert app .title =="Vinted Parser Bot"
    assert app .version =="0.1.0"