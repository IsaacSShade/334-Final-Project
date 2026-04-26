import unittest
import uuid
from pathlib import Path

from sim.actions.room_update import RoomUpdateAction
from sim.actions.schemas import ActionContext, RoomUpdateActionRequest
from sim.core.database import Database

TESTS_DIR = Path(__file__).resolve().parent


class FakeLLMClient:
	def __init__(self, response):
		self.response = response

	def generate_structured_chat(self, system_prompt, messages, response_schema, timeout=30.0):
		return self.response


class TestRoomUpdateAction(unittest.TestCase):
	def setUp(self) -> None:
		self.db_path = TESTS_DIR / f"room_update_test_{uuid.uuid4().hex}.db"
		self.database = Database(str(self.db_path))
		self.database.initialize()

		self.room_id = self.database.create_room(15, "A room full of unopened boxes.", room_id="living_room")
		self.character_id = self.database.create_character(
			name="Alice",
			background="Just moved in.",
			personality="Busy and hopeful.",
			current_room_id=self.room_id,
			character_id="alice",
		)

	def tearDown(self) -> None:
		self.database.close()
		self.db_path.unlink(missing_ok=True)

	def test_room_update_changes_description_and_logs_event(self) -> None:
		action = RoomUpdateAction(
			self.database,
			FakeLLMClient(
				{
					"new_description": (
						"A mostly settled living room with books on the shelves and only "
						"two boxes left near the sofa."
					),
					"change_summary": "Alice unpacked most of the living room.",
					"change_tags": ["unpacked", "settled"],
				}
			),
		)
		context = ActionContext(
			turn_number=4,
			character=dict(self.database.get_character(self.character_id)),
			current_room=dict(self.database.get_room(self.room_id)),
		)

		result = action.execute(
			RoomUpdateActionRequest(
				context=context,
				update_intent="Unpack the living room so it looks more settled.",
			)
		)

		self.assertTrue(result.success)
		self.assertEqual(len(result.events_created), 1)
		self.assertIn("mostly settled", self.database.get_room(self.room_id)["description"])

	def test_empty_description_becomes_no_op_failure(self) -> None:
		action = RoomUpdateAction(
			self.database,
			FakeLLMClient(
				{
					"new_description": "   ",
					"change_summary": "No usable change.",
					"change_tags": [],
				}
			),
		)
		context = ActionContext(
			turn_number=1,
			character=dict(self.database.get_character(self.character_id)),
			current_room=dict(self.database.get_room(self.room_id)),
		)

		result = action.execute(
			RoomUpdateActionRequest(
				context=context,
				update_intent="Do something vague.",
			)
		)

		self.assertFalse(result.success)
		self.assertEqual(result.events_created, [])
		self.assertEqual(
			self.database.get_room(self.room_id)["description"],
			"A room full of unopened boxes.",
		)
