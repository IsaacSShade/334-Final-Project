import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from sim.core.simulation import Simulation

TESTS_DIR = Path(__file__).resolve().parent


class TestRoomManager(unittest.TestCase):
    """
    Purpose:
        Cover the interactive room manager helpers added for issue #4.
    """

    def setUp(self) -> None:
        self.db_path = TESTS_DIR / f"room_manager_test_{uuid.uuid4().hex}.db"
        self.sim = Simulation(db_path=str(self.db_path))
        # Drop any rooms auto-seeded by Simulation (e.g. the lobby/library
        # default world) so each test starts from a deterministic empty state.
        for room in list(self.sim.rooms):
            self.sim.database.delete_room(room["id"])
        self.sim.rooms.clear()

    def tearDown(self) -> None:
        self.sim.shutdown()
        self.db_path.unlink(missing_ok=True)

    @patch("builtins.input", side_effect=["kitchen", "12", "A warm tidy kitchen."])
    def test_create_room_persists_in_memory_and_db(self, _mock_input):
        room = self.sim.create_room()

        self.assertEqual(room["id"], "kitchen")
        self.assertEqual(room["size"], 12)
        self.assertEqual(room["description"], "A warm tidy kitchen.")
        self.assertEqual(self.sim.rooms, [room])

        stored = self.sim.database.get_room("kitchen")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["size"], 12)
        self.assertEqual(stored["description"], "A warm tidy kitchen.")

    @patch(
        "builtins.input",
        side_effect=[
            "",            # empty id rejected
            "lab",         # accepted id
            "abc",         # bad size rejected
            "-1",          # negative size rejected
            "5",           # accepted size
            "",            # empty description rejected
            "A small lab.",
        ],
    )
    def test_create_room_validates_inputs(self, _mock_input):
        room = self.sim.create_room()

        self.assertEqual(room, {"id": "lab", "size": 5, "description": "A small lab."})

    @patch("builtins.input", side_effect=["kitchen", "12", "Original description."])
    def test_create_room_rejects_duplicate_id(self, _mock_input):
        self.sim.create_room()

        with patch(
            "builtins.input",
            side_effect=["kitchen", "kitchen2", "8", "Different room."],
        ):
            second = self.sim.create_room()

        self.assertEqual(second["id"], "kitchen2")
        self.assertEqual(len(self.sim.rooms), 2)

    def test_list_rooms_returns_rooms_reference(self):
        self.sim.rooms.append(
            {"id": "kitchen", "size": 12, "description": "A kitchen."}
        )

        result = self.sim.list_rooms()

        self.assertIs(result, self.sim.rooms)

    @patch(
        "builtins.input",
        side_effect=["1", "20", "A larger room."],
    )
    def test_edit_room_updates_in_memory_and_db(self, _mock_input):
        self.sim.rooms.append(
            {"id": "kitchen", "size": 12, "description": "A kitchen."}
        )
        self.sim.database.upsert_room("kitchen", 12, "A kitchen.")

        updated = self.sim.edit_room()

        self.assertIsNotNone(updated)
        self.assertEqual(updated["size"], 20)
        self.assertEqual(updated["description"], "A larger room.")

        stored = self.sim.database.get_room("kitchen")
        self.assertEqual(stored["size"], 20)
        self.assertEqual(stored["description"], "A larger room.")

    @patch("builtins.input", side_effect=["1", "", ""])
    def test_edit_room_keeps_existing_when_blank(self, _mock_input):
        self.sim.rooms.append(
            {"id": "kitchen", "size": 12, "description": "A kitchen."}
        )
        self.sim.database.upsert_room("kitchen", 12, "A kitchen.")

        updated = self.sim.edit_room()

        self.assertEqual(updated["size"], 12)
        self.assertEqual(updated["description"], "A kitchen.")

    @patch("builtins.input", side_effect=[""])
    def test_edit_room_cancels_on_blank_pick(self, _mock_input):
        self.sim.rooms.append(
            {"id": "kitchen", "size": 12, "description": "A kitchen."}
        )

        result = self.sim.edit_room()

        self.assertIsNone(result)

    @patch("builtins.input", side_effect=["1", "kitchen"])
    def test_delete_room_removes_room_and_clears_character_link(self, _mock_input):
        self.sim.rooms.append(
            {"id": "kitchen", "size": 12, "description": "A kitchen."}
        )
        self.sim.database.upsert_room("kitchen", 12, "A kitchen.")
        self.sim.characters.append(
            {"id": "alice", "name": "Alice", "current_room_id": "kitchen"}
        )

        deleted_id = self.sim.delete_room()

        self.assertEqual(deleted_id, "kitchen")
        self.assertEqual(self.sim.rooms, [])
        self.assertIsNone(self.sim.characters[0]["current_room_id"])
        self.assertIsNone(self.sim.database.get_room("kitchen"))

    @patch("builtins.input", side_effect=["1", "wrong"])
    def test_delete_room_aborts_without_matching_id(self, _mock_input):
        self.sim.rooms.append(
            {"id": "kitchen", "size": 12, "description": "A kitchen."}
        )
        self.sim.database.upsert_room("kitchen", 12, "A kitchen.")

        result = self.sim.delete_room()

        self.assertIsNone(result)
        self.assertEqual(len(self.sim.rooms), 1)
        self.assertIsNotNone(self.sim.database.get_room("kitchen"))

    @patch(
        "builtins.input",
        side_effect=["1", "2", "lab", "3", "A research lab.", "5"],
    )
    def test_manage_rooms_menu_creates_then_exits(self, _mock_input):
        self.sim.manage_rooms()

        self.assertEqual(len(self.sim.rooms), 1)
        self.assertEqual(self.sim.rooms[0]["id"], "lab")


class TestDatabaseDeleteRoom(unittest.TestCase):
    def test_delete_room_clears_character_link(self) -> None:
        db_path = TESTS_DIR / f"db_delete_room_{uuid.uuid4().hex}.db"
        sim = Simulation(db_path=str(db_path))
        try:
            sim.database.upsert_room("kitchen", 10, "A kitchen.")
            sim.database.upsert_character(
                "alice", "Alice", "Bg", "Pers", "kitchen"
            )

            sim.database.delete_room("kitchen")

            self.assertIsNone(sim.database.get_room("kitchen"))
            character = sim.database.get_character("alice")
            self.assertIsNotNone(character)
            self.assertIsNone(character["current_room_id"])
        finally:
            sim.shutdown()
            db_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
