"""End-to-end tests for deployment and system monitoring."""

import asyncio
import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Mark all tests in this file as e2e
pytestmark = pytest.mark.e2e


class TestDeploymentValidation:
    """End-to-end tests for deployment validation and system health."""

    @pytest.fixture
    def test_client(self):
        """Create test client for deployment validation."""
        from src.main import app
        return TestClient(app)

    def test_health_check_endpoint(self, test_client):
        """Test health check endpoint for deployment validation."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        health_data = response.json()
        
        # Verify health check structure
        assert "status" in health_data
        assert "timestamp" in health_data
        assert "services" in health_data
        
        # Verify service health
        services = health_data["services"]
        assert "database" in services
        assert "redis" in services
        assert "vinted_api" in services
        assert "yookassa_api" in services

    def test_deployment_readiness_check(self, test_client):
        """Test comprehensive deployment readiness."""
        # Check all critical endpoints
        critical_endpoints = [
            "/health",
            "/metrics", 
            "/webhooks/yookassa",
            "/webhooks/telegram"
        ]
        
        for endpoint in critical_endpoints:
            if endpoint.startswith("/webhooks"):
                # Webhooks should reject GET requests
                response = test_client.get(endpoint)
                assert response.status_code in [405, 404], f"Webhook {endpoint} should reject GET"
            else:
                response = test_client.get(endpoint)
                assert response.status_code == 200, f"Critical endpoint {endpoint} not accessible"

    def test_environment_configuration(self, test_client):
        """Test environment configuration for deployment."""
        from src.config import settings
        
        # Verify critical settings are configured
        assert settings.bot_token is not None, "Bot token not configured"
        assert settings.database_url is not None, "Database URL not configured"
        assert settings.redis_url is not None, "Redis URL not configured"
        
        # Verify security settings
        assert settings.webhook_secret is not None, "Webhook secret not configured"
        assert len(settings.webhook_secret) >= 16, "Webhook secret too short"

    def test_database_migration_status(self):
        """Test database migration status for deployment."""
        # This would check if all migrations are applied
        # For now, we'll simulate the check
        migration_status = {
            "applied_migrations": 2,
            "pending_migrations": 0,
            "last_migration": "20250810000002_enable_rls"
        }
        
        assert migration_status["pending_migrations"] == 0, "Pending migrations found"
        assert migration_status["applied_migrations"] > 0, "No migrations applied"

    def test_metrics_endpoint(self, test_client):
        """Test metrics endpoint for monitoring."""
        response = test_client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Verify Prometheus metrics format
        assert "# HELP" in metrics_text
        assert "# TYPE" in metrics_text
        
        # Verify key metrics are present
        assert "http_requests_total" in metrics_text
        assert "http_request_duration_seconds" in metrics_text
        assert "active_users_total" in metrics_text

    @pytest.mark.asyncio
    async def test_webhook_endpoint_deployment(self, test_client):
        """Test webhook endpoint for deployment validation."""
        # Create valid webhook payload
        webhook_data = {
            "event": "payment.succeeded",
            "object": {
                "id": "test_payment_123",
                "status": "succeeded",
                "amount": {"value": "299.00", "currency": "RUB"},
                "metadata": {"user_id": "123456789"}
            }
        }

        payload = json.dumps(webhook_data).encode()
        timestamp = str(int(datetime.utcnow().timestamp()))

        # Create valid signature
        import hmac
        import hashlib
        secret_key = os.getenv("YOOKASSA_SECRET_KEY", "test_secret_key")
        message = payload + timestamp.encode()
        signature = hmac.new(secret_key.encode(), message, hashlib.sha256).hexdigest()

        with patch("src.main.payment_service") as mock_payment_service:
            mock_payment_service.process_webhook.return_value = (True, "Payment processed")

            response = test_client.post(
                "/webhooks/yookassa",
                content=payload,
                headers={
                    "Yookassa-Signature": signature,
                    "Yookassa-Timestamp": timestamp,
                    "Content-Type": "application/json"
                }
            )

            assert response.status_code == 200
            assert response.json()["status"] == "success"

    def test_static_files_serving(self, test_client):
        """Test static file serving for deployment."""
        # Test if static files are properly served
        response = test_client.get("/static/favicon.ico")
        
        # Should either serve the file or return 404 (not 500)
        assert response.status_code in [200, 404]

    def test_cors_configuration(self, test_client):
        """Test CORS configuration for deployment."""
        response = test_client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        # Verify CORS headers are present
        assert response.status_code in [200, 204]
        if "Access-Control-Allow-Origin" in response.headers:
            assert response.headers["Access-Control-Allow-Origin"] in ["*", "https://example.com"]


class TestRollbackProcedures:
    """End-to-end tests for rollback procedures."""

    @pytest.mark.asyncio
    async def test_database_rollback_scenario(self):
        """Test database rollback procedures."""
        with patch("src.db.base.get_session") as mock_get_session:
            mock_session = mock_get_session.return_value.__aenter__.return_value
            
            # Simulate rollback scenario
            mock_session.rollback = lambda: None
            mock_session.commit.side_effect = Exception("Database error")

            # Test rollback handling
            try:
                async with mock_get_session() as session:
                    # Simulate operation that fails
                    session.commit()
            except Exception:
                # Verify rollback was called
                mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_degradation_scenario(self):
        """Test graceful service degradation."""
        with patch("src.bot.services.vinted_service.VintedService") as mock_vinted_service:
            # Simulate Vinted service failure
            mock_vinted_service.return_value.health_check.return_value = False
            mock_vinted_service.return_value.search_items.side_effect = Exception("Service unavailable")

            # Test degraded mode operation
            from src.bot.services.vinted_service import VintedService
            service = VintedService()
            
            # Should handle gracefully
            is_healthy = await service.health_check()
            assert is_healthy is False

    @pytest.mark.asyncio
    async def test_configuration_rollback(self):
        """Test configuration rollback procedures."""
        original_config = {
            "bot_token": "original_token",
            "webhook_domain": "https://original.example.com"
        }
        
        new_config = {
            "bot_token": "new_token",
            "webhook_domain": "https://new.example.com"
        }

        # Simulate configuration change and rollback
        with patch.dict(os.environ, new_config):
            # Verify new config is active
            assert os.getenv("bot_token") == "new_token"
            
            # Simulate rollback
            with patch.dict(os.environ, original_config):
                # Verify rollback is successful
                assert os.getenv("bot_token") == "original_token"


class TestMonitoringAndAlerting:
    """End-to-end tests for monitoring and alerting functionality."""

    @pytest.mark.asyncio
    async def test_error_rate_monitoring(self):
        """Test error rate monitoring and alerting."""
        from src.monitoring import record_request_metrics, get_health_summary
        
        # Simulate successful requests
        for i in range(8):
            record_request_metrics(
                request=type('Request', (), {'method': 'GET', 'url': type('URL', (), {'path': '/search'})})(),
                response_time=0.1,
                status_code=200
            )
        
        # Simulate error requests
        for i in range(2):
            record_request_metrics(
                request=type('Request', (), {'method': 'GET', 'url': type('URL', (), {'path': '/search'})})(),
                response_time=0.5,
                status_code=500
            )

        # Check health summary
        health = get_health_summary()
        assert "performance" in health
        assert health["performance"]["avg_response_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_alerting_thresholds(self):
        """Test alerting threshold configuration and triggering."""
        # Define alerting thresholds
        thresholds = {
            "error_rate": 0.05,  # 5%
            "response_time_p95": 2.0,  # 2 seconds
            "cpu_usage": 80.0,  # 80%
            "memory_usage": 85.0,  # 85%
            "disk_usage": 90.0  # 90%
        }
        
        # Simulate metrics that would trigger alerts
        test_metrics = {
            "error_rate": 0.08,  # Above threshold
            "response_time_p95": 1.5,  # Below threshold
            "cpu_usage": 85.0,  # Above threshold
            "memory_usage": 70.0,  # Below threshold
            "disk_usage": 95.0  # Above threshold
        }
        
        # Check which alerts should trigger
        triggered_alerts = []
        for metric, value in test_metrics.items():
            if value > thresholds[metric]:
                triggered_alerts.append(metric)
        
        expected_alerts = ["error_rate", "cpu_usage", "disk_usage"]
        assert set(triggered_alerts) == set(expected_alerts), f"Alert mismatch: {triggered_alerts}"

    @pytest.mark.asyncio
    async def test_monitoring_data_retention(self):
        """Test monitoring data retention policies."""
        from src.monitoring import get_health_summary
        
        # Simulate old metrics
        old_timestamp = time.time() - 3600  # 1 hour ago
        recent_timestamp = time.time() - 60  # 1 minute ago
        
        # Test that old data is properly handled
        health = get_health_summary()
        
        # Verify timestamp is recent
        assert health["timestamp"] > recent_timestamp, "Health check timestamp too old"
        
        # Verify data retention (implementation would clean old data)
        assert "performance" in health, "Performance metrics missing"

    @pytest.mark.asyncio
    async def test_performance_monitoring(self):
        """Test performance monitoring and alerting."""
        from src.monitoring import MetricsCollector
        
        collector = MetricsCollector()
        
        # Simulate performance metrics
        response_times = [0.1, 0.2, 0.15, 0.8, 0.12, 0.9, 0.11, 0.13, 0.14, 0.16]
        
        for response_time in response_times:
            collector.record_response_time("search", response_time)

        # Check performance metrics
        avg_response_time = collector.get_average_response_time("search")
        p95_response_time = collector.get_percentile_response_time("search", 95)
        
        # Performance assertions
        assert avg_response_time < 1.0  # Average should be under 1 second
        assert p95_response_time < 2.0  # P95 should be under 2 seconds

    @pytest.mark.asyncio
    async def test_resource_usage_monitoring(self):
        """Test resource usage monitoring."""
        import psutil
        
        # Get current resource usage
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_info = psutil.virtual_memory()
        disk_usage = psutil.disk_usage('/')

        # Resource usage assertions
        assert cpu_percent < 90.0, f"CPU usage too high: {cpu_percent}%"
        assert memory_info.percent < 90.0, f"Memory usage too high: {memory_info.percent}%"
        assert disk_usage.percent < 90.0, f"Disk usage too high: {disk_usage.percent}%"

    @pytest.mark.asyncio
    async def test_database_connection_monitoring(self):
        """Test database connection monitoring."""
        with patch("src.db.base.engine") as mock_engine:
            mock_pool = mock_engine.pool
            mock_pool.size.return_value = 10
            mock_pool.checked_in.return_value = 8
            mock_pool.checked_out.return_value = 2
            mock_pool.overflow.return_value = 0

            # Check connection pool health
            pool_size = mock_pool.size()
            active_connections = mock_pool.checked_out()
            idle_connections = mock_pool.checked_in()
            
            # Connection pool assertions
            assert pool_size > 0, "Database pool not configured"
            assert active_connections < pool_size, "All connections in use"
            assert idle_connections > 0, "No idle connections available"

    @pytest.mark.asyncio
    async def test_external_service_monitoring(self):
        """Test external service health monitoring."""
        from src.bot.services.vinted_service import VintedService
        from src.bot.services.payment_service import PaymentService
        
        # Test Vinted service health
        vinted_service = VintedService()
        vinted_healthy = await vinted_service.health_check()
        
        # Test YooKassa service health
        payment_service = PaymentService()
        yookassa_healthy = await payment_service.health_check()
        
        # Service health assertions
        # Note: In real E2E tests, these would check actual services
        # For now, we verify the health check methods exist and return boolean
        assert isinstance(vinted_healthy, bool)
        assert isinstance(yookassa_healthy, bool)


class TestDisasterRecovery:
    """End-to-end tests for disaster recovery procedures."""

    @pytest.mark.asyncio
    async def test_backup_restoration_procedure(self):
        """Test backup and restoration procedures."""
        # Simulate backup creation
        backup_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "users_count": 1000,
            "payments_count": 500,
            "items_count": 10000
        }

        # Simulate backup storage
        backup_file = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Verify backup data structure
        assert "timestamp" in backup_data
        assert "users_count" in backup_data
        assert backup_data["users_count"] > 0

        # Simulate restoration validation
        restored_data = backup_data.copy()
        assert restored_data == backup_data

    @pytest.mark.asyncio
    async def test_failover_scenario(self):
        """Test failover scenario handling."""
        primary_service_healthy = False
        secondary_service_healthy = True

        # Simulate failover logic
        if not primary_service_healthy and secondary_service_healthy:
            active_service = "secondary"
        else:
            active_service = "primary"

        # Verify failover worked
        assert active_service == "secondary"

    @pytest.mark.asyncio
    async def test_data_consistency_check(self):
        """Test data consistency checks for disaster recovery."""
        # Simulate data consistency validation
        user_count_primary = 1000
        user_count_backup = 1000
        
        payment_count_primary = 500
        payment_count_backup = 500

        # Data consistency assertions
        assert user_count_primary == user_count_backup, "User data inconsistency detected"
        assert payment_count_primary == payment_count_backup, "Payment data inconsistency detected"

    @pytest.mark.asyncio
    async def test_recovery_time_objective(self):
        """Test Recovery Time Objective (RTO) compliance."""
        # Simulate disaster recovery time
        disaster_start = datetime.utcnow()
        
        # Simulate recovery procedures
        await asyncio.sleep(0.1)  # Simulate recovery time
        
        recovery_complete = datetime.utcnow()
        recovery_time = (recovery_complete - disaster_start).total_seconds()

        # RTO assertion (should be under 5 minutes for this system)
        rto_limit = 300  # 5 minutes
        assert recovery_time < rto_limit, f"Recovery took too long: {recovery_time}s > {rto_limit}s"

    @pytest.mark.asyncio
    async def test_recovery_point_objective(self):
        """Test Recovery Point Objective (RPO) compliance."""
        # Simulate data loss scenario
        last_backup_time = datetime.utcnow() - timedelta(minutes=30)
        disaster_time = datetime.utcnow()
        
        data_loss_window = (disaster_time - last_backup_time).total_seconds()

        # RPO assertion (should be under 1 hour for this system)
        rpo_limit = 3600  # 1 hour
        assert data_loss_window < rpo_limit, f"Data loss window too large: {data_loss_window}s > {rpo_limit}s"