from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional
from urllib import error, request


class OllamaClientError(RuntimeError):
	"""
	Purpose:
		Represent Ollama configuration, availability, or response errors.
	"""


@dataclass(slots=True)
class OllamaClient:
	"""
	Purpose:
	Provide a small Ollama API client that supports both cloud and local
	configurations with the same interface.
	"""

	mode: str = "local"
	base_url: str = "http://localhost:11434"
	model: str = "qwen3:30b"
	api_key: Optional[str] = None

	@classmethod
	def from_env(cls) -> "OllamaClient":
		"""
		Purpose:
			Build a client from environment variables.

		Inputs:
			None.

		Outputs:
			A configured OllamaClient instance.
		"""
		return cls(
			mode=os.environ.get("OLLAMA_MODE", "local"),
			base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
			model=os.environ.get("OLLAMA_MODEL", "qwen3:30b"),
			api_key=os.environ.get("OLLAMA_API_KEY"),
		)

	def normalized_base_url(self) -> str:
		"""
		Purpose:
			Normalize the configured base URL so request paths can be appended
			consistently.

		Inputs:
			None.

		Outputs:
			A base URL ending in `/api`.
		"""
		base_url = self.base_url.rstrip("/")
		if base_url.endswith("/api"):
			return base_url
		return f"{base_url}/api"

	def is_local_mode(self) -> bool:
		"""
		Purpose:
			Indicate whether the client is configured for a local Ollama host.

		Inputs:
			None.

		Outputs:
			True when running in local mode, otherwise False.
		"""
		return self.mode.lower() == "local"

	def get_startup_warning(self, timeout: float = 2.0) -> Optional[str]:
		"""
		Purpose:
			Return a user-facing warning string if the current configuration is
			not ready for model-backed actions.

		Inputs:
			timeout: Maximum request time in seconds for local availability checks.

		Outputs:
			A warning string or None when configuration looks usable.
		"""
		if self.is_local_mode():
			if self.is_available(timeout=timeout):
				return None
			return (
				"Ollama is not running at "
				f"{self.normalized_base_url()}. Start Ollama or switch to cloud "
				"mode before launching model-backed actions."
			)

		if not self.api_key:
			return (
				"OLLAMA_API_KEY is not set for Ollama Cloud. Add an API key or "
				"switch to local mode before launching model-backed actions."
			)

		return None

	def is_available(self, timeout: float = 2.0) -> bool:
		"""
		Purpose:
			Check whether the configured Ollama host is reachable.

		Inputs:
			timeout: Maximum request time in seconds.

		Outputs:
			True if the host responded successfully, otherwise False.
		"""
		try:
			self._request("GET", "/version", timeout=timeout)
		except OllamaClientError:
			return False
		return True

	def generate_structured_chat(
		self,
		system_prompt: str,
		messages: list[dict[str, str]],
		response_schema: dict[str, Any],
		timeout: float = 30.0,
	) -> dict[str, Any]:
		"""
		Purpose:
			Request one non-streaming structured chat completion from Ollama.

		Inputs:
			system_prompt: High-level instruction for the model.
			messages: Chat messages to send.
			response_schema: JSON schema for the expected response.
			timeout: Maximum request time in seconds.

		Outputs:
			A parsed JSON dictionary representing the model response.
		"""
		payload = {
			"model": self.model,
			"stream": False,
			"format": response_schema,
			"messages": [{"role": "system", "content": system_prompt}, *messages],
			"options": {"temperature": 0},
		}
		response = self._request("POST", "/chat", data=payload, timeout=timeout)
		content = response.get("message", {}).get("content")

		if not content:
			raise OllamaClientError("Ollama response did not include message content.")

		try:
			return json.loads(content)
		except json.JSONDecodeError as exc:
			raise OllamaClientError("Ollama returned non-JSON structured output.") from exc

	def _request(
		self,
		method: str,
		path: str,
		data: Optional[dict[str, Any]] = None,
		timeout: float = 30.0,
	) -> dict[str, Any]:
		"""
		Purpose:
			Perform one HTTP request against the configured Ollama host.

		Inputs:
			method: HTTP method.
			path: API path beginning with `/`.
			data: Optional JSON payload.
			timeout: Maximum request time in seconds.

		Outputs:
			The parsed JSON response body.
		"""
		url = f"{self.normalized_base_url()}{path}"
		headers = {"Content-Type": "application/json"}

		if not self.is_local_mode() and self.api_key:
			headers["Authorization"] = f"Bearer {self.api_key}"

		body = None
		if data is not None:
			body = json.dumps(data).encode("utf-8")

		http_request = request.Request(
			url=url,
			data=body,
			headers=headers,
			method=method,
		)

		try:
			with request.urlopen(http_request, timeout=timeout) as response:
				return json.loads(response.read().decode("utf-8"))
		except error.HTTPError as exc:
			message = exc.read().decode("utf-8", errors="replace")
			raise OllamaClientError(
				f"Ollama request failed with status {exc.code}: {message}"
			) from exc
		except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
			raise OllamaClientError(f"Ollama request failed: {exc}") from exc
