import unittest
from unittest.mock import patch
from sim.core.simulation import Simulation

class TestSimulation(unittest.TestCase):
    def setUp(self) -> None:
        self.sim = Simulation()

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

if __name__ == "__main__":
    unittest.main()