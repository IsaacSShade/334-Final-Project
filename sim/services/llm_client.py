from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional
from urllib import error, request

_DEV = os.environ.get("SIM_DEV_MODE", "0").strip() == "1"


def _dev(msg: str) -> None:
    if _DEV:
        print(f"[DEV][llm_client] {msg}")


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
	model: str = "gpt-oss:20b-cloud"
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
			model=os.environ.get("OLLAMA_MODEL", "gpt-oss:20b-cloud"),
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
		_dev(f"POST /chat — model={self.model}")
		_dev(f"  system_prompt: {system_prompt[:120]!r}")
		for m in messages:
			_dev(f"  [{m['role']}]: {str(m.get('content', ''))[:200]!r}")
		response = self._request("POST", "/chat", data=payload, timeout=timeout)
		content = response.get("message", {}).get("content")
		_dev(f"  raw content: {str(content)[:300]!r}")

		if not content:
			raise OllamaClientError("Ollama response did not include message content.")

		try:
			return self._parse_structured_content(str(content))
		except json.JSONDecodeError as exc:
			raise OllamaClientError(
				f"Ollama returned non-JSON structured output. Raw content: {content!r}"
			) from exc

	def _parse_structured_content(self, content: str) -> dict[str, Any]:
		"""
		Purpose:
			Parse structured model output while tolerating common wrappers such as
			code fences or short lead-in text.

		Inputs:
			content: The raw model message content.

		Outputs:
			A parsed JSON dictionary.
		"""
		stripped = content.strip()
		if not stripped:
			raise json.JSONDecodeError("Empty content", content, 0)

		candidates = [
			stripped,
			self._strip_markdown_fences(stripped),
		]
		extracted = self._extract_json_object(stripped)
		if extracted is not None:
			candidates.append(extracted)

		last_error: json.JSONDecodeError | None = None
		for candidate in candidates:
			if not candidate:
				continue
			try:
				parsed = json.loads(candidate)
			except json.JSONDecodeError as exc:
				last_error = exc
				continue

			if not isinstance(parsed, dict):
				raise json.JSONDecodeError("Structured response was not a JSON object", candidate, 0)
			return parsed

		if last_error is not None:
			raise last_error
		raise json.JSONDecodeError("Unable to parse structured content", content, 0)

	def _strip_markdown_fences(self, content: str) -> str:
		if content.startswith("```") and content.endswith("```"):
			lines = content.splitlines()
			if len(lines) >= 3:
				return "\n".join(lines[1:-1]).strip()
		return content

	def _extract_json_object(self, content: str) -> str | None:
		start = None
		depth = 0
		for index, char in enumerate(content):
			if char == "{":
				if start is None:
					start = index
				depth += 1
			elif char == "}":
				if start is None:
					continue
				depth -= 1
				if depth == 0:
					return content[start:index + 1]
		return None

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
