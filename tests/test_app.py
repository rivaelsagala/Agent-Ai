import unittest
from unittest.mock import patch

from app import create_app


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_agent_status_endpoint(self):
        response = self.client.get("/api/agent/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        expected_status = "ready" if data["llm_configured"] else "no-llm-key"
        self.assertEqual(data["status"], expected_status)

    def test_chat_endpoint(self):
        with patch(
            "app.routes.handle_chat",
            return_value={"answer": "Hello!", "route": "email"},
        ) as mocked_chat:
            response = self.client.post(
                "/api/agent/chat",
                json={"message": "hello", "thread_id": "test-thread"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["reply"], "Hello!")
        self.assertEqual(data["route"], "email")
        self.assertEqual(data["thread_id"], "test-thread")
        mocked_chat.assert_called_once_with("hello", "test-thread")

    def test_chat_endpoint_requires_message(self):
        response = self.client.post("/api/agent/chat", json={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_expected_api_routes_are_registered(self):
        api_routes = {
            rule.rule
            for rule in self.app.url_map.iter_rules()
            if rule.rule.startswith("/api/")
        }
        self.assertEqual(
            api_routes,
            {
                "/api/agent/chat",
                "/api/agent/status",
                "/api/market/status",
                "/api/monitor/run",
                "/api/notifications/test",
                "/api/subscribers",
            },
        )

    def test_admin_endpoint_requires_key(self):
        with patch("app.admin_routes.settings.ADMIN_API_KEY", "secret"):
            response = self.client.get("/api/market/status")
        self.assertEqual(response.status_code, 401)

    def test_subscriber_validation_does_not_access_database(self):
        with patch("app.admin_routes.settings.ADMIN_API_KEY", "secret"):
            response = self.client.post(
                "/api/subscribers",
                headers={"X-Admin-Key": "secret"},
                json={
                    "display_name": "Investor",
                    "channel_type": "telegram",
                    "destination": "12345",
                    "tickers": [],
                },
            )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
