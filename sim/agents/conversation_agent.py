from __future__ import annotations

from typing import Any

from sim.actions.schemas import ConversationActionRequest, TranscriptMessage


class ConversationAgent:
	"""
	Purpose:
		Own the prompt-building and structured reply generation for one speaker
		turn within a conversation.
	"""

	def __init__(self, llm_client: Any) -> None:
		self.llm_client = llm_client

	def generate_reply(
		self,
		request: ConversationActionRequest,
		speaker: dict[str, Any],
		other: dict[str, Any],
		transcript: list[TranscriptMessage],
		exchange_number: int,
	) -> dict[str, Any]:
		"""
		Purpose:
			Generate one structured conversation reply.

		Inputs:
			request: The conversation action request.
			speaker: The current speaker.
			other: The other participant.
			transcript: Shared conversation transcript so far.
			exchange_number: 1-based transcript position for this reply.

		Outputs:
			A parsed structured reply dictionary.
		"""
		return self.llm_client.generate_structured_chat(
			system_prompt=self._build_system_prompt(exchange_number, request.max_exchanges),
			messages=[
				{
					"role": "user",
					"content": self._build_conversation_prompt(
						request=request,
						speaker=speaker,
						other=other,
						transcript=transcript,
					),
				}
			],
			response_schema={
				"type": "object",
				"properties": {
					"utterance": {"type": "string"},
					"should_end": {"type": "boolean"},
					"end_reason": {"type": ["string", "null"]},
				},
				"required": ["utterance", "should_end", "end_reason"],
			},
		)

	def _build_system_prompt(self, exchange_number: int, max_exchanges: int) -> str:
		if exchange_number >= max_exchanges:
			closing_instruction = "This is the final exchange — you MUST end the conversation now. Set should_end to true."
		elif exchange_number >= max_exchanges - 2:
			closing_instruction = "The conversation is winding down. Start wrapping up and set should_end to true if it feels natural to stop."
		else:
			closing_instruction = "Respond naturally and stay in character."

		return (
			"You are taking one turn in a character-to-character conversation inside a "
			"simulation. Return JSON only. Keep the conversation grounded in what the "
			"speaker can observe. "
			f"{closing_instruction}"
		)

	def _build_conversation_prompt(
		self,
		request: ConversationActionRequest,
		speaker: dict[str, Any],
		other: dict[str, Any],
		transcript: list[TranscriptMessage],
	) -> str:
		lines = [
			f"Current room: {request.context.current_room.get('description', 'A room.')}",
			f"Your name: {speaker.get('name', 'Unknown')}",
			(
				"Your internal details: "
				f"background={speaker.get('background', '')}; "
				f"personality={speaker.get('personality', '')}"
			),
			f"Other character visible details: {self._visible_character_details(other)}",
			"Conversation transcript so far:",
		]

		if transcript:
			lines.extend(
				f"- {entry.speaker_name}: {entry.message}"
				for entry in transcript
			)
		else:
			lines.append("- No dialogue yet. Open the conversation naturally.")

		if request.context.room_event_backlog:
			lines.append("Recent room events:")
			lines.extend(f"- {event}" for event in request.context.room_event_backlog)

		lines.append(
			"Return JSON with keys utterance, should_end, and end_reason."
		)
		return "\n".join(lines)

	def _visible_character_details(self, character: dict[str, Any]) -> str:
		visible_keys = ["physical_details", "appearance", "description"]
		details = [str(character.get(key)).strip() for key in visible_keys if character.get(key)]
		if details:
			return f"{character.get('name', 'Unknown')} - {'; '.join(details)}"
		return character.get("name", "Unknown")
