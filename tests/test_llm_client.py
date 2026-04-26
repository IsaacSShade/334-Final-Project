import os
import unittest
from unittest.mock import patch

from sim.services.llm_client import OllamaClient


class TestOllamaClient(unittest.TestCase):
	def test_normalized_base_url_supports_with_or_without_api_suffix(self) -> None:
		self.assertEqual(
			OllamaClient(base_url="https://ollama.com/api").normalized_base_url(),
			"https://ollama.com/api",
		)
		self.assertEqual(
			OllamaClient(base_url="http://localhost:11434").normalized_base_url(),
			"http://localhost:11434/api",
		)

	def test_cloud_warning_requires_api_key(self) -> None:
		client = OllamaClient(mode="cloud", base_url="https://ollama.com/api", api_key=None)
		self.assertIn("OLLAMA_API_KEY", client.get_startup_warning() or "")

	@patch.dict(os.environ, {"OLLAMA_MODE": "cloud", "OLLAMA_BASE_URL": "https://ollama.com/api", "OLLAMA_MODEL": "qwen3:30b"}, clear=True)
	def test_from_env_uses_cloud_defaults(self) -> None:
		client = OllamaClient.from_env()
		self.assertEqual(client.mode, "cloud")
		self.assertEqual(client.base_url, "https://ollama.com/api")
		self.assertEqual(client.model, "qwen3:30b")
