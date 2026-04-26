from __future__ import annotations

from sim.actions.schemas import ActionResult, MoveActionRequest
from sim.core.database import Database


class MovementAction:
	"""
	Purpose:
		Resolve a previously chosen room movement.
	"""

	def __init__(self, database: Database) -> None:
		self.database = database

	def execute(self, request: MoveActionRequest) -> ActionResult:
		"""
		Purpose:
			Move a character to a target room when the target exists.

		Inputs:
			request: The movement action request.

		Outputs:
			An ActionResult describing what happened.
		"""
		character = request.context.character
		current_room = request.context.current_room
		character_id = character.get("id")
		current_room_id = current_room.get("id")
		target_room_id = request.target_room_id

		if not character_id or not current_room_id:
			return ActionResult(
				action_type="move",
				success=False,
				summary="Movement skipped because the actor context is incomplete.",
				warnings=["Missing character or room identifier."],
			)

		if target_room_id in {None, "", current_room_id}:
			return ActionResult(
				action_type="move",
				success=True,
				summary=f"{character.get('name', 'The character')} stayed in place.",
			)

		if self.database.get_character(character_id) is None:
			return ActionResult(
				action_type="move",
				success=False,
				summary="Movement skipped because the character no longer exists.",
				warnings=[f"Character '{character_id}' was not found."],
			)

		target_room = self.database.get_room(target_room_id)
		if target_room is None:
			return ActionResult(
				action_type="move",
				success=False,
				summary=f"{character.get('name', 'The character')} could not move.",
				warnings=[f"Room '{target_room_id}' was not found."],
			)

		self.database.move_character(character_id, target_room_id)

		source_label = current_room.get("name") or current_room_id
		target_label = target_room["id"]
		leave_event = self.database.create_event(
			turn_number=request.context.turn_number,
			character_id=character_id,
			room_id=current_room_id,
			log=f"{character.get('name', 'The character')} left {source_label} for {target_label}.",
		)
		enter_event = self.database.create_event(
			turn_number=request.context.turn_number,
			character_id=character_id,
			room_id=target_room_id,
			log=f"{character.get('name', 'The character')} entered {target_label} from {source_label}.",
		)

		return ActionResult(
			action_type="move",
			success=True,
			summary=f"{character.get('name', 'The character')} moved to {target_label}.",
			events_created=[leave_event, enter_event],
			state_changes={"current_room_id": target_room_id},
		)
