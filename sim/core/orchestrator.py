from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

_DEV = os.environ.get("SIM_DEV_MODE", "0").strip() == "1"


def _dev(msg: str) -> None:
    if _DEV:
        print(f"[DEV][orchestrator] {msg}")

from sim.actions.conversation import ConversationAction
from sim.actions.movement import MovementAction
from sim.actions.room_update import RoomUpdateAction
from sim.actions.schemas import (
	ActionContext,
	ConversationActionRequest,
	MoveActionRequest,
	RoomUpdateActionRequest,
)
from sim.agents.turn_planner_agent import TurnActionPlan, TurnPlannerAgent
from sim.core.database import Database
from sim.services.room_backlog import RoomBacklogService


@dataclass(slots=True)
class OrchestratorResult:
	"""
	Purpose:
		Represent one completed character turn advancement.
	"""

	turn_number: int
	public_log_entries: list[str] = field(default_factory=list)
	blocked_reason: str | None = None


class Orchestrator:
	"""
	Purpose:
		Advance the simulation one character turn at a time while preserving
		world-turn ordering and per-character backlog semantics.
	"""

	def __init__(self, database: Database, llm_client: Any) -> None:
		self.database = database
		self.llm_client = llm_client
		self.movement_action = MovementAction(database)
		self.conversation_action = ConversationAction(database, llm_client)
		self.room_update_action = RoomUpdateAction(database, llm_client)
		self.turn_planner = TurnPlannerAgent(llm_client)
		self.room_backlog = RoomBacklogService(database)
		self.current_turn_number = self.database.get_latest_turn_number()
		self._active_character_ids: list[str] = []
		self._active_character_index = 0

	def reset_runtime(self) -> None:
		"""
		Purpose:
			Reset in-memory orchestrator progress without mutating persistent
			world state.

		Inputs:
			None.

		Outputs:
			None.
		"""
		self.current_turn_number = self.database.get_latest_turn_number()
		self._active_character_ids = []
		self._active_character_index = 0

	def run_character_turn(self) -> OrchestratorResult:
		"""
		Purpose:
			Advance exactly one actor turn.

		Inputs:
			None.

		Outputs:
			An OrchestratorResult summarizing the actor turn.
		"""
		rooms = self.database.get_all_rooms()
		characters = self.database.get_all_characters()

		if not rooms or not characters:
			return OrchestratorResult(
				turn_number=self.current_turn_number,
				public_log_entries=["The simulation cannot advance without rooms and characters."],
			)

		if not self._active_character_ids or self._active_character_index >= len(self._active_character_ids):
			self._start_next_world_turn(characters)

		character_id = self._active_character_ids[self._active_character_index]
		result = self._run_one_actor(
			character_id,
			self._build_available_rooms([dict(row) for row in rooms]),
		)
		self._active_character_index += 1

		if self._active_character_index >= len(self._active_character_ids):
			self._active_character_ids = []
			self._active_character_index = 0

		return result

	def _start_next_world_turn(self, characters: list[Any]) -> None:
		self.current_turn_number = max(self.current_turn_number, self.database.get_latest_turn_number()) + 1
		ordered = sorted(
			(dict(row) for row in characters),
			key=lambda character: (
				str(character.get("name", "")).lower(),
				str(character.get("id", "")),
			),
		)
		self._active_character_ids = [str(character["id"]) for character in ordered]
		self._active_character_index = 0

	def _run_one_actor(
		self,
		character_id: str,
		available_rooms: list[dict[str, Any]],
	) -> OrchestratorResult:
		character_row = self.database.get_character(character_id)
		if character_row is None:
			return OrchestratorResult(
				turn_number=self.current_turn_number,
				public_log_entries=[f"Skipped a missing character entry: {character_id}."],
			)

		character = dict(character_row)
		turn_floor = int(character.get("last_completed_turn", 0) or 0)
		self.room_backlog.begin_actor_turn(turn_floor)
		used_actions: set[str] = set()
		public_entries: list[str] = []

		_dev(f"--- actor turn: {character.get('name')} (id={character_id}) turn={self.current_turn_number} ---")
		while len(used_actions) < 3:
			character_row = self.database.get_character(character_id)
			if character_row is None:
				break

			character = dict(character_row)
			room_id = character.get("current_room_id")
			if not room_id:
				_dev(f"  no room_id for {character.get('name')} — breaking")
				public_entries.append(
					f"{character.get('name', 'A character')} could not act because they are not in a room."
				)
				break

			room_row = self.database.get_room(str(room_id))
			if room_row is None:
				_dev(f"  room '{room_id}' missing — breaking")
				public_entries.append(
					f"{character.get('name', 'A character')} could not act because room '{room_id}' is missing."
				)
				break

			context = self._build_context(character, dict(room_row))
			_dev(f"  calling planner (used_actions={used_actions})")
			plan = self.turn_planner.choose_next_action(context, available_rooms, used_actions)
			_dev(f"  planner returned: action={plan.next_action!r}")
			if plan.next_action == "none":
				_dev("  next_action=none — breaking")
				break

			if plan.next_action in used_actions:
				_dev(f"  repeated action {plan.next_action!r} — breaking")
				public_entries.append(
					f"{character.get('name', 'A character')} ended their turn after repeating an action choice."
				)
				break

			action_result = self._execute_plan(plan, context, available_rooms)
			_dev(f"  action result: success={action_result.success} type={action_result.action_type!r} summary={action_result.summary!r}")
			if action_result.summary:
				public_entries.append(action_result.summary)

			if not action_result.success:
				_dev("  action failed — breaking")
				break

			used_actions.add(action_result.action_type)

		if not public_entries:
			public_entries.append(f"{character.get('name', 'A character')} took no action.")

		self.database.update_character_last_completed_turn(character_id, self.current_turn_number)
		return OrchestratorResult(
			turn_number=self.current_turn_number,
			public_log_entries=public_entries,
		)

	def _build_available_rooms(
		self,
		rooms: list[dict[str, Any]],
	) -> list[dict[str, Any]]:
		available_rooms: list[dict[str, Any]] = []
		for room in rooms:
			room_id = str(room["id"])
			room_copy = dict(room)
			room_copy["occupant_count"] = len(self.database.get_characters_in_room(room_id))
			available_rooms.append(room_copy)
		return available_rooms

	def _build_context(
		self,
		character: dict[str, Any],
		room: dict[str, Any],
	) -> ActionContext:
		room_id = str(room["id"])
		backlog = self.room_backlog.get_room_backlog(room_id)
		return ActionContext(
			turn_number=self.current_turn_number,
			character=character,
			current_room=room,
			characters_in_current_room=[
				dict(row) for row in self.database.get_characters_in_room(room_id)
			],
			room_event_backlog=backlog,
		)

	def _execute_plan(
		self,
		plan: TurnActionPlan,
		context: ActionContext,
		available_rooms: list[dict[str, Any]],
	):
		if plan.next_action == "move":
			return self.movement_action.execute(
				MoveActionRequest(
					context=context,
					available_rooms=available_rooms,
					target_room_id=plan.move_target_room_id,
				)
			)

		if plan.next_action == "conversation":
			if plan.conversation_target_character_id is None:
				return self._invalid_result(
					"conversation",
					"Conversation ended because no target character was chosen.",
				)

			return self.conversation_action.execute(
				ConversationActionRequest(
					context=context,
					target_character_id=plan.conversation_target_character_id,
				)
			)

		if plan.next_action == "room_update":
			if plan.room_update_intent is None:
				return self._invalid_result(
					"room_update",
					"Room update ended because no update intent was provided.",
				)

			return self.room_update_action.execute(
				RoomUpdateActionRequest(
					context=context,
					update_intent=plan.room_update_intent,
				)
			)

		return self._invalid_result(
			str(plan.next_action),
			"Turn ended because the planner returned an unsupported action.",
		)

	def _invalid_result(self, action_type: str, summary: str):
		from sim.actions.schemas import ActionResult

		return ActionResult(
			action_type=action_type,
			success=False,
			summary=summary,
			warnings=[summary],
		)
