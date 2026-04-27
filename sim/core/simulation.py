from dataclasses import dataclass, field
from typing import Optional

from sim.core.database import Database
from sim.services.llm_client import OllamaClient

@dataclass
class Simulation:
	"""
	Purpose:
		Store the current simulation state and control whether the simulation
		is running, paused, or stopped.

	Inputs:
		None at construction time. The simulation starts empty and can be
		populated later by UI flows such as character creation, room creation,
		or save-file loading.

	Outputs:
		A Simulation object with empty rooms, empty characters, and default
		runtime state.
	"""

	# Starts empty so the app can launch before the user creates anything.
	rooms: list[dict] = field(default_factory=list)
	characters: list[dict] = field(default_factory=list)
	event_log: list[str] = field(default_factory=list)

	# Runtime state.
	tick_count: int = 0
	is_running: bool = False
	is_paused: bool = False

	# Internal timing values for ticking the simulation over time.
	_time_accumulator: float = 0.0
	tick_interval: float = 1.0
	db_path: Optional[str] = None
	database: Database = field(init=False, repr=False)
	llm_client: OllamaClient = field(init=False, repr=False)

	def __post_init__(self) -> None:
		"""
		Purpose:
			Initialize systems that should not be passed directly into the
			dataclass constructor.

		Inputs:
			None.

		Outputs:
			None. Creates the database connection and ensures the schema exists.
		"""

		self.database = Database(self.db_path)
		self.database.initialize()
		self.llm_client = OllamaClient.from_env()

	def get_model_startup_warning(self) -> Optional[str]:
		"""
		Purpose:
			Expose any user-facing model availability warning at startup time.

		Inputs:
			None.

		Outputs:
			A warning string when the current Ollama configuration is not ready,
			otherwise None.
		"""
		return self.llm_client.get_startup_warning()

	def start(self) -> None:
		"""
		Purpose:
			Start the simulation.

		Inputs:
			None.

		Outputs:
			None. Updates internal state so the simulation begins advancing
			when update() is called.
		"""

		self.is_running = True
		self.is_paused = False

	def pause(self) -> None:
		"""
		Purpose:
			Pause the simulation without clearing its current state.

		Inputs:
			None.

		Outputs:
			None. If the simulation is currently running, it becomes paused.
		"""

		if self.is_running:
			self.is_paused = True

	def resume(self) -> None:
		"""
		Purpose:
			Resume the simulation after a pause.

		Inputs:
			None.

		Outputs:
			None. If the simulation is currently running, it becomes unpaused.
		"""

		if self.is_running:
			self.is_paused = False

	def stop(self) -> None:
		"""
		Purpose:
			Stop the simulation clock without deleting rooms, characters,
			or prior log history.

		Inputs:
			None.

		Outputs:
			None. Runtime flags are reset so update() no longer advances time.
		"""

		self.is_running = False
		self.is_paused = False
		self._time_accumulator = 0.0

	def clear(self) -> None:
		"""
		Purpose:
			Fully clear the simulation back to an empty state.

		Inputs:
			None.

		Outputs:
			None. Removes all rooms, characters, log entries, and resets
			runtime counters.
		"""

		self.rooms.clear()
		self.characters.clear()
		self.event_log.clear()
		self.tick_count = 0
		self.is_running = False
		self.is_paused = False
		self._time_accumulator = 0.0

	def add_room(self, room_data: dict) -> None:
		"""
		Purpose:
			Add a room to the simulation if it does not already exist.

		Inputs:
			room_data: A dictionary representing one room.

		Outputs:
			None. Appends the room if it is valid and not already present.
		"""

		if room_data:
			room_id = room_data.get("id")
			if not any(r.get("id") == room_id for r in self.rooms):
				self.rooms.append(room_data)

	def add_character(self, character: dict) -> None:
		"""
		Purpose:
			Add a character to the simulation.

		Inputs:
			character: A dictionary representing one character. For now this is
				kept loose so we can evolve the structure.

		Outputs:
			None. Adds the character to the simulation if a value was provided.
		"""

		if character:
			self.characters.append(character)

	def load_state(self, rooms: list[dict], characters: list[dict]) -> None:
		"""
		Purpose:
			Replace the current simulation content with externally provided data.
			This is the future hook for loading from a save file or character
			creator flow.

		Inputs:
			rooms: A list of room dictionaries.
			characters: A list of character dictionaries.

		Outputs:
			None. Replaces current rooms and characters with the provided data.
		"""

		self.rooms = list(rooms)
		self.characters = list(characters)
		self.event_log.clear()
		self.tick_count = 0
		self.is_running = False
		self.is_paused = False
		self._time_accumulator = 0.0

	def save_to_db(self) -> None:
		"""
		Purpose:
			Serialize and save the current simulation state to the database.
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
			self.database.upsert_character(char_id, name, background, personality, room_id)

	def load_from_db(self) -> None:
		"""
		Purpose:
			Load the simulation state from the database.
		"""
		db_rooms = self.database.get_all_rooms()
		db_characters = self.database.get_all_characters()

		self.rooms = [dict(r) for r in db_rooms]
		self.characters = [dict(c) for c in db_characters]

	def update(self, dt: float) -> None:
		"""
		Purpose:
			Advance internal simulation time based on frame delta time.

		Inputs:
			dt: Elapsed time in seconds since the last frame.

		Outputs:
			None. Calls step() whenever enough time has accumulated for one
			simulation tick.
		"""

		if not self.is_running or self.is_paused:
			return

		self._time_accumulator += dt

		while self._time_accumulator >= self.tick_interval:
			self.step()
			self._time_accumulator -= self.tick_interval

	def step(self) -> None:
		"""
		Purpose:
			Advance the simulation by one tick.

		Inputs:
			None.

		Outputs:
			None. Increments the tick counter and records a simple event log
			entry. Later this is where orchestrator / agent logic will go.
		"""

		self.tick_count += 1
		self.event_log.append(f"Tick {self.tick_count}: simulation advanced.")

		# Prevent the log from growing forever during early prototyping.
		if len(self.event_log) > 50:
			self.event_log.pop(0)

	def shutdown(self) -> None:
		"""
		Purpose:
			Clean up long-lived resources before the application exits.

		Inputs:
			None.

		Outputs:
			None. Closes the database connection.
		"""

		self.database.close()


	def create_room(self) -> dict:
		"""
		Purpose:
			Interactively create a new room through console prompts. Persists
			the new room to both the in-memory list and the database so that
			AI-driven actions (e.g. RoomUpdateAction) can later mutate it.

		Inputs:
			None. Prompts user for input.

		Outputs:
			The created room dictionary that was added to the simulation.
		"""
		print("\n=== Room Creator ===")

		while True:
			room_id = input("Enter room id (e.g. kitchen, lab_a): ").strip()
			if not room_id:
				print("Room id cannot be empty. Please try again.")
				continue
			if any(r.get("id") == room_id for r in self.rooms):
				print(f"A room with id '{room_id}' already exists. Pick another id.")
				continue
			break

		while True:
			size_raw = input("Enter room size (non-negative integer): ").strip()
			try:
				size = int(size_raw)
			except ValueError:
				print("Size must be an integer. Please try again.")
				continue
			if size < 0:
				print("Size cannot be negative. Please try again.")
				continue
			break

		while True:
			description = input("Enter room description: ").strip()
			if description:
				break
			print("Description cannot be empty. Please try again.")

		room = {"id": room_id, "size": size, "description": description}
		self.rooms.append(room)
		self.database.upsert_room(room_id, size, description)

		print(f"\nRoom '{room_id}' created successfully!")
		return room

	def list_rooms(self) -> list[dict]:
		"""
		Purpose:
			Print a numbered listing of every room in the simulation.

		Inputs:
			None.

		Outputs:
			The list of rooms (same reference as self.rooms).
		"""
		print("\n=== Rooms ===")
		if not self.rooms:
			print("(no rooms yet)")
			return self.rooms

		for index, room in enumerate(self.rooms, start=1):
			print(
				f"{index}. id={room.get('id')}  "
				f"size={room.get('size')}  "
				f"description={room.get('description')}"
			)
		return self.rooms

	def _pick_room(self, prompt: str) -> Optional[dict]:
		"""
		Purpose:
			Helper to let the user pick an existing room by its 1-based index
			from the list shown in list_rooms.

		Inputs:
			prompt: The prompt label shown to the user.

		Outputs:
			The selected room dictionary, or None if there are no rooms or the
			user cancels with an empty entry.
		"""
		if not self.rooms:
			print("No rooms exist yet.")
			return None

		self.list_rooms()
		while True:
			choice = input(f"{prompt} (number, blank to cancel): ").strip()
			if not choice:
				return None
			try:
				index = int(choice)
			except ValueError:
				print("Please enter a number.")
				continue
			if 1 <= index <= len(self.rooms):
				return self.rooms[index - 1]
			print(f"Please enter a number between 1 and {len(self.rooms)}.")

	def edit_room(self) -> Optional[dict]:
		"""
		Purpose:
			Interactively edit an existing room's description and/or size.
			Empty input leaves the existing field unchanged.

		Inputs:
			None.

		Outputs:
			The updated room dictionary, or None if the user cancelled.
		"""
		print("\n=== Edit Room ===")
		room = self._pick_room("Pick a room to edit")
		if room is None:
			return None

		size_raw = input(
			f"New size (blank keeps {room.get('size')}): "
		).strip()
		if size_raw:
			try:
				size = int(size_raw)
				if size < 0:
					print("Size cannot be negative. Keeping previous value.")
				else:
					room["size"] = size
			except ValueError:
				print("Size must be an integer. Keeping previous value.")

		description = input(
			"New description (blank keeps current): "
		).strip()
		if description:
			room["description"] = description

		self.database.upsert_room(
			room["id"],
			int(room.get("size", 0)),
			str(room.get("description", "")),
		)
		print(f"Room '{room['id']}' updated.")
		return room

	def delete_room(self) -> Optional[str]:
		"""
		Purpose:
			Interactively delete an existing room after confirmation.

		Inputs:
			None.

		Outputs:
			The id of the deleted room, or None if the user cancelled.
		"""
		print("\n=== Delete Room ===")
		room = self._pick_room("Pick a room to delete")
		if room is None:
			return None

		confirm = input(
			f"Type the room id '{room['id']}' to confirm deletion: "
		).strip()
		if confirm != room["id"]:
			print("Deletion cancelled.")
			return None

		room_id = room["id"]
		self.rooms = [r for r in self.rooms if r.get("id") != room_id]
		for character in self.characters:
			if character.get("current_room_id") == room_id:
				character["current_room_id"] = None
		self.database.delete_room(room_id)
		print(f"Room '{room_id}' deleted.")
		return room_id

	def manage_rooms(self) -> None:
		"""
		Purpose:
			Run an interactive room manager loop that exposes create / list /
			edit / delete actions until the user exits.

		Inputs:
			None.

		Outputs:
			None.
		"""
		menu = (
			"\n=== Room Manager ===\n"
			"1) List rooms\n"
			"2) Create room\n"
			"3) Edit room\n"
			"4) Delete room\n"
			"5) Done\n"
		)
		while True:
			print(menu)
			choice = input("Choose an option: ").strip()
			if choice == "1":
				self.list_rooms()
			elif choice == "2":
				self.create_room()
			elif choice == "3":
				self.edit_room()
			elif choice == "4":
				self.delete_room()
			elif choice == "5" or choice.lower() in {"done", "q", "quit", "exit"}:
				return
			else:
				print("Unknown option. Please choose 1-5.")

	def create_character(self) -> dict:
		"""
		Purpose:
			Interactively create a new character through console prompts.

		Inputs:
			None. Prompts user for input.

		Outputs:
			The created character dictionary that was added to the simulation.
		"""
		print("\n=== Character Creator ===")
		
		# Get character name
		while True:
			name = input("Enter character name: ").strip()
			if name:
				break
			print("Name cannot be empty. Please try again.")
		
		# Get background
		while True:
			background = input("Enter character background: ").strip()
			if background:
				break
			print("Background cannot be empty. Please try again.")
		
		# Get personality
		while True:
			personality = input("Enter character personality: ").strip()
			if personality:
				break
			print("Personality cannot be empty. Please try again.")
		
		# Create character dict
		character = {
			"name": name,
			"background": background,
			"personality": personality
		}
		
		# Add to simulation
		self.add_character(character)
		
		print(f"\nCharacter '{name}' created successfully!")
		return character
