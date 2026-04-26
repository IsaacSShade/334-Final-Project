import unittest
import uuid
from pathlib import Path

from sim.core.database import Database
from sim.core.orchestrator import Orchestrator

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
		if not self.responses:
			raise AssertionError("FakeLLMClient ran out of queued responses.")
		return self.responses.pop(0)


class TestOrchestrator(unittest.TestCase):
	def setUp(self) -> None:
		self.db_path = TESTS_DIR / f"orchestrator_test_{uuid.uuid4().hex}.db"
		self.database = Database(str(self.db_path))
		self.database.initialize()
		self.database.create_room(10, "A calm commons.", room_id="commons")
		self.database.create_room(12, "A quiet studio.", room_id="studio")

	def tearDown(self) -> None:
		self.database.close()
		self.db_path.unlink(missing_ok=True)

	def test_world_turn_order_is_alphabetical(self) -> None:
		self.database.create_character(
			name="Blake",
			background="Talks fast.",
			personality="Lively.",
			current_room_id="commons",
			character_id="blake",
		)
		self.database.create_character(
			name="Ava",
			background="Keeps track of details.",
			personality="Calm.",
			current_room_id="commons",
			character_id="ava",
		)

		client = FakeLLMClient(
			[
				{"next_action": "none", "end_turn": True, "move_target_room_id": None, "conversation_target_character_id": None, "room_update_intent": None},
				{"next_action": "none", "end_turn": True, "move_target_room_id": None, "conversation_target_character_id": None, "room_update_intent": None},
			]
		)
		orchestrator = Orchestrator(self.database, client)

		first = orchestrator.run_character_turn()
		second = orchestrator.run_character_turn()

		self.assertEqual(first.turn_number, 1)
		self.assertEqual(second.turn_number, 1)
		self.assertEqual(first.public_log_entries, ["Ava took no action."])
		self.assertEqual(second.public_log_entries, ["Blake took no action."])
		self.assertEqual(self.database.get_character("ava")["last_completed_turn"], 1)
		self.assertEqual(self.database.get_character("blake")["last_completed_turn"], 1)

	def test_actor_can_talk_then_move_then_update_same_turn(self) -> None:
		self.database.create_character(
			name="Ava",
			background="Likes to check in with people.",
			personality="Warm and curious.",
			current_room_id="commons",
			character_id="ava",
		)
		self.database.create_character(
			name="Blake",
			background="Works nearby.",
			personality="Friendly and calm.",
			current_room_id="commons",
			character_id="blake",
		)

		client = FakeLLMClient(
			[
				{"next_action": "conversation", "end_turn": False, "move_target_room_id": None, "conversation_target_character_id": "blake", "room_update_intent": None},
				{"utterance": "Hi Blake, how is the day going?", "should_end": False, "end_reason": None},
				{"utterance": "Pretty well. I should get back to work soon.", "should_end": True, "end_reason": "natural_close"},
				{"next_action": "move", "end_turn": False, "move_target_room_id": "studio", "conversation_target_character_id": None, "room_update_intent": None},
				{"next_action": "room_update", "end_turn": False, "move_target_room_id": None, "conversation_target_character_id": None, "room_update_intent": "Straighten the studio and make it look more focused."},
				{"new_description": "A tidy studio with neatly stacked papers and a cleared central desk.", "change_summary": "Ava straightened the studio.", "change_tags": ["tidy", "focused"]},
				{"next_action": "none", "end_turn": True, "move_target_room_id": None, "conversation_target_character_id": None, "room_update_intent": None},
				{"next_action": "none", "end_turn": True, "move_target_room_id": None, "conversation_target_character_id": None, "room_update_intent": None},
			]
		)
		orchestrator = Orchestrator(self.database, client)

		result = orchestrator.run_character_turn()

		self.assertEqual(result.turn_number, 1)
		self.assertEqual(len(result.public_log_entries), 3)
		self.assertIn("talked in commons", result.public_log_entries[0])
		self.assertIn("moved to studio", result.public_log_entries[1])
		self.assertIn("straightened the studio", result.public_log_entries[2])
		self.assertEqual(self.database.get_character("ava")["current_room_id"], "studio")
		self.assertIn("tidy studio", self.database.get_room("studio")["description"])
		self.assertEqual(self.database.get_character("ava")["last_completed_turn"], 1)

	def test_destination_room_backlog_is_delivered_before_replanning(self) -> None:
		self.database.create_character(
			name="Ava",
			background="Pays attention to the room.",
			personality="Alert.",
			current_room_id="commons",
			character_id="ava",
		)
		self.database.create_character(
			name="Blake",
			background="Worked here earlier.",
			personality="Quiet.",
			current_room_id="studio",
			character_id="blake",
			last_completed_turn=1,
		)
		self.database.create_event(
			turn_number=1,
			character_id="blake",
			room_id="studio",
			log="Blake rearranged the studio chairs.",
		)

		client = FakeLLMClient(
			[
				{"next_action": "move", "end_turn": False, "move_target_room_id": "studio", "conversation_target_character_id": None, "room_update_intent": None},
				{"next_action": "none", "end_turn": True, "move_target_room_id": None, "conversation_target_character_id": None, "room_update_intent": None},
				{"next_action": "none", "end_turn": True, "move_target_room_id": None, "conversation_target_character_id": None, "room_update_intent": None},
			]
		)
		orchestrator = Orchestrator(self.database, client)

		orchestrator.run_character_turn()

		second_planner_prompt = client.calls[1]["messages"][0]["content"]
		self.assertIn("Blake rearranged the studio chairs.", second_planner_prompt)
