from __future__ import annotations

from typing import Any

from sim.agents.conversation_agent import ConversationAgent
from sim.actions.schemas import (
	ActionResult,
	ConversationActionRequest,
	TranscriptMessage,
)
from sim.core.database import Database
from sim.services.llm_client import OllamaClientError


class ConversationAction:
	"""
	Purpose:
		Run a bounded back-and-forth conversation between two room occupants.
	"""

	def __init__(self, database: Database, llm_client: Any) -> None:
		self.database = database
		self.agent = ConversationAgent(llm_client)

	def execute(self, request: ConversationActionRequest) -> ActionResult:
		"""
		Purpose:
			Run one full conversation action with transcript persistence.

		Inputs:
			request: The conversation action request.

		Outputs:
			An ActionResult describing the conversation outcome.
		"""
		initiator = request.context.character
		initiator_id = initiator.get("id")
		room = request.context.current_room
		room_id = room.get("id")

		if not initiator_id or not room_id:
			return ActionResult(
				action_type="conversation",
				success=False,
				summary="Conversation skipped because the actor context is incomplete.",
				warnings=["Missing character or room identifier."],
			)

		recipient_row = self.database.get_character(request.target_character_id)
		if recipient_row is None:
			return ActionResult(
				action_type="conversation",
				success=False,
				summary="Conversation skipped because the target character was not found.",
				warnings=[f"Character '{request.target_character_id}' was not found."],
			)

		recipient = dict(recipient_row)
		if recipient["id"] == initiator_id:
			return ActionResult(
				action_type="conversation",
				success=False,
				summary="Conversation skipped because a character cannot target themselves.",
				warnings=["Self-targeted conversation request."],
			)

		if recipient.get("current_room_id") != room_id:
			return ActionResult(
				action_type="conversation",
				success=False,
				summary="Conversation skipped because the target is no longer in the room.",
				warnings=[f"Character '{recipient['id']}' is not in room '{room_id}'."],
			)

		conversation_id = self.database.create_conversation(
			turn_number=request.context.turn_number,
			room_id=room_id,
			initiator_id=initiator_id,
			recipient_id=recipient["id"],
		)
		start_event = self.database.create_event(
			turn_number=request.context.turn_number,
			character_id=initiator_id,
			room_id=room_id,
			log=(
				f"{initiator.get('name', 'The character')} started a conversation "
				f"with {recipient.get('name', 'another character')} in {room_id}."
			),
		)

		transcript: list[TranscriptMessage] = []
		speakers = [initiator, recipient]
		ended_by = "max_turns"

		for exchange_number in range(1, request.max_exchanges + 1):
			speaker = speakers[(exchange_number - 1) % 2]
			other = speakers[exchange_number % 2]

			try:
				reply = self.agent.generate_reply(
					request=request,
					speaker=speaker,
					other=other,
					transcript=transcript,
					exchange_number=exchange_number,
				)
			except OllamaClientError as exc:
				self.database.complete_conversation(
					conversation_id=conversation_id,
					exchange_count=len(transcript),
					summary="Conversation ended early because the model response failed.",
					status="failed",
				)
				return ActionResult(
					action_type="conversation",
					success=False,
					summary="Conversation ended early because the model response failed.",
					events_created=[start_event],
					warnings=[str(exc)],
				)

			utterance = str(reply.get("utterance", "")).strip()
			should_end = bool(reply.get("should_end", False))
			end_reason = reply.get("end_reason")

			if not utterance:
				self.database.complete_conversation(
					conversation_id=conversation_id,
					exchange_count=len(transcript),
					summary="Conversation ended early because the model response was empty.",
					status="failed",
				)
				return ActionResult(
					action_type="conversation",
					success=False,
					summary="Conversation ended early because the model response was empty.",
					events_created=[start_event],
					warnings=["Conversation model returned an empty utterance."],
				)

			transcript_message = TranscriptMessage(
				speaker_id=speaker["id"],
				speaker_name=speaker.get("name", "Unknown"),
				message=utterance,
				should_end=should_end,
				end_reason=end_reason,
			)
			transcript.append(transcript_message)
			self.database.append_conversation_message(
				conversation_id=conversation_id,
				speaker_id=speaker["id"],
				exchange_number=exchange_number,
				message=utterance,
				should_end=should_end,
				end_reason=end_reason,
			)

			if should_end:
				ended_by = str(end_reason or "natural_close")
				break

		summary = self._build_summary(initiator, recipient, room_id, transcript, ended_by)
		self.database.complete_conversation(
			conversation_id=conversation_id,
			exchange_count=len(transcript),
			summary=summary,
			status="completed",
		)
		summary_event = self.database.create_event(
			turn_number=request.context.turn_number,
			character_id=initiator_id,
			room_id=room_id,
			log=summary,
		)
		self.database.create_memory(
			character_id=initiator_id,
			memory_type="short_term",
			text=self._build_memory_text(initiator, recipient, transcript),
			source_event_id=summary_event,
			created_turn=request.context.turn_number,
		)
		self.database.create_memory(
			character_id=recipient["id"],
			memory_type="short_term",
			text=self._build_memory_text(recipient, initiator, transcript),
			source_event_id=summary_event,
			created_turn=request.context.turn_number,
		)

		return ActionResult(
			action_type="conversation",
			success=True,
			summary=summary,
			events_created=[start_event, summary_event],
			state_changes={"conversation_id": conversation_id, "exchange_count": len(transcript)},
		)

	def _build_summary(
		self,
		initiator: dict[str, Any],
		recipient: dict[str, Any],
		room_id: str,
		transcript: list[TranscriptMessage],
		ended_by: str,
	) -> str:
		if not transcript:
			return (
				f"{initiator.get('name', 'A character')} tried to talk with "
				f"{recipient.get('name', 'another character')} in {room_id}, "
				"but the conversation never started."
			)

		last_message = transcript[-1].message
		return (
			f"{initiator.get('name', 'A character')} and "
			f"{recipient.get('name', 'another character')} talked in {room_id} "
			f"and ended with {ended_by}. Final note: {last_message}"
		)

	def _build_memory_text(
		self,
		owner: dict[str, Any],
		other: dict[str, Any],
		transcript: list[TranscriptMessage],
	) -> str:
		if not transcript:
			return (
				f"I tried to talk with {other.get('name', 'someone')}, but the "
				"conversation did not get started."
			)

		first_message = transcript[0].message
		return (
			f"I talked with {other.get('name', 'someone')}. It started with: "
			f"{first_message}"
		)
