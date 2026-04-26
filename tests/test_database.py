import tempfile
import unittest
from pathlib import Path

from sim.core.database import Database


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
		with tempfile.TemporaryDirectory() as temp_dir:
			db_path = Path(temp_dir) / "test_sim.db"
			database = Database(str(db_path))
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

			database.close()

	def test_default_room_creation_and_connections(self) -> None:
		"""
		Purpose:
			Verify that default rooms can be connected and default agents start in the lobby.
		"""
		with tempfile.TemporaryDirectory() as temp_dir:
			db_path = Path(temp_dir) / "test_default_rooms.db"
			database = Database(str(db_path))
			database.initialize()

			# Create default rooms and connect them manually as Simulation would
			database.create_room(size=20, description="Lobby", room_id="lobby")
			database.create_room(size=15, description="Library", room_id="library")
			database.connect_rooms("lobby", "library")

			# Verify two-way connection
			cursor = database.connection.execute("SELECT room_id_2 FROM room_connections WHERE room_id_1 = 'lobby'")
			connected_rooms = [row["room_id_2"] for row in cursor.fetchall()]
			self.assertIn("library", connected_rooms)

			# Verify default agent room assignment
			char_id = database.create_character(name="Agent Smith", background="A test agent.", personality="Stoic.")
			cursor = database.connection.execute("SELECT current_room_id FROM characters WHERE id = ?", (char_id,))
			self.assertEqual(cursor.fetchone()["current_room_id"], "lobby")

			database.close()

if __name__ == "__main__":
	unittest.main()