import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from sim.core.orchestrator import OrchestratorResult
from sim.core.simulation import Simulation
from sim.services.llm_client import OllamaClientError

TESTS_DIR = Path(__file__).resolve().parent

class TestSimulation(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = TESTS_DIR / f"simulation_test_{uuid.uuid4().hex}.db"
        self.sim = Simulation(db_path=str(self.db_path), auto_seed_world=False)

    def tearDown(self) -> None:
        self.sim.shutdown()
        self.db_path.unlink(missing_ok=True)

    def test_auto_seed_populates_default_world(self):
        self.sim.shutdown()
        self.db_path.unlink(missing_ok=True)
        seeded = Simulation(db_path=str(self.db_path))

        try:
            rooms = seeded.database.get_all_rooms()
            characters = seeded.database.get_all_characters()
            self.assertGreaterEqual(len(rooms), 4)
            self.assertGreaterEqual(len(characters), 4)
            occupancy = {character["current_room_id"] for character in characters}
            self.assertEqual(len(occupancy), len(characters))
            self.assertTrue(
                any("curious" in str(character["personality"]).lower() for character in characters)
            )
        finally:
            seeded.shutdown()

    @patch('builtins.input', side_effect=['Alice', 'A curious explorer', 'Adventurous and friendly'])
    def test_create_character_success(self, mock_input):
        """Test successful character creation through interactive prompts."""
        character = self.sim.create_character()
        
        expected = {
            "name": "Alice",
            "background": "A curious explorer", 
            "personality": "Adventurous and friendly"
        }
        
        self.assertEqual(character, expected)
        self.assertEqual(len(self.sim.characters), 1)
        self.assertEqual(self.sim.characters[0], expected)

    @patch('builtins.input', side_effect=['', 'Alice', '', 'Background here', '', 'Personality here'])
    def test_create_character_validation(self, mock_input):
        """Test that empty inputs are rejected and re-prompted."""
        character = self.sim.create_character()
        
        expected = {
            "name": "Alice",
            "background": "Background here",
            "personality": "Personality here"
        }
        
        self.assertEqual(character, expected)
        self.assertEqual(len(self.sim.characters), 1)

    @patch('builtins.input', side_effect=['Alice', 'Background', 'Personality'])
    @patch('builtins.print')
    def test_create_character_output(self, mock_print, mock_input):
        """Test that the method prints appropriate messages."""
        self.sim.create_character()
        
        # Check that success message was printed (contains the key text)
        printed_calls = [call.args[0] for call in mock_print.call_args_list]
        success_message_found = any("Character 'Alice' created successfully!" in call for call in printed_calls)
        self.assertTrue(success_message_found, f"Success message not found in: {printed_calls}")

    def test_reset_simulation_clears_history_but_keeps_world(self):
        self.sim.database.create_room(10, "A shared room.", room_id="room_a")
        self.sim.database.create_character(
            name="Alice",
            background="Observant.",
            personality="Calm.",
            current_room_id="room_a",
            character_id="alice",
        )
        event_id = self.sim.database.create_event(1, "alice", "Alice looked around.", room_id="room_a")
        self.sim.database.create_memory(
            character_id="alice",
            memory_type="short_term",
            text="I looked around the room.",
            source_event_id=event_id,
            created_turn=1,
        )
        self.sim.event_log.append("Some event")
        self.sim.tick_count = 3

        self.sim.reset_simulation()

        self.assertEqual(len(self.sim.database.get_all_rooms()), 1)
        self.assertEqual(len(self.sim.database.get_all_characters()), 1)
        self.assertEqual(self.sim.database.get_recent_events(), [])
        self.assertEqual(self.sim.database.get_character_memories("alice"), [])
        self.assertEqual(self.sim.tick_count, 0)
        self.assertEqual(self.sim.event_log, [])

    def test_reset_world_clears_rooms_and_characters(self):
        self.sim.database.create_room(10, "A shared room.", room_id="room_a")
        self.sim.database.create_character(
            name="Alice",
            background="Observant.",
            personality="Calm.",
            current_room_id="room_a",
            character_id="alice",
        )

        self.sim.reset_world()

        self.assertEqual(self.sim.database.get_all_rooms(), [])
        self.assertEqual(self.sim.database.get_all_characters(), [])
        self.assertEqual(self.sim.get_scene_state()["world_empty"], True)

    def test_pause_takes_effect_after_one_character_step(self):
        self.sim.database.create_room(10, "A shared room.", room_id="room_a")
        self.sim.database.create_character(
            name="Alice",
            background="Observant.",
            personality="Calm.",
            current_room_id="room_a",
            character_id="alice",
        )

        class FakeOrchestrator:
            def __init__(self):
                self.calls = 0

            def run_character_turn(self):
                self.calls += 1
                return OrchestratorResult(turn_number=1, public_log_entries=["Alice took no action."])

        self.sim.orchestrator = FakeOrchestrator()

        with patch.object(self.sim, "get_model_startup_warning", return_value=None):
            self.assertTrue(self.sim.start())
            self.sim.pause()
            self.sim.update(self.sim.tick_interval)

        self.assertEqual(self.sim.orchestrator.calls, 1)
        self.assertTrue(self.sim.is_paused)

    def test_update_does_not_catch_up_multiple_character_turns_after_delay(self):
        self.sim.database.create_room(10, "A shared room.", room_id="room_a")
        self.sim.database.create_character(
            name="Alice",
            background="Observant.",
            personality="Calm.",
            current_room_id="room_a",
            character_id="alice",
        )

        class FakeOrchestrator:
            def __init__(self):
                self.calls = 0

            def run_character_turn(self):
                self.calls += 1
                return OrchestratorResult(turn_number=self.calls, public_log_entries=[f"Turn {self.calls}"])

        self.sim.orchestrator = FakeOrchestrator()

        with patch.object(self.sim, "get_model_startup_warning", return_value=None):
            self.assertTrue(self.sim.start())
            self.sim.update(self.sim.tick_interval * 3)

        self.assertEqual(self.sim.orchestrator.calls, 1)
        self.assertEqual(self.sim.tick_count, 1)

    def test_step_pauses_instead_of_crashing_on_ollama_parse_failure(self):
        self.sim.database.create_room(10, "A shared room.", room_id="room_a")
        self.sim.database.create_character(
            name="Alice",
            background="Observant.",
            personality="Calm.",
            current_room_id="room_a",
            character_id="alice",
        )

        class FailingOrchestrator:
            def run_character_turn(self):
                raise OllamaClientError("Ollama returned non-JSON structured output.")

        self.sim.orchestrator = FailingOrchestrator()
        self.sim.is_running = True

        self.sim.step()

        self.assertFalse(self.sim.is_running)
        self.assertTrue(self.sim.is_paused)
        self.assertIn("could not be parsed", self.sim.event_log[-1])

if __name__ == "__main__":
    unittest.main()
