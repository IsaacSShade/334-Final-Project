import unittest
import uuid
from pathlib import Path

from sim.core.database import Database

TESTS_DIR = Path(__file__).resolve().parent


class TestDatabase(unittest.TestCase):
	"""
	Purpose:
		Test basic database schema creation and inserts.

	Inputs:
		None.

	Outputs:
		Unit test results.
	"""

	def test_can_create_schema_and_insert_rows(self) -> None:
		"""
		Purpose:
			Verify rooms, characters, events, and memories can be inserted and read.

		Inputs:
			None.

		Outputs:
			None.
		"""
		db_path = TESTS_DIR / f"test_sim_{uuid.uuid4().hex}.db"
		database = Database(str(db_path))

		try:
			database.initialize()

			room_id = database.create_room(
				size=10,
				description="A plain test room."
			)

			character_id = database.create_character(
				name="Alice",
				background="A careful observer.",
				personality="Calm and analytical.",
				current_room_id=room_id,
			)

			event_id = database.create_event(
				turn_number=1,
				character_id=character_id,
				room_id=room_id,
				log="Alice entered the room and looked around."
			)

			database.create_memory(
				character_id=character_id,
				memory_type="short_term",
				text="I entered a plain room and looked around.",
				source_event_id=event_id,
				created_turn=1,
			)

			memories = database.get_character_memories(character_id)
			events = database.get_recent_events()

			self.assertEqual(len(memories), 1)
			self.assertEqual(len(events), 1)
			self.assertEqual(memories[0]["memory_type"], "short_term")
			self.assertEqual(events[0]["turn_number"], 1)
		finally:
			database.close()
			db_path.unlink(missing_ok=True)

	def test_upsert_and_get_all(self) -> None:
		"""
		Purpose:
			Verify that upserting rooms and characters works, and that they can be retrieved.
		"""
		db_path = TESTS_DIR / f"test_sim_upsert_{uuid.uuid4().hex}.db"
		database = Database(str(db_path))

		try:
			database.initialize()

			# Insert new room and character via upsert
			database.upsert_room("room_1", 20, "A large testing room")
			database.upsert_character("char_1", "Bob", "Builder", "Happy", "room_1")

			rooms = database.get_all_rooms()
			characters = database.get_all_characters()

			self.assertEqual(len(rooms), 1)
			self.assertEqual(rooms[0]["id"], "room_1")
			self.assertEqual(len(characters), 1)
			self.assertEqual(characters[0]["id"], "char_1")

			# Upsert existing to check if it updates instead of duplicating
			database.upsert_room("room_1", 30, "An expanded testing room")
			rooms_updated = database.get_all_rooms()
			
			self.assertEqual(len(rooms_updated), 1)
			self.assertEqual(rooms_updated[0]["size"], 30)
			self.assertEqual(rooms_updated[0]["description"], "An expanded testing room")
		finally:
			database.close()
			db_path.unlink(missing_ok=True)

	def test_room_events_since_turn_and_completed_turn_updates(self) -> None:
		"""
		Purpose:
			Verify room backlog reads and completed-turn writes behave as expected.
		"""
		db_path = TESTS_DIR / f"test_sim_turns_{uuid.uuid4().hex}.db"
		database = Database(str(db_path))

		try:
			database.initialize()
			room_id = database.create_room(8, "A focused test room.", room_id="room_a")
			character_id = database.create_character(
				name="Alice",
				background="Keeps notes.",
				personality="Precise.",
				current_room_id=room_id,
				character_id="alice",
			)
			database.create_event(1, character_id, "Turn one event.", room_id=room_id)
			database.create_event(2, character_id, "Turn two event.", room_id=room_id)

			rows = database.get_room_events_since_turn(room_id, after_turn=1)
			self.assertEqual(len(rows), 1)
			self.assertEqual(rows[0]["log"], "Turn two event.")

			database.update_character_last_completed_turn(character_id, 2)
			character = database.get_character(character_id)
			self.assertEqual(character["last_completed_turn"], 2)
		finally:
			database.close()
			db_path.unlink(missing_ok=True)


if __name__ == "__main__":
	unittest.main()
