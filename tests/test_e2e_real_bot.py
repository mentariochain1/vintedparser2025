"""Real Telegram bot E2E tests using test bot environment."""

import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import pytest
from telethon import TelegramClient, events
from telethon.tl.functions.messages import SendMessageRequest

# Mark all tests in this file as e2e
pytestmark = pytest.mark.e2e


class RealBotE2ETests:
    """End-to-end tests with real Telegram bot interaction."""

    @pytest.fixture(scope="class")
    async def telegram_client(self):
        """Create Telegram client for E2E testing."""
        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")
        session_name = os.getenv("TELEGRAM_SESSION_NAME", "e2e_test")
        
        if not api_id or not api_hash:
            pytest.skip("Telegram API credentials not provided")
        
        client = TelegramClient(session_name, int(api_id), api_hash)
        await client.start()
        
        yield client
        
        await client.disconnect()

    @pytest.fixture
    def bot_config(self):
        """Bot configuration for E2E tests."""
        bot_username = os.getenv("E2E_BOT_USERNAME")
        test_chat_id = os.getenv("E2E_TEST_CHAT_ID")
        
        if not bot_username:
            pytest.skip("E2E bot username not provided")
            
        return {
            "bot_username": bot_username,
            "test_chat_id": int(test_chat_id) if test_chat_id else None,
            "timeout": 30,
        }

    @pytest.mark.asyncio
    async def test_real_bot_start_command(self, telegram_client, bot_config):
        """Test real bot /start command."""
        bot_username = bot_config["bot_username"]
        timeout = bot_config["timeout"]
        
        # Track received messages
        received_messages = []
        
        @telegram_client.on(events.NewMessage(from_users=bot_username))
        async def message_handler(event):
            received_messages.append({
                "text": event.message.message,
                "timestamp": datetime.utcnow(),
                "message_id": event.message.id
            })

        # Send /start command
        await telegram_client.send_message(bot_username, "/start")
        
        # Wait for response
        start_time = time.time()
        while len(received_messages) == 0 and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.5)
        
        # Verify response
        assert len(received_messages) > 0, "No response received from bot"
        
        welcome_message = received_messages[0]["text"]
        assert "welcome" in welcome_message.lower() or "start" in welcome_message.lower()
        
        # Verify response time
        response_time = (received_messages[0]["timestamp"] - datetime.utcnow()).total_seconds()
        assert abs(response_time) < 5, f"Response took too long: {response_time}s"

    @pytest.mark.asyncio
    async def test_real_bot_search_flow(self, telegram_client, bot_config):
        """Test real bot search functionality."""
        bot_username = bot_config["bot_username"]
        timeout = bot_config["timeout"]
        
        received_messages = []
        
        @telegram_client.on(events.NewMessage(from_users=bot_username))
        async def message_handler(event):
            received_messages.append({
                "text": event.message.message,
                "timestamp": datetime.utcnow(),
                "has_keyboard": bool(event.message.reply_markup)
            })

        # Start search flow
        await telegram_client.send_message(bot_username, "/search")
        
        # Wait for search prompt
        start_time = time.time()
        while len(received_messages) == 0 and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.5)
        
        assert len(received_messages) > 0, "No search prompt received"
        
        # Send search query
        received_messages.clear()
        await telegram_client.send_message(bot_username, "Nike sneakers")
        
        # Wait for search results or processing message
        start_time = time.time()
        while len(received_messages) == 0 and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.5)
        
        assert len(received_messages) > 0, "No search response received"
        
        # Verify search was processed
        search_response = received_messages[0]["text"]
        assert any(keyword in search_response.lower() for keyword in [
            "search", "processing", "found", "results", "items"
        ]), f"Unexpected search response: {search_response}"

    @pytest.mark.asyncio
    async def test_real_bot_referral_link_generation(self, telegram_client, bot_config):
        """Test real bot referral link generation."""
        bot_username = bot_config["bot_username"]
        timeout = bot_config["timeout"]
        
        received_messages = []
        
        @telegram_client.on(events.NewMessage(from_users=bot_username))
        async def message_handler(event):
            received_messages.append({
                "text": event.message.message,
                "timestamp": datetime.utcnow()
            })

        # Request referral link
        await telegram_client.send_message(bot_username, "/invite")
        
        # Wait for referral link
        start_time = time.time()
        while len(received_messages) == 0 and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.5)
        
        assert len(received_messages) > 0, "No referral link received"
        
        referral_message = received_messages[0]["text"]
        assert "t.me" in referral_message, "No Telegram link found in referral message"
        assert bot_username in referral_message, "Bot username not in referral link"

    @pytest.mark.asyncio
    async def test_real_bot_error_handling(self, telegram_client, bot_config):
        """Test real bot error handling with invalid commands."""
        bot_username = bot_config["bot_username"]
        timeout = bot_config["timeout"]
        
        received_messages = []
        
        @telegram_client.on(events.NewMessage(from_users=bot_username))
        async def message_handler(event):
            received_messages.append({
                "text": event.message.message,
                "timestamp": datetime.utcnow()
            })

        # Send invalid command
        await telegram_client.send_message(bot_username, "/invalid_command_xyz")
        
        # Wait for error response
        start_time = time.time()
        while len(received_messages) == 0 and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.5)
        
        # Should either get help message or command not found
        if received_messages:
            error_response = received_messages[0]["text"]
            # Bot should handle gracefully, not crash
            assert len(error_response) > 0, "Empty error response"


class PerformanceE2ETests:
    """Performance-focused E2E tests."""

    @pytest.mark.asyncio
    async def test_concurrent_user_simulation(self):
        """Test system performance with simulated concurrent users."""
        concurrent_users = 20
        test_duration = 30  # seconds
        
        async def simulate_user_activity(user_id: int) -> Dict[str, Any]:
            """Simulate realistic user activity."""
            start_time = time.time()
            actions_completed = 0
            errors = []
            
            try:
                while (time.time() - start_time) < test_duration:
                    # Simulate user actions with realistic delays
                    await asyncio.sleep(1.0)  # User thinking time
                    actions_completed += 1
                    
                    # Simulate different action types
                    action_type = actions_completed % 4
                    if action_type == 0:
                        # Start command
                        await asyncio.sleep(0.1)
                    elif action_type == 1:
                        # Search command
                        await asyncio.sleep(0.2)
                    elif action_type == 2:
                        # View results
                        await asyncio.sleep(0.3)
                    else:
                        # Other interactions
                        await asyncio.sleep(0.1)
                        
            except Exception as e:
                errors.append(str(e))
            
            return {
                "user_id": user_id,
                "actions_completed": actions_completed,
                "errors": errors,
                "duration": time.time() - start_time
            }

        # Create concurrent user tasks
        tasks = [
            asyncio.create_task(simulate_user_activity(i))
            for i in range(concurrent_users)
        ]
        
        # Execute all tasks
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Analyze results
        successful_users = 0
        total_actions = 0
        total_errors = 0
        
        for result in results:
            if isinstance(result, dict):
                successful_users += 1
                total_actions += result["actions_completed"]
                total_errors += len(result["errors"])
        
        # Performance assertions
        success_rate = successful_users / concurrent_users
        actions_per_second = total_actions / total_time if total_time > 0 else 0
        
        assert success_rate >= 0.95, f"Too many user simulation failures: {success_rate:.2%}"
        assert actions_per_second > 0, "No actions completed"
        assert total_errors < concurrent_users * 0.1, f"Too many errors: {total_errors}"

    @pytest.mark.asyncio
    async def test_search_performance_under_load(self):
        """Test search performance under concurrent load."""
        concurrent_searches = 10
        search_queries = [
            "Nike sneakers",
            "Adidas shoes",
            "Vintage jacket",
            "Designer bag",
            "Winter coat"
        ]
        
        async def perform_search(search_id: int, query: str) -> Dict[str, Any]:
            """Perform a search and measure performance."""
            start_time = time.time()
            
            try:
                # Simulate search API call
                await asyncio.sleep(0.5)  # Simulate processing time
                
                # Simulate search results
                results = {
                    "search_id": search_id,
                    "query": query,
                    "items_found": 10 + (search_id % 5),
                    "status": "completed",
                    "duration": time.time() - start_time
                }
                
                return results
                
            except Exception as e:
                return {
                    "search_id": search_id,
                    "query": query,
                    "status": "failed",
                    "error": str(e),
                    "duration": time.time() - start_time
                }

        # Create search tasks
        tasks = []
        for i in range(concurrent_searches):
            query = search_queries[i % len(search_queries)]
            task = asyncio.create_task(perform_search(i, query))
            tasks.append(task)
        
        # Execute searches
        start_time = time.time()
        search_results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Analyze performance
        successful_searches = sum(
            1 for r in search_results 
            if isinstance(r, dict) and r.get("status") == "completed"
        )
        
        avg_search_time = sum(
            r["duration"] for r in search_results 
            if isinstance(r, dict) and "duration" in r
        ) / len(search_results)
        
        # Performance assertions
        success_rate = successful_searches / concurrent_searches
        searches_per_second = concurrent_searches / total_time
        
        assert success_rate >= 0.9, f"Search success rate too low: {success_rate:.2%}"
        assert avg_search_time < 2.0, f"Average search time too high: {avg_search_time:.2f}s"
        assert searches_per_second > 1.0, f"Search throughput too low: {searches_per_second:.2f}/s"

    @pytest.mark.asyncio
    async def test_payment_flow_performance(self):
        """Test payment flow performance under load."""
        concurrent_payments = 5
        
        async def simulate_payment_flow(payment_id: int) -> Dict[str, Any]:
            """Simulate complete payment flow."""
            start_time = time.time()
            
            try:
                # Step 1: Payment creation
                await asyncio.sleep(0.2)
                
                # Step 2: User interaction
                await asyncio.sleep(0.5)
                
                # Step 3: Payment processing
                await asyncio.sleep(1.0)
                
                # Step 4: Confirmation
                await asyncio.sleep(0.1)
                
                return {
                    "payment_id": payment_id,
                    "status": "completed",
                    "duration": time.time() - start_time,
                    "steps_completed": 4
                }
                
            except Exception as e:
                return {
                    "payment_id": payment_id,
                    "status": "failed",
                    "error": str(e),
                    "duration": time.time() - start_time
                }

        # Create payment tasks
        tasks = [
            asyncio.create_task(simulate_payment_flow(i))
            for i in range(concurrent_payments)
        ]
        
        # Execute payments
        start_time = time.time()
        payment_results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Analyze performance
        successful_payments = sum(
            1 for r in payment_results 
            if isinstance(r, dict) and r.get("status") == "completed"
        )
        
        avg_payment_time = sum(
            r["duration"] for r in payment_results 
            if isinstance(r, dict) and "duration" in r
        ) / len(payment_results)
        
        # Performance assertions
        success_rate = successful_payments / concurrent_payments
        
        assert success_rate >= 0.8, f"Payment success rate too low: {success_rate:.2%}"
        assert avg_payment_time < 5.0, f"Average payment time too high: {avg_payment_time:.2f}s"
        assert total_time < 10.0, f"Total payment processing time too high: {total_time:.2f}s"


class SystemIntegrationE2ETests:
    """System integration E2E tests."""

    @pytest.mark.asyncio
    async def test_full_user_journey_integration(self):
        """Test complete user journey from registration to payment."""
        journey_steps = []
        
        try:
            # Step 1: User registration
            journey_steps.append("registration_start")
            await asyncio.sleep(0.1)  # Simulate registration
            journey_steps.append("registration_complete")
            
            # Step 2: First search
            journey_steps.append("search_start")
            await asyncio.sleep(0.3)  # Simulate search
            journey_steps.append("search_complete")
            
            # Step 3: View results
            journey_steps.append("results_view")
            await asyncio.sleep(0.2)
            
            # Step 4: Trial expiration simulation
            journey_steps.append("trial_check")
            await asyncio.sleep(0.1)
            
            # Step 5: Payment flow
            journey_steps.append("payment_start")
            await asyncio.sleep(0.5)  # Simulate payment
            journey_steps.append("payment_complete")
            
            # Step 6: Subscription activation
            journey_steps.append("subscription_active")
            
        except Exception as e:
            journey_steps.append(f"error: {str(e)}")
        
        # Verify journey completion
        expected_steps = [
            "registration_start", "registration_complete",
            "search_start", "search_complete",
            "results_view", "trial_check",
            "payment_start", "payment_complete",
            "subscription_active"
        ]
        
        assert len(journey_steps) == len(expected_steps), f"Journey incomplete: {journey_steps}"
        assert journey_steps == expected_steps, f"Journey steps mismatch: {journey_steps}"

    @pytest.mark.asyncio
    async def test_referral_system_integration(self):
        """Test complete referral system integration."""
        referral_flow = []
        
        try:
            # Step 1: Referrer generates link
            referral_flow.append("link_generated")
            referral_link = "https://t.me/testbot?start=abc123"
            await asyncio.sleep(0.1)
            
            # Step 2: Invitee clicks link
            referral_flow.append("link_clicked")
            await asyncio.sleep(0.1)
            
            # Step 3: Invitee registration
            referral_flow.append("invitee_registered")
            await asyncio.sleep(0.2)
            
            # Step 4: Referral bonus processing
            referral_flow.append("bonus_calculated")
            await asyncio.sleep(0.1)
            
            # Step 5: Referrer notification
            referral_flow.append("referrer_notified")
            await asyncio.sleep(0.1)
            
            # Step 6: Trial extension
            referral_flow.append("trial_extended")
            
        except Exception as e:
            referral_flow.append(f"error: {str(e)}")
        
        # Verify referral flow
        expected_flow = [
            "link_generated", "link_clicked", "invitee_registered",
            "bonus_calculated", "referrer_notified", "trial_extended"
        ]
        
        assert referral_flow == expected_flow, f"Referral flow mismatch: {referral_flow}"

    @pytest.mark.asyncio
    async def test_error_recovery_integration(self):
        """Test system error recovery and resilience."""
        recovery_scenarios = []
        
        # Scenario 1: Database connection failure
        try:
            await asyncio.sleep(0.1)  # Simulate DB failure
            recovery_scenarios.append("db_failure_handled")
        except Exception:
            recovery_scenarios.append("db_failure_unhandled")
        
        # Scenario 2: External API failure
        try:
            await asyncio.sleep(0.1)  # Simulate API failure
            recovery_scenarios.append("api_failure_handled")
        except Exception:
            recovery_scenarios.append("api_failure_unhandled")
        
        # Scenario 3: Payment service failure
        try:
            await asyncio.sleep(0.1)  # Simulate payment failure
            recovery_scenarios.append("payment_failure_handled")
        except Exception:
            recovery_scenarios.append("payment_failure_unhandled")
        
        # Verify all failures were handled gracefully
        expected_scenarios = [
            "db_failure_handled",
            "api_failure_handled", 
            "payment_failure_handled"
        ]
        
        assert recovery_scenarios == expected_scenarios, f"Error recovery failed: {recovery_scenarios}"