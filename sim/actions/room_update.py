from __future__ import annotations

from typing import Any

from sim.agents.room_update_agent import RoomUpdateAgent
from sim.actions.schemas import ActionResult, RoomUpdateActionRequest
from sim.core.database import Database
from sim.services.llm_client import OllamaClientError


class RoomUpdateAction:
	"""
	Purpose:
		Update the current room description using a prompt-driven model response.
	"""

	def __init__(self, database: Database, llm_client: Any) -> None:
		self.database = database
		self.agent = RoomUpdateAgent(llm_client)

	def execute(self, request: RoomUpdateActionRequest) -> ActionResult:
		"""
		Purpose:
			Generate and persist one room description update.

		Inputs:
			request: The room update action request.

		Outputs:
			An ActionResult describing the outcome.
		"""
		character = request.context.character
		room = request.context.current_room
		character_id = character.get("id")
		room_id = room.get("id")
		current_description = str(room.get("description", "")).strip()

		if not character_id or not room_id:
			return ActionResult(
				action_type="room_update",
				success=False,
				summary="Room update skipped because the actor context is incomplete.",
				warnings=["Missing character or room identifier."],
			)

		try:
			reply = self.agent.generate_update(request)
		except OllamaClientError as exc:
			return ActionResult(
				action_type="room_update",
				success=False,
				summary="Room update ended early because the model response failed.",
				warnings=[str(exc)],
			)

		new_description = str(reply.get("new_description", "")).strip()
		change_summary = str(reply.get("change_summary", "")).strip()

		if not new_description:
			return ActionResult(
				action_type="room_update",
				success=False,
				summary="Room update produced no usable description.",
				warnings=["Room update model returned an empty description."],
			)

		if new_description == current_description:
			return ActionResult(
				action_type="room_update",
				success=True,
				summary="Room description stayed the same.",
			)

		self.database.update_room_description(room_id, new_description)
		event_id = self.database.create_event(
			turn_number=request.context.turn_number,
			character_id=character_id,
			room_id=room_id,
			log=change_summary or self._default_summary(character, room_id),
			event_type="room_update",
			event_meta={"before": current_description, "after": new_description},
		)

		return ActionResult(
			action_type="room_update",
			success=True,
			summary=change_summary or self._default_summary(character, room_id),
			events_created=[event_id],
			state_changes={"description": new_description},
		)

	def _default_summary(self, character: dict[str, Any], room_id: str) -> str:
		return f"{character.get('name', 'The character')} updated the appearance of {room_id}."
