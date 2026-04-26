from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.actions.schemas import ActionContext


@dataclass(slots=True)
class TurnActionPlan:
	"""
	Purpose:
		Represent one planner decision for the next action within an actor turn.
	"""

	next_action: str
	end_turn: bool
	move_target_room_id: str | None = None
	conversation_target_character_id: str | None = None
	room_update_intent: str | None = None


class TurnPlannerAgent:
	"""
	Purpose:
		Choose one next action at a time for a character using the shared
		context and current unused action set.
	"""

	def __init__(self, llm_client: Any) -> None:
		self.llm_client = llm_client

	def choose_next_action(
		self,
		context: ActionContext,
		available_rooms: list[dict[str, Any]],
		used_actions: set[str],
	) -> TurnActionPlan:
		"""
		Purpose:
			Request one structured next-action decision from the model.

		Inputs:
			context: The actor's current action context.
			available_rooms: Rooms the actor may move between.
			used_actions: Action types already consumed this turn.

		Outputs:
			A validated TurnActionPlan.
		"""
		reply = self.llm_client.generate_structured_chat(
			system_prompt=(
				"You are deciding the next single action for a character in a "
				"turn-based simulation. Return JSON only. Pick at most one unused "
				"action from move, conversation, room_update, or none. If the turn "
				"should stop now, set end_turn to true."
			),
			messages=[
				{
					"role": "user",
					"content": self._build_prompt(context, available_rooms, used_actions),
				}
			],
			response_schema={
				"type": "object",
				"properties": {
					"next_action": {
						"type": "string",
						"enum": ["move", "conversation", "room_update", "none"],
					},
					"end_turn": {"type": "boolean"},
					"move_target_room_id": {"type": ["string", "null"]},
					"conversation_target_character_id": {"type": ["string", "null"]},
					"room_update_intent": {"type": ["string", "null"]},
				},
				"required": [
					"next_action",
					"end_turn",
					"move_target_room_id",
					"conversation_target_character_id",
					"room_update_intent",
				],
			},
		)

		return TurnActionPlan(
			next_action=str(reply.get("next_action", "none")).strip() or "none",
			end_turn=bool(reply.get("end_turn", False)),
			move_target_room_id=self._normalize_optional_text(reply.get("move_target_room_id")),
			conversation_target_character_id=self._normalize_optional_text(
				reply.get("conversation_target_character_id")
			),
			room_update_intent=self._normalize_optional_text(reply.get("room_update_intent")),
		)

	def _build_prompt(
		self,
		context: ActionContext,
		available_rooms: list[dict[str, Any]],
		used_actions: set[str],
	) -> str:
		character = context.character
		current_room = context.current_room
		lines = [
			f"Turn number: {context.turn_number}",
			f"Your name: {character.get('name', 'Unknown')}",
			(
				"Your internal details: "
				f"background={character.get('background', '')}; "
				f"personality={character.get('personality', '')}"
			),
			f"Current room id: {current_room.get('id')}",
			f"Current room description: {current_room.get('description', 'A room.')}",
			f"Actions already used this turn: {', '.join(sorted(used_actions)) or 'none'}",
			"Characters in the current room:",
		]

		if context.characters_in_current_room:
			for occupant in context.characters_in_current_room:
				lines.append(f"- {occupant.get('id')}: {occupant.get('name', 'Unknown')}")
		else:
			lines.append("- Nobody is here.")

		lines.append("Available rooms:")
		for room in available_rooms:
			lines.append(
				f"- {room.get('id')}: {room.get('description', 'A room.')}"
			)

		if context.room_event_backlog:
			lines.append("Recent room events since your last turn:")
			lines.extend(f"- {entry}" for entry in context.room_event_backlog)

		lines.append(
			"Choose the single best next action. If there is nothing useful to do, "
			"choose none and end the turn."
		)
		return "\n".join(lines)

	def _normalize_optional_text(self, value: Any) -> str | None:
		if value is None:
			return None
		text = str(value).strip()
		if not text:
			return None
		return text
