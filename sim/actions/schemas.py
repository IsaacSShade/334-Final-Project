from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class ActionContext:
	"""
	Purpose:
		Capture the shared read-only context passed into one action.
	"""

	turn_number: int
	character: dict[str, Any]
	current_room: dict[str, Any]
	characters_in_current_room: list[dict[str, Any]] = field(default_factory=list)
	room_event_backlog: list[str] = field(default_factory=list)
	character_memories: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MoveActionRequest:
	"""
	Purpose:
		Represent one movement action request.
	"""

	context: ActionContext
	available_rooms: list[dict[str, Any]]
	target_room_id: Optional[str]


@dataclass(slots=True)
class ConversationActionRequest:
	"""
	Purpose:
		Represent one conversation action request.
	"""

	context: ActionContext
	target_character_id: str
	max_exchanges: int = 8


@dataclass(slots=True)
class RoomUpdateActionRequest:
	"""
	Purpose:
		Represent one room description update request.
	"""

	context: ActionContext
	update_intent: str


@dataclass(slots=True)
class TranscriptMessage:
	"""
	Purpose:
		Represent one line in a conversation transcript.
	"""

	speaker_id: str
	speaker_name: str
	message: str
	should_end: bool = False
	end_reason: Optional[str] = None


@dataclass(slots=True)
class ActionResult:
	"""
	Purpose:
		Represent the result of one resolved action.
	"""

	action_type: str
	success: bool
	summary: str
	events_created: list[int] = field(default_factory=list)
	state_changes: dict[str, Any] = field(default_factory=dict)
	warnings: list[str] = field(default_factory=list)
