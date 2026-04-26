import unittest
import uuid
from pathlib import Path

from sim.actions.movement import MovementAction
from sim.actions.schemas import ActionContext, MoveActionRequest
from sim.core.database import Database

TESTS_DIR = Path(__file__).resolve().parent


class TestMovementAction(unittest.TestCase):
	def setUp(self) -> None:
		self.db_path = TESTS_DIR / f"movement_test_{uuid.uuid4().hex}.db"
		self.database = Database(str(self.db_path))
		self.database.initialize()

		self.room_a = self.database.create_room(10, "Room A", room_id="room_a")
		self.room_b = self.database.create_room(12, "Room B", room_id="room_b")
		self.character_id = self.database.create_character(
			name="Alice",
			background="A traveler.",
			personality="Curious.",
			current_room_id=self.room_a,
			character_id="alice",
		)
		self.action = MovementAction(self.database)

	def tearDown(self) -> None:
		self.database.close()
		self.db_path.unlink(missing_ok=True)

	def _context(self) -> ActionContext:
		return ActionContext(
			turn_number=1,
			character=dict(self.database.get_character(self.character_id)),
			current_room=dict(self.database.get_room(self.room_a)),
		)

	def test_move_success_updates_room_and_events(self) -> None:
		result = self.action.execute(
			MoveActionRequest(
				context=self._context(),
				available_rooms=[dict(room) for room in self.database.get_all_rooms()],
				target_room_id=self.room_b,
			)
		)

		self.assertTrue(result.success)
		self.assertEqual(result.state_changes["current_room_id"], self.room_b)
		self.assertEqual(len(result.events_created), 2)
		self.assertEqual(self.database.get_character(self.character_id)["current_room_id"], self.room_b)

	def test_stay_creates_no_events(self) -> None:
		result = self.action.execute(
			MoveActionRequest(
				context=self._context(),
				available_rooms=[dict(room) for room in self.database.get_all_rooms()],
				target_room_id=self.room_a,
			)
		)

		self.assertTrue(result.success)
		self.assertEqual(result.events_created, [])
		self.assertEqual(self.database.get_character(self.character_id)["current_room_id"], self.room_a)

	def test_invalid_room_fails_safely(self) -> None:
		result = self.action.execute(
			MoveActionRequest(
				context=self._context(),
				available_rooms=[dict(room) for room in self.database.get_all_rooms()],
				target_room_id="missing_room",
			)
		)

		self.assertFalse(result.success)
		self.assertEqual(result.events_created, [])
		self.assertEqual(self.database.get_character(self.character_id)["current_room_id"], self.room_a)
