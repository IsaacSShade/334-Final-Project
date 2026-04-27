import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from sim.core.database import Database
from sim.core.default_world import seed_default_world
from sim.core.orchestrator import Orchestrator
from sim.services.llm_client import OllamaClient, OllamaClientError


@dataclass
class Simulation:
	"""
	Purpose:
		Store the current simulation state and coordinate runtime control for the
		turn-by-turn orchestrator.
	"""

	rooms: list[dict] = field(default_factory=list)
	characters: list[dict] = field(default_factory=list)
	event_log: list[str] = field(default_factory=list)

	tick_count: int = 0
	is_running: bool = False
	is_paused: bool = False
	pause_requested: bool = False

	_time_accumulator: float = 0.0
	tick_interval: float = 1.0
	db_path: Optional[str] = None
	auto_seed_world: bool = True
	database: Database = field(init=False, repr=False)
	llm_client: OllamaClient = field(init=False, repr=False)
	orchestrator: Orchestrator = field(init=False, repr=False)
	_model_startup_warning: Optional[str] = field(init=False, default=None, repr=False)
	_step_thread: Optional[threading.Thread] = field(init=False, default=None, repr=False)
	_step_lock: threading.Lock = field(init=False, default_factory=threading.Lock, repr=False)

	def __post_init__(self) -> None:
		"""
		Purpose:
			Initialize persistent services and optionally seed a starter world.
		"""
		self.database = Database(self.db_path)
		self.database.initialize()
		self.llm_client = OllamaClient.from_env()
		self._model_startup_warning = self.llm_client.get_startup_warning()

		if self.auto_seed_world and self._should_seed_default_world():
			seed_default_world(self.database)

		self.orchestrator = Orchestrator(self.database, self.llm_client)
		self.load_from_db()
		self.tick_count = self.database.get_latest_turn_number()

	def _should_seed_default_world(self) -> bool:
		return not self.database.get_all_rooms() or not self.database.get_all_characters()

	def get_model_startup_warning(self) -> Optional[str]:
		"""
		Purpose:
			Expose any user-facing model availability warning at startup time.
		"""
		return self._model_startup_warning

	def start(self) -> bool:
		"""
		Purpose:
			Start or resume simulation advancement when the world is ready.

		Inputs:
			None.

		Outputs:
			True if advancement can proceed, otherwise False.
		"""
		self._model_startup_warning = self.llm_client.get_startup_warning()
		if self.get_model_startup_warning() is not None:
			return False

		self.load_from_db()
		if not self.rooms or not self.characters:
			return False

		self.is_running = True
		self.is_paused = False
		self.pause_requested = False
		return True

	def pause(self) -> None:
		"""
		Purpose:
			Request a pause after the current character turn finishes.
		"""
		if self.is_running:
			self.pause_requested = True

	def resume(self) -> None:
		"""
		Purpose:
			Resume the simulation after a pause.
		"""
		self.start()

	def stop(self) -> None:
		"""
		Purpose:
			Stop turn advancement without clearing any persistent state.
		"""
		self.is_running = False
		self.is_paused = False
		self.pause_requested = False
		self._time_accumulator = 0.0

	def clear(self) -> None:
		"""
		Purpose:
			Fully clear in-memory state.
		"""
		self.rooms.clear()
		self.characters.clear()
		self.event_log.clear()
		self.tick_count = 0
		self.is_running = False
		self.is_paused = False
		self.pause_requested = False
		self._time_accumulator = 0.0

	def reset_simulation(self) -> None:
		"""
		Purpose:
			Clear derived turn history while preserving the current rooms and
			characters exactly as they are.
		"""
		self.database.clear_history()
		self.orchestrator.reset_runtime()
		self.event_log.clear()
		self.tick_count = 0
		self.is_running = False
		self.is_paused = False
		self.pause_requested = False
		self._time_accumulator = 0.0
		self.load_from_db()

	def reset_world(self) -> None:
		"""
		Purpose:
			Clear the full persisted world, including rooms and characters.
		"""
		self.database.clear_world()
		self.orchestrator.reset_runtime()
		self.clear()
		self.load_from_db()

	def add_room(self, room_data: dict) -> None:
		"""
		Purpose:
			Add a room to the in-memory world snapshot if it does not already
			exist.
		"""
		if room_data:
			room_id = room_data.get("id")
			if not any(r.get("id") == room_id for r in self.rooms):
				self.rooms.append(room_data)

	def add_character(self, character: dict) -> None:
		"""
		Purpose:
			Add a character to the in-memory world snapshot.
		"""
		if character:
			self.characters.append(character)

	def load_state(self, rooms: list[dict], characters: list[dict]) -> None:
		"""
		Purpose:
			Replace the current in-memory state with externally provided data.
		"""
		self.rooms = list(rooms)
		self.characters = list(characters)
		self.event_log.clear()
		self.tick_count = 0
		self.is_running = False
		self.is_paused = False
		self.pause_requested = False
		self._time_accumulator = 0.0

	def save_to_db(self) -> None:
		"""
		Purpose:
			Serialize and save the current in-memory simulation state.
		"""
		for room in self.rooms:
			room_id = room.get("id", "default_room")
			size = room.get("size", 10)
			desc = room.get("description", "A room.")
			self.database.upsert_room(room_id, size, desc)

		for char in self.characters:
			char_id = char.get("id", char.get("name", "unknown_id"))
			name = char.get("name", "Unknown")
			background = char.get("background", "No background")
			personality = char.get("personality", "No personality")
			room_id = char.get("current_room_id")
			last_completed_turn = int(char.get("last_completed_turn", 0) or 0)
			self.database.upsert_character(
				char_id,
				name,
				background,
				personality,
				room_id,
				last_completed_turn=last_completed_turn,
			)

	def load_from_db(self) -> None:
		"""
		Purpose:
			Load the current room and character state from the database.
		"""
		db_rooms = self.database.get_all_rooms()
		db_characters = self.database.get_all_characters()

		self.rooms = [dict(r) for r in db_rooms]
		self.characters = [dict(c) for c in db_characters]

	def get_scene_state(self) -> dict[str, Any]:
		"""
		Purpose:
			Expose a renderer-friendly snapshot of the current world state.
		"""
		self.load_from_db()
		warning = self.get_model_startup_warning()
		status = "running" if self.is_running and not self.is_paused else "paused" if self.is_paused else "idle"
		can_start = warning is None and bool(self.rooms) and bool(self.characters)

		return {
			"turn_number": self.tick_count,
			"rooms": list(self.rooms),
			"characters": list(self.characters),
			"event_log": list(self.event_log),
			"is_running": self.is_running,
			"is_paused": self.is_paused,
			"pause_requested": self.pause_requested,
			"status": status,
			"startup_warning": warning,
			"can_start": can_start,
			"world_empty": not self.rooms or not self.characters,
		}

	def update(self, dt: float) -> None:
		"""
		Purpose:
			Advance internal simulation time based on frame delta time.
		"""
		if not self.is_running or self.is_paused:
			return

		if self._step_thread is not None and self._step_thread.is_alive():
			return

		self._time_accumulator += dt

		if self._time_accumulator < self.tick_interval:
			return

		self._time_accumulator = 0.0
		self._step_thread = threading.Thread(target=self._run_step_locked, daemon=True)
		self._step_thread.start()

	def _run_step_locked(self) -> None:
		with self._step_lock:
			self.step()

	def step(self) -> None:
		"""
		Purpose:
			Advance the simulation by exactly one character turn.
		"""
		try:
			result = self.orchestrator.run_character_turn()
		except OllamaClientError as exc:
			self.is_running = False
			self.is_paused = True
			self.pause_requested = False
			self.event_log.append(f"Simulation paused because the Ollama response could not be parsed: {exc}")
			self.event_log = self.event_log[-50:]
			self._model_startup_warning = str(exc)
			return

		self.tick_count = result.turn_number
		self.event_log.extend(result.public_log_entries)
		self.event_log = self.event_log[-50:]
		self.load_from_db()

		if self.pause_requested:
			self.is_paused = True
			self.pause_requested = False

	def shutdown(self) -> None:
		"""
		Purpose:
			Clean up long-lived resources before the application exits.
		"""
		self.database.close()

	def create_character(self) -> dict:
		"""
		Purpose:
			Interactively create a new character through console prompts.
		"""
		print("\n=== Character Creator ===")

		while True:
			name = input("Enter character name: ").strip()
			if name:
				break
			print("Name cannot be empty. Please try again.")

		while True:
			background = input("Enter character background: ").strip()
			if background:
				break
			print("Background cannot be empty. Please try again.")

		while True:
			personality = input("Enter character personality: ").strip()
			if personality:
				break
			print("Personality cannot be empty. Please try again.")

		character = {
			"name": name,
			"background": background,
			"personality": personality,
		}
		self.add_character(character)

		print(f"\nCharacter '{name}' created successfully!")
		return character
