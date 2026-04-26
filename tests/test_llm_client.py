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

	@patch.dict(os.environ, {}, clear=True)
	def test_from_env_uses_local_defaults(self) -> None:
		client = OllamaClient.from_env()
		self.assertEqual(client.mode, "local")
		self.assertEqual(client.base_url, "http://localhost:11434")
		self.assertEqual(client.model, "qwen3:30b")
