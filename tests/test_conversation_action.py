import unittest
import uuid
from pathlib import Path

from sim.actions.conversation import ConversationAction
from sim.actions.schemas import ActionContext, ConversationActionRequest
from sim.core.database import Database

TESTS_DIR = Path(__file__).resolve().parent


class FakeLLMClient:
	def __init__(self, responses):
		self.responses = list(responses)
		self.calls = []

	def generate_structured_chat(self, system_prompt, messages, response_schema, timeout=30.0):
		self.calls.append(
			{
				"system_prompt": system_prompt,
				"messages": messages,
				"response_schema": response_schema,
			}
		)
		return self.responses.pop(0)


class TestConversationAction(unittest.TestCase):
	def setUp(self) -> None:
		self.db_path = TESTS_DIR / f"conversation_test_{uuid.uuid4().hex}.db"
		self.database = Database(str(self.db_path))
		self.database.initialize()

		self.room_id = self.database.create_room(10, "A bright kitchen.", room_id="kitchen")
		self.alice_id = self.database.create_character(
			name="Alice",
			background="Just moved in.",
			personality="Warm and curious.",
			current_room_id=self.room_id,
			character_id="alice",
		)
		self.bob_id = self.database.create_character(
			name="Bob",
			background="A neighbor.",
			personality="Friendly and calm.",
			current_room_id=self.room_id,
			character_id="bob",
		)

	def tearDown(self) -> None:
		self.database.close()
		self.db_path.unlink(missing_ok=True)

	def test_conversation_persists_transcript_and_memories(self) -> None:
		client = FakeLLMClient(
			[
				{
					"utterance": "Hi Bob, how are you settling in next door?",
					"should_end": False,
					"end_reason": None,
				},
				{
					"utterance": "Pretty well, thanks. I should get back to unpacking soon.",
					"should_end": True,
					"end_reason": "natural_close",
				},
			]
		)
		action = ConversationAction(self.database, client)
		context = ActionContext(
			turn_number=3,
			character=dict(self.database.get_character(self.alice_id)),
			current_room=dict(self.database.get_room(self.room_id)),
			characters_in_current_room=[
				dict(character)
				for character in self.database.get_characters_in_room(self.room_id)
			],
			room_event_backlog=["Bob decorated the kitchen earlier."],
		)

		result = action.execute(
			ConversationActionRequest(
				context=context,
				target_character_id=self.bob_id,
				max_exchanges=6,
			)
		)

		self.assertTrue(result.success)
		self.assertEqual(len(result.events_created), 2)
		conversation = self.database.get_conversation(result.state_changes["conversation_id"])
		messages = self.database.get_conversation_messages(result.state_changes["conversation_id"])
		alice_memories = self.database.get_character_memories(self.alice_id)
		bob_memories = self.database.get_character_memories(self.bob_id)

		self.assertIsNotNone(conversation)
		self.assertEqual(conversation["exchange_count"], 2)
		self.assertEqual(len(messages), 2)
		self.assertEqual(messages[0]["speaker_id"], self.alice_id)
		self.assertEqual(messages[1]["speaker_id"], self.bob_id)
		self.assertEqual(len(alice_memories), 1)
		self.assertEqual(len(bob_memories), 1)
		self.assertIn("No dialogue yet", client.calls[0]["messages"][0]["content"])
		self.assertIn("Hi Bob", client.calls[1]["messages"][0]["content"])

	def test_conversation_fails_if_target_not_in_room(self) -> None:
		self.database.move_character(self.bob_id, None)
		client = FakeLLMClient([])
		action = ConversationAction(self.database, client)
		context = ActionContext(
			turn_number=1,
			character=dict(self.database.get_character(self.alice_id)),
			current_room=dict(self.database.get_room(self.room_id)),
		)

		result = action.execute(
			ConversationActionRequest(
				context=context,
				target_character_id=self.bob_id,
			)
		)

		self.assertFalse(result.success)
		self.assertEqual(result.events_created, [])
