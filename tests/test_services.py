import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app.service.database.store import JSONStore
from app.service.database.store import chat_history
from app.usecases.chat_usecase import chat


class ServiceTestCase(unittest.TestCase):
    def test_json_store_preserves_concurrent_appends(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = JSONStore("test_history")
            store.path = Path(temporary_directory) / "history.json"

            with (
                patch("app.service.database.store.os.fsync"),
                ThreadPoolExecutor(max_workers=8) as executor,
            ):
                list(executor.map(lambda value: store.append({"value": value}), range(12)))

            records = store.load()
            self.assertEqual(len(records), 12)
            self.assertEqual({record["value"] for record in records}, set(range(12)))

    def test_chat_uses_email_agent_directly(self):
        with (
            patch(
                "app.usecases.chat_usecase.run_email_agent",
                return_value="Email draft ready",
            ) as mocked_agent,
            patch.object(chat_history, "append") as mocked_append,
        ):
            result = chat("Create a draft", "thread-123")

        self.assertEqual(result["route"], "email")
        self.assertEqual(result["answer"], "Email draft ready")
        mocked_agent.assert_called_once_with("Create a draft", "thread-123")
        mocked_append.assert_called_once_with(result)


if __name__ == "__main__":
    unittest.main()
