from dataclasses import dataclass, field


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
	rooms: list[str] = field(default_factory=list)
	characters: list[dict] = field(default_factory=list)
	event_log: list[str] = field(default_factory=list)

	# Runtime state.
	tick_count: int = 0
	is_running: bool = False
	is_paused: bool = False

	# Internal timing values for ticking the simulation over time.
	_time_accumulator: float = 0.0
	tick_interval: float = 1.0

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

	def add_room(self, room_name: str) -> None:
		"""
		Purpose:
			Add a room to the simulation if it does not already exist.

		Inputs:
			room_name: The room name to add.

		Outputs:
			None. Appends the room name if it is valid and not already present.
		"""

		if room_name and room_name not in self.rooms:
			self.rooms.append(room_name)

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

	def load_state(self, rooms: list[str], characters: list[dict]) -> None:
		"""
		Purpose:
			Replace the current simulation content with externally provided data.
			This is the future hook for loading from a save file or character
			creator flow.

		Inputs:
			rooms: A list of room names.
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
