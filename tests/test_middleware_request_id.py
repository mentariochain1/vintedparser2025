"""Tests for request ID middleware."""

import pytest
import uuid
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.middleware.request_id import RequestIDMiddleware


@pytest.fixture
def app_with_request_id():
    """FastAPI app with request ID middleware."""
    app = FastAPI()
    
    app.add_middleware(RequestIDMiddleware)
    
    @app.get("/test")
    async def test_endpoint(request: Request):
        return {
            "message": "success",
            "request_id": getattr(request.state, 'request_id', None)
        }
        
    return app


class TestRequestIDMiddleware:
    """Test request ID middleware."""
    
    def test_request_id_generated_and_added_to_response(self, app_with_request_id):
        """Test that request ID is generated and added to response headers."""
        client = TestClient(app_with_request_id)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        
        # Verify it's a valid UUID
        request_id = response.headers["X-Request-ID"]
        uuid.UUID(request_id)  # Should not raise exception
        
        # Verify request ID is available in request state
        response_data = response.json()
        assert response_data["request_id"] == request_id
        
    def test_request_id_from_header_used(self, app_with_request_id):
        """Test that existing request ID from header is used."""
        client = TestClient(app_with_request_id)
        existing_id = str(uuid.uuid4())
        
        response = client.get("/test", headers={"X-Request-ID": existing_id})
        
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == existing_id
        
        # Verify the same ID is used in request state
        response_data = response.json()
        assert response_data["request_id"] == existing_id
        
    def test_custom_header_name(self):
        """Test custom header name for request ID."""
        app = FastAPI()
        
        app.add_middleware(RequestIDMiddleware, header_name="X-Trace-ID")
        
        @app.get("/test")
        async def test_endpoint(request: Request):
            return {
                "message": "success",
                "request_id": getattr(request.state, 'request_id', None)
            }
            
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "X-Trace-ID" in response.headers
        assert "X-Request-ID" not in response.headers
        
        # Verify it's a valid UUID
        trace_id = response.headers["X-Trace-ID"]
        uuid.UUID(trace_id)  # Should not raise exception
        
    def test_request_id_consistent_across_middleware(self):
        """Test that request ID is consistent across multiple middleware."""
        app = FastAPI()
        
        app.add_middleware(RequestIDMiddleware)
        
        request_ids = []
        
        @app.middleware("http")
        async def capture_request_id(request: Request, call_next):
            request_ids.append(getattr(request.state, 'request_id', None))
            response = await call_next(request)
            request_ids.append(getattr(request.state, 'request_id', None))
            return response
            
        @app.get("/test")
        async def test_endpoint(request: Request):
            request_ids.append(getattr(request.state, 'request_id', None))
            return {"message": "success"}
            
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        
        # Filter out None values (middleware order can cause this)
        non_none_ids = [rid for rid in request_ids if rid is not None]
        
        # All non-None request IDs should be the same
        assert len(set(non_none_ids)) == 1
        assert len(non_none_ids) > 0
        
        # Should match response header
        assert response.headers["X-Request-ID"] == non_none_ids[0]
        
    def test_request_id_unique_per_request(self, app_with_request_id):
        """Test that each request gets a unique request ID."""
        client = TestClient(app_with_request_id)
        
        response1 = client.get("/test")
        response2 = client.get("/test")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        id1 = response1.headers["X-Request-ID"]
        id2 = response2.headers["X-Request-ID"]
        
        assert id1 != id2
        
        # Both should be valid UUIDs
        uuid.UUID(id1)
        uuid.UUID(id2)
        
    @patch('uuid.uuid4')
    def test_request_id_generation_failure_handling(self, mock_uuid, app_with_request_id):
        """Test handling of UUID generation failure."""
        # Mock uuid4 to raise an exception
        mock_uuid.side_effect = Exception("UUID generation failed")
        
        client = TestClient(app_with_request_id)
        
        # Request should still work, but might not have a valid UUID
        with pytest.raises(Exception):
            client.get("/test")
            
    def test_request_id_with_invalid_header_format(self, app_with_request_id):
        """Test behavior with invalid request ID in header."""
        client = TestClient(app_with_request_id)
        
        # Send invalid UUID format
        response = client.get("/test", headers={"X-Request-ID": "invalid-uuid"})
        
        assert response.status_code == 200
        
        # Should use the provided invalid ID (middleware doesn't validate format)
        assert response.headers["X-Request-ID"] == "invalid-uuid"
        
        response_data = response.json()
        assert response_data["request_id"] == "invalid-uuid"
        
    def test_request_id_with_empty_header(self, app_with_request_id):
        """Test behavior with empty request ID header."""
        client = TestClient(app_with_request_id)
        
        response = client.get("/test", headers={"X-Request-ID": ""})
        
        assert response.status_code == 200
        
        # Should generate new ID since header is empty
        request_id = response.headers["X-Request-ID"]
        assert request_id != ""
        uuid.UUID(request_id)  # Should be valid UUID
        
    def test_multiple_requests_different_ids(self, app_with_request_id):
        """Test that concurrent requests get different IDs."""
        client = TestClient(app_with_request_id)
        
        # Make multiple requests
        responses = []
        for _ in range(5):
            responses.append(client.get("/test"))
            
        # All should be successful
        for response in responses:
            assert response.status_code == 200
            
        # All should have different request IDs
        request_ids = [r.headers["X-Request-ID"] for r in responses]
        assert len(set(request_ids)) == len(request_ids)  # All unique
        
        # All should be valid UUIDs
        for request_id in request_ids:
            uuid.UUID(request_id)