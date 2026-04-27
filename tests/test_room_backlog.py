import unittest
import uuid
from pathlib import Path

from sim.core.database import Database
from sim.services.room_backlog import RoomBacklogService

TESTS_DIR = Path(__file__).resolve().parent


class TestRoomBacklogService(unittest.TestCase):
	def setUp(self) -> None:
		self.db_path = TESTS_DIR / f"room_backlog_test_{uuid.uuid4().hex}.db"
		self.database = Database(str(self.db_path))
		self.database.initialize()
		self.room_id = self.database.create_room(10, "A shared room.", room_id="shared")
		self.character_id = self.database.create_character(
			name="Alice",
			background="Observes everything.",
			personality="Alert.",
			current_room_id=self.room_id,
			character_id="alice",
		)
		self.service = RoomBacklogService(self.database)

	def tearDown(self) -> None:
		self.database.close()
		self.db_path.unlink(missing_ok=True)

	def test_backlog_only_includes_events_newer_than_turn_floor(self) -> None:
		self.database.create_event(1, self.character_id, "Turn one event.", room_id=self.room_id)
		self.database.create_event(2, self.character_id, "Turn two event.", room_id=self.room_id)

		self.service.begin_actor_turn(turn_floor=1)
		backlog = self.service.get_room_backlog(self.room_id)

		self.assertEqual(backlog, ["Turn two event."])

	def test_backlog_delivery_is_idempotent_within_active_turn(self) -> None:
		self.database.create_event(2, self.character_id, "A fresh event.", room_id=self.room_id)

		self.service.begin_actor_turn(turn_floor=1)
		first = self.service.get_room_backlog(self.room_id)
		second = self.service.get_room_backlog(self.room_id)

		self.assertEqual(first, ["A fresh event."])
		self.assertEqual(second, [])
