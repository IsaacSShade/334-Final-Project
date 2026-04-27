from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from sim.actions.schemas import ActionContext

_DEV = os.environ.get("SIM_DEV_MODE", "0").strip() == "1"


def _dev(msg: str) -> None:
    if _DEV:
        print(f"[DEV][turn_planner] {msg}")


@dataclass(slots=True)
class TurnActionPlan:
	"""
	Purpose:
		Represent one planner decision for the next action within an actor turn.
	"""

	next_action: str
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
				"turn-based simulation. Pick one action from: "
				"move, conversation, room_update, or none. "
				"none means the character waits and observes while others act. "
				"Personality should strongly influence the choice. Curious, restless, "
				"or social characters should move or interact rather than waiting. "
				"Only choose none when waiting genuinely fits the personality. "
				"You MUST respond with ONLY a JSON object using exactly these four "
				"fields — do not rename them, do not add extra fields:\n"
				"  next_action: one of \"move\", \"conversation\", \"room_update\", \"none\"\n"
				"  move_target_room_id: the room id string to move to, or null\n"
				"  conversation_target_character_id: the character id string to talk to, or null\n"
				"  room_update_intent: a short string describing the room change, or null\n"
				"Example for a move: "
				"{\"next_action\":\"move\",\"move_target_room_id\":\"kitchen\","
				"\"conversation_target_character_id\":null,\"room_update_intent\":null}\n"
				"Example for waiting: "
				"{\"next_action\":\"none\",\"move_target_room_id\":null,"
				"\"conversation_target_character_id\":null,\"room_update_intent\":null}"
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
					"move_target_room_id": {"type": ["string", "null"]},
					"conversation_target_character_id": {"type": ["string", "null"]},
					"room_update_intent": {"type": ["string", "null"]},
				},
				"required": [
					"next_action",
					"move_target_room_id",
					"conversation_target_character_id",
					"room_update_intent",
				],
			},
		)

		plan = TurnActionPlan(
			next_action=str(reply.get("next_action", "none")).strip() or "none",
			move_target_room_id=self._normalize_optional_text(reply.get("move_target_room_id")),
			conversation_target_character_id=self._normalize_optional_text(
				reply.get("conversation_target_character_id")
			),
			room_update_intent=self._normalize_optional_text(reply.get("room_update_intent")),
		)
		_dev(
			f"plan => action={plan.next_action!r} "
			f"move_target={plan.move_target_room_id!r} "
			f"convo_target={plan.conversation_target_character_id!r} "
			f"room_intent={plan.room_update_intent!r}"
		)
		return plan

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
			"Other characters in the current room:",
		]
		other_occupants = [
			occupant
			for occupant in context.characters_in_current_room
			if str(occupant.get("id")) != str(character.get("id"))
		]

		if other_occupants:
			for occupant in other_occupants:
				lines.append(f"- {occupant.get('id')}: {occupant.get('name', 'Unknown')}")
		else:
			lines.append("- Nobody else is here.")

		lines.append("Available rooms:")
		for room in available_rooms:
			room_id = str(room.get("id"))
			occupant_count = self._room_occupant_count(available_rooms, context, room_id)
			lines.append(
				f"- {room_id}: {room.get('description', 'A room.')} "
				f"(occupants here now: {occupant_count})"
			)

		if context.character_memories:
			lines.append("Your memories (most recent first):")
			lines.extend(f"- {mem}" for mem in context.character_memories)

		if context.room_event_backlog:
			lines.append("Recent room events since your last turn:")
			lines.extend(f"- {entry}" for entry in context.room_event_backlog)

		lines.append(
			"Choose the single best next action now. The character may act multiple "
			"times per turn — choose none only when waiting genuinely fits them.\n"
			"Respond with JSON using exactly these fields: next_action, "
			"move_target_room_id, conversation_target_character_id, room_update_intent."
		)
		return "\n".join(lines)

	def _normalize_optional_text(self, value: Any) -> str | None:
		if value is None:
			return None
		text = str(value).strip()
		if not text:
			return None
		return text

	def _room_occupant_count(
		self,
		available_rooms: list[dict[str, Any]],
		context: ActionContext,
		room_id: str,
	) -> int:
		count = 0
		if room_id == str(context.current_room.get("id")):
			return len(
				[
					occupant
					for occupant in context.characters_in_current_room
					if str(occupant.get("id")) != str(context.character.get("id"))
				]
			)

		for room in available_rooms:
			if str(room.get("id")) == room_id:
				raw_count = room.get("occupant_count")
				if isinstance(raw_count, int):
					return raw_count
		return count
