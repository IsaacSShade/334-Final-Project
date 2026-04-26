from __future__ import annotations

from typing import Any

from sim.actions.schemas import RoomUpdateActionRequest


class RoomUpdateAgent:
	"""
	Purpose:
		Own prompt-building and structured generation for room description updates.
	"""

	def __init__(self, llm_client: Any) -> None:
		self.llm_client = llm_client

	def generate_update(self, request: RoomUpdateActionRequest) -> dict[str, Any]:
		"""
		Purpose:
			Generate one structured room update response.

		Inputs:
			request: The room update action request.

		Outputs:
			A parsed structured update dictionary.
		"""
		return self.llm_client.generate_structured_chat(
			system_prompt=(
				"You are updating the description of the current room in a "
				"simulation. Return JSON only. Only describe changes to the "
				"current room. Keep the room's identity stable and return a "
				"usable replacement description."
			),
			messages=[
				{
					"role": "user",
					"content": self._build_prompt(request),
				}
			],
			response_schema={
				"type": "object",
				"properties": {
					"new_description": {"type": "string"},
					"change_summary": {"type": "string"},
					"change_tags": {
						"type": "array",
						"items": {"type": "string"},
					},
				},
				"required": ["new_description", "change_summary", "change_tags"],
			},
		)

	def _build_prompt(self, request: RoomUpdateActionRequest) -> str:
		room = request.context.current_room
		character = request.context.character
		lines = [
			f"Current room id: {room.get('id')}",
			f"Current room description: {room.get('description', 'A room.')}",
			f"Acting character: {character.get('name', 'Unknown')}",
			f"Update intent: {request.update_intent}",
		]

		if request.context.room_event_backlog:
			lines.append("Recent room events:")
			lines.extend(f"- {event}" for event in request.context.room_event_backlog)

		lines.append(
			"Return JSON with keys new_description, change_summary, and change_tags."
		)
		return "\n".join(lines)
