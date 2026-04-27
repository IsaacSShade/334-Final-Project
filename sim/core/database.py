from pathlib import Path
import sqlite3
import uuid
from typing import Optional


class Database:
	"""
	Purpose:
		Manage SQLite persistence for simulation data.
	"""

	def __init__(self, db_path: Optional[str] = None) -> None:
		"""
		Purpose:
			Create the database manager and open a SQLite connection.

		Inputs:
			db_path: Optional override path to the SQLite database file.

		Outputs:
			None.
		"""

		if db_path is None:
			project_sim_dir = Path(__file__).resolve().parent.parent
			self.db_path = project_sim_dir / "data" / "sim.db"
		else:
			self.db_path = Path(db_path)

		self.connection = self._connect()

	def _connect(self) -> sqlite3.Connection:
		"""
		Purpose:
			Open a SQLite connection and enable foreign key support.

		Inputs:
			None.

		Outputs:
			A live sqlite3 connection.
		"""
		self.db_path.parent.mkdir(parents=True, exist_ok=True)

		connection = sqlite3.connect(self.db_path, check_same_thread=False)
		connection.row_factory = sqlite3.Row
		connection.execute("PRAGMA foreign_keys = ON;")
		return connection

	def initialize(self) -> None:
		"""
		Purpose:
			Create the required database tables if they do not already exist.

		Inputs:
			None.

		Outputs:
			None.
		"""
		schema = """
		CREATE TABLE IF NOT EXISTS rooms (
			id TEXT PRIMARY KEY,
			size INTEGER NOT NULL CHECK (size >= 0),
			description TEXT NOT NULL
		);

		CREATE TABLE IF NOT EXISTS characters (
			id TEXT PRIMARY KEY,
			name TEXT NOT NULL,
			background TEXT NOT NULL,
			personality TEXT NOT NULL,
			current_room_id TEXT,
			last_completed_turn INTEGER NOT NULL DEFAULT 0,
			FOREIGN KEY (current_room_id) REFERENCES rooms(id) ON DELETE SET NULL
		);

		CREATE TABLE IF NOT EXISTS events (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			turn_number INTEGER NOT NULL,
			character_id TEXT NOT NULL,
			room_id TEXT,
			log TEXT NOT NULL,
			created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
			FOREIGN KEY (character_id) REFERENCES characters(id),
			FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE SET NULL
		);

		CREATE TABLE IF NOT EXISTS memories (
			id TEXT PRIMARY KEY,
			character_id TEXT NOT NULL,
			memory_type TEXT NOT NULL CHECK (memory_type IN ('short_term', 'long_term')),
			text TEXT NOT NULL,
			source_event_id INTEGER,
			created_turn INTEGER,
			created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
			FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
			FOREIGN KEY (source_event_id) REFERENCES events(id) ON DELETE SET NULL
		);

		CREATE TABLE IF NOT EXISTS conversations (
			id TEXT PRIMARY KEY,
			turn_number INTEGER NOT NULL,
			room_id TEXT NOT NULL,
			initiator_id TEXT NOT NULL,
			recipient_id TEXT NOT NULL,
			status TEXT NOT NULL,
			exchange_count INTEGER NOT NULL DEFAULT 0,
			summary TEXT,
			FOREIGN KEY (room_id) REFERENCES rooms(id),
			FOREIGN KEY (initiator_id) REFERENCES characters(id),
			FOREIGN KEY (recipient_id) REFERENCES characters(id)
		);

		CREATE TABLE IF NOT EXISTS conversation_messages (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			conversation_id TEXT NOT NULL,
			speaker_id TEXT NOT NULL,
			exchange_number INTEGER NOT NULL,
			message TEXT NOT NULL,
			should_end INTEGER NOT NULL DEFAULT 0,
			end_reason TEXT,
			FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
			FOREIGN KEY (speaker_id) REFERENCES characters(id)
		);

		CREATE INDEX IF NOT EXISTS idx_events_turn_number
		ON events(turn_number);

		CREATE INDEX IF NOT EXISTS idx_memories_character_id
		ON memories(character_id);

		CREATE INDEX IF NOT EXISTS idx_memories_character_type
		ON memories(character_id, memory_type);

		CREATE INDEX IF NOT EXISTS idx_characters_current_room
		ON characters(current_room_id);

		CREATE INDEX IF NOT EXISTS idx_events_room_turn
		ON events(room_id, turn_number, id);

		CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation
		ON conversation_messages(conversation_id, exchange_number);
		"""
		self.connection.executescript(schema)
		self._ensure_character_schema()
		self.connection.commit()

	def _ensure_character_schema(self) -> None:
		"""
		Purpose:
			Apply lightweight schema upgrades for existing local databases.

		Inputs:
			None.

		Outputs:
			None.
		"""
		columns = {
			row["name"]
			for row in self.connection.execute("PRAGMA table_info(characters)")
		}
		if "last_completed_turn" not in columns:
			self.connection.execute(
				"""
				ALTER TABLE characters
				ADD COLUMN last_completed_turn INTEGER NOT NULL DEFAULT 0
				"""
			)

	def close(self) -> None:
		"""
		Purpose:
			Close the database connection cleanly.

		Inputs:
			None.

		Outputs:
			None.
		"""
		self.connection.close()

	def create_room(
		self,
		size: int,
		description: str,
		room_id: Optional[str] = None,
	) -> str:
		"""
		Purpose:
			Insert a new room into the database.

		Inputs:
			size: Non-negative room size value.
			description: Human-readable room description.
			room_id: Optional custom room identifier.

		Outputs:
			The room identifier that was inserted.
		"""
		if room_id is None:
			room_id = str(uuid.uuid4())

		self.connection.execute(
			"""
			INSERT INTO rooms (id, size, description)
			VALUES (?, ?, ?)
			""",
			(room_id, size, description),
		)
		self.connection.commit()
		return room_id

	def upsert_room(self, room_id: str, size: int, description: str) -> None:
		"""
		Purpose:
			Insert or update a room in the database.

		Inputs:
			room_id: Identifier of the room.
			size: Non-negative room size value.
			description: Human-readable room description.

		Outputs:
			None.
		"""
		self.connection.execute(
			"""
			INSERT INTO rooms (id, size, description)
			VALUES (?, ?, ?)
			ON CONFLICT(id) DO UPDATE SET
				size=excluded.size,
				description=excluded.description
			""",
			(room_id, size, description),
		)
		self.connection.commit()

	def update_room_description(self, room_id: str, description: str) -> None:
		"""
		Purpose:
			Update the current description of a room.

		Inputs:
			room_id: The room to update.
			description: The new room description.

		Outputs:
			None.
		"""
		self.connection.execute(
			"""
			UPDATE rooms
			SET description = ?
			WHERE id = ?
			""",
			(description, room_id),
		)
		self.connection.commit()

	def create_character(
		self,
		name: str,
		background: str,
		personality: str,
		current_room_id: Optional[str] = None,
		character_id: Optional[str] = None,
		last_completed_turn: int = 0,
	) -> str:
		"""
		Purpose:
			Insert a new character into the database.

		Inputs:
			name: Character name.
			background: Character backstory/background text.
			personality: Character personality text.
			current_room_id: Optional room the character currently occupies.
			character_id: Optional custom character identifier.
			last_completed_turn: The latest completed world turn for this actor.

		Outputs:
			The character identifier that was inserted.
		"""
		if character_id is None:
			character_id = str(uuid.uuid4())

		self.connection.execute(
			"""
			INSERT INTO characters (
				id,
				name,
				background,
				personality,
				current_room_id,
				last_completed_turn
			)
			VALUES (?, ?, ?, ?, ?, ?)
			""",
			(
				character_id,
				name,
				background,
				personality,
				current_room_id,
				last_completed_turn,
			),
		)
		self.connection.commit()
		return character_id

	def upsert_character(
		self,
		character_id: str,
		name: str,
		background: str,
		personality: str,
		current_room_id: Optional[str] = None,
		last_completed_turn: Optional[int] = None,
	) -> None:
		"""
		Purpose:
			Insert or update a character in the database.

		Inputs:
			character_id: The identifier for the character.
			name: Character name.
			background: Character backstory/background text.
			personality: Character personality text.
			current_room_id: Optional room the character currently occupies.
			last_completed_turn: Optional completed-turn override.

		Outputs:
			None.
		"""
		if last_completed_turn is None:
			last_completed_turn = 0

		self.connection.execute(
			"""
			INSERT INTO characters (
				id,
				name,
				background,
				personality,
				current_room_id,
				last_completed_turn
			)
			VALUES (?, ?, ?, ?, ?, ?)
			ON CONFLICT(id) DO UPDATE SET
				name=excluded.name,
				background=excluded.background,
				personality=excluded.personality,
				current_room_id=excluded.current_room_id,
				last_completed_turn=excluded.last_completed_turn
			""",
			(
				character_id,
				name,
				background,
				personality,
				current_room_id,
				last_completed_turn,
			),
		)
		self.connection.commit()

	def move_character(self, character_id: str, room_id: Optional[str]) -> None:
		"""
		Purpose:
			Update a character's current room assignment.

		Inputs:
			character_id: The character to move.
			room_id: The room to move them into, or None.

		Outputs:
			None.
		"""
		self.connection.execute(
			"""
			UPDATE characters
			SET current_room_id = ?
			WHERE id = ?
			""",
			(room_id, character_id),
		)
		self.connection.commit()

	def update_character_last_completed_turn(
		self,
		character_id: str,
		turn_number: int,
	) -> None:
		"""
		Purpose:
			Update the latest completed world turn for a character.

		Inputs:
			character_id: The character to update.
			turn_number: The latest completed world turn number.

		Outputs:
			None.
		"""
		self.connection.execute(
			"""
			UPDATE characters
			SET last_completed_turn = ?
			WHERE id = ?
			""",
			(turn_number, character_id),
		)
		self.connection.commit()

	def get_room(self, room_id: str) -> Optional[sqlite3.Row]:
		"""
		Purpose:
			Fetch a single room by its identifier.

		Inputs:
			room_id: The room identifier to fetch.

		Outputs:
			A sqlite3.Row if found, otherwise None.
		"""
		cursor = self.connection.execute(
			"""
			SELECT *
			FROM rooms
			WHERE id = ?
			""",
			(room_id,),
		)
		return cursor.fetchone()

	def get_character(self, character_id: str) -> Optional[sqlite3.Row]:
		"""
		Purpose:
			Fetch a single character by identifier.

		Inputs:
			character_id: The character identifier to fetch.

		Outputs:
			A sqlite3.Row if found, otherwise None.
		"""
		cursor = self.connection.execute(
			"""
			SELECT *
			FROM characters
			WHERE id = ?
			""",
			(character_id,),
		)
		return cursor.fetchone()

	def get_characters_in_room(self, room_id: str) -> list[sqlite3.Row]:
		"""
		Purpose:
			Fetch all characters currently assigned to a room.

		Inputs:
			room_id: The room identifier.

		Outputs:
			A list of sqlite3.Row objects.
		"""
		cursor = self.connection.execute(
			"""
			SELECT *
			FROM characters
			WHERE current_room_id = ?
			ORDER BY name
			""",
			(room_id,),
		)
		return list(cursor.fetchall())

	def get_recent_room_events(
		self,
		room_id: str,
		limit: int = 20,
	) -> list[sqlite3.Row]:
		"""
		Purpose:
			Fetch recent events tied to a specific room.

		Inputs:
			room_id: The room identifier.
			limit: Maximum number of events to return.

		Outputs:
			A list of sqlite3.Row objects.
		"""
		cursor = self.connection.execute(
			"""
			SELECT *
			FROM events
			WHERE room_id = ?
			ORDER BY turn_number DESC, id DESC
			LIMIT ?
			""",
			(room_id, limit),
		)
		return list(cursor.fetchall())

	def get_room_events_since_turn(
		self,
		room_id: str,
		after_turn: int,
		limit: Optional[int] = None,
	) -> list[sqlite3.Row]:
		"""
		Purpose:
			Fetch room-local events newer than a given completed turn.

		Inputs:
			room_id: The room whose events should be returned.
			after_turn: Lower exclusive turn-number bound.
			limit: Optional maximum number of rows.

		Outputs:
			A list of sqlite3.Row objects in chronological order.
		"""
		query = """
		SELECT *
		FROM events
		WHERE room_id = ?
			AND turn_number > ?
		ORDER BY turn_number ASC, id ASC
		"""
		parameters: list[object] = [room_id, after_turn]

		if limit is not None:
			query += " LIMIT ?"
			parameters.append(limit)

		cursor = self.connection.execute(query, parameters)
		return list(cursor.fetchall())

	def create_event(
		self,
		turn_number: int,
		character_id: str,
		log: str,
		room_id: Optional[str] = None,
	) -> int:
		"""
		Purpose:
			Insert a summarized event log entry for a character turn.

		Inputs:
			turn_number: The simulation turn number.
			character_id: The acting character.
			log: Short natural-language event summary.
			room_id: Optional room tied to the event.

		Outputs:
			The integer event identifier that was inserted.
		"""
		cursor = self.connection.execute(
			"""
			INSERT INTO events (turn_number, character_id, room_id, log)
			VALUES (?, ?, ?, ?)
			""",
			(turn_number, character_id, room_id, log),
		)
		event_id = cursor.lastrowid

		if event_id is None:
			self.connection.rollback()
			raise RuntimeError("Failed to retrieve event ID after insert.")

		self.connection.commit()
		return event_id

	def create_memory(
		self,
		character_id: str,
		memory_type: str,
		text: str,
		source_event_id: Optional[int] = None,
		created_turn: Optional[int] = None,
		memory_id: Optional[str] = None,
	) -> str:
		"""
		Purpose:
			Insert a character memory record.

		Inputs:
			character_id: The character who owns the memory.
			memory_type: Either 'short_term' or 'long_term'.
			text: The memory text.
			source_event_id: Optional related event identifier.
			created_turn: Optional turn when the memory was formed.
			memory_id: Optional custom memory identifier.

		Outputs:
			The memory identifier that was inserted.
		"""
		if memory_type not in {"short_term", "long_term"}:
			raise ValueError("memory_type must be 'short_term' or 'long_term'.")

		if memory_id is None:
			memory_id = str(uuid.uuid4())

		self.connection.execute(
			"""
			INSERT INTO memories (
				id,
				character_id,
				memory_type,
				text,
				source_event_id,
				created_turn
			)
			VALUES (?, ?, ?, ?, ?, ?)
			""",
			(
				memory_id,
				character_id,
				memory_type,
				text,
				source_event_id,
				created_turn,
			),
		)
		self.connection.commit()
		return memory_id

	def get_character_memories(
		self,
		character_id: str,
		memory_type: Optional[str] = None,
		limit: Optional[int] = None,
	) -> list[sqlite3.Row]:
		"""
		Purpose:
			Fetch memory rows for a given character.

		Inputs:
			character_id: The character whose memories should be returned.
			memory_type: Optional filter for 'short_term' or 'long_term'.
			limit: Optional maximum number of rows to return.

		Outputs:
			A list of sqlite3.Row objects.
		"""
		query = """
		SELECT *
		FROM memories
		WHERE character_id = ?
		"""
		parameters: list[object] = [character_id]

		if memory_type is not None:
			query += " AND memory_type = ?"
			parameters.append(memory_type)

		query += " ORDER BY created_turn DESC, created_at DESC"

		if limit is not None:
			query += " LIMIT ?"
			parameters.append(limit)

		cursor = self.connection.execute(query, parameters)
		return list(cursor.fetchall())

	def get_recent_events(self, limit: int = 20) -> list[sqlite3.Row]:
		"""
		Purpose:
			Fetch the most recent event summaries.

		Inputs:
			limit: Maximum number of events to return.

		Outputs:
			A list of sqlite3.Row objects.
		"""
		cursor = self.connection.execute(
			"""
			SELECT *
			FROM events
			ORDER BY turn_number DESC, id DESC
			LIMIT ?
			""",
			(limit,),
		)
		return list(cursor.fetchall())

	def create_conversation(
		self,
		turn_number: int,
		room_id: str,
		initiator_id: str,
		recipient_id: str,
		status: str = "active",
		conversation_id: Optional[str] = None,
	) -> str:
		"""
		Purpose:
			Create a conversation row before transcript messages are appended.

		Inputs:
			turn_number: The current simulation turn.
			room_id: The room where the conversation occurs.
			initiator_id: The starting speaker.
			recipient_id: The target speaker.
			status: Current conversation status.
			conversation_id: Optional custom identifier.

		Outputs:
			The conversation identifier that was inserted.
		"""
		if conversation_id is None:
			conversation_id = str(uuid.uuid4())

		self.connection.execute(
			"""
			INSERT INTO conversations (
				id,
				turn_number,
				room_id,
				initiator_id,
				recipient_id,
				status
			)
			VALUES (?, ?, ?, ?, ?, ?)
			""",
			(
				conversation_id,
				turn_number,
				room_id,
				initiator_id,
				recipient_id,
				status,
			),
		)
		self.connection.commit()
		return conversation_id

	def append_conversation_message(
		self,
		conversation_id: str,
		speaker_id: str,
		exchange_number: int,
		message: str,
		should_end: bool = False,
		end_reason: Optional[str] = None,
	) -> int:
		"""
		Purpose:
			Append one message to a persisted conversation transcript.

		Inputs:
			conversation_id: Identifier for the conversation.
			speaker_id: The speaking character.
			exchange_number: 1-based message order.
			message: The utterance text.
			should_end: Whether the speaker is signaling a wrap-up.
			end_reason: Optional reason the conversation should end.

		Outputs:
			The inserted transcript row ID.
		"""
		cursor = self.connection.execute(
			"""
			INSERT INTO conversation_messages (
				conversation_id,
				speaker_id,
				exchange_number,
				message,
				should_end,
				end_reason
			)
			VALUES (?, ?, ?, ?, ?, ?)
			""",
			(
				conversation_id,
				speaker_id,
				exchange_number,
				message,
				int(should_end),
				end_reason,
			),
		)
		message_id = cursor.lastrowid
		self.connection.commit()

		if message_id is None:
			raise RuntimeError("Failed to retrieve conversation message ID.")

		return message_id

	def complete_conversation(
		self,
		conversation_id: str,
		exchange_count: int,
		summary: str,
		status: str = "completed",
	) -> None:
		"""
		Purpose:
			Mark a conversation finished and persist its summary.

		Inputs:
			conversation_id: Identifier for the conversation.
			exchange_count: Number of transcript messages stored.
			summary: Final natural-language summary.
			status: Final status string.

		Outputs:
			None.
		"""
		self.connection.execute(
			"""
			UPDATE conversations
			SET status = ?,
				exchange_count = ?,
				summary = ?
			WHERE id = ?
			""",
			(status, exchange_count, summary, conversation_id),
		)
		self.connection.commit()

	def get_conversation(self, conversation_id: str) -> Optional[sqlite3.Row]:
		"""
		Purpose:
			Fetch a single conversation record.

		Inputs:
			conversation_id: Identifier for the conversation.

		Outputs:
			A sqlite3.Row if found, otherwise None.
		"""
		cursor = self.connection.execute(
			"""
			SELECT *
			FROM conversations
			WHERE id = ?
			""",
			(conversation_id,),
		)
		return cursor.fetchone()

	def get_conversation_messages(self, conversation_id: str) -> list[sqlite3.Row]:
		"""
		Purpose:
			Fetch transcript rows for one conversation.

		Inputs:
			conversation_id: Identifier for the conversation.

		Outputs:
			A list of sqlite3.Row objects ordered by exchange number.
		"""
		cursor = self.connection.execute(
			"""
			SELECT *
			FROM conversation_messages
			WHERE conversation_id = ?
			ORDER BY exchange_number
			""",
			(conversation_id,),
		)
		return list(cursor.fetchall())

	def get_all_rooms(self) -> list[sqlite3.Row]:
		"""
		Purpose:
			Fetch all rooms currently in the database.

		Inputs:
			None.

		Outputs:
			A list of sqlite3.Row objects.
		"""
		cursor = self.connection.execute(
			"""
			SELECT *
			FROM rooms
			ORDER BY id
			"""
		)
		return list(cursor.fetchall())

	def get_all_characters(self) -> list[sqlite3.Row]:
		"""
		Purpose:
			Fetch all characters currently in the database.

		Inputs:
			None.

		Outputs:
			A list of sqlite3.Row objects.
		"""
		cursor = self.connection.execute(
			"""
			SELECT *
			FROM characters
			ORDER BY name
			"""
		)
		return list(cursor.fetchall())

	def get_latest_turn_number(self) -> int:
		"""
		Purpose:
			Fetch the latest completed or recorded world turn number.

		Inputs:
			None.

		Outputs:
			The latest known world turn number, or 0 if no turns exist.
		"""
		row = self.connection.execute(
			"""
			SELECT MAX(turn_value) AS latest_turn
			FROM (
				SELECT COALESCE(MAX(last_completed_turn), 0) AS turn_value
				FROM characters
				UNION ALL
				SELECT COALESCE(MAX(turn_number), 0) AS turn_value
				FROM events
				UNION ALL
				SELECT COALESCE(MAX(turn_number), 0) AS turn_value
				FROM conversations
			)
			"""
		).fetchone()
		if row is None or row["latest_turn"] is None:
			return 0
		return int(row["latest_turn"])

	def clear_history(self) -> None:
		"""
		Purpose:
			Clear event, conversation, and memory history while preserving rooms
			and characters.

		Inputs:
			None.

		Outputs:
			None.
		"""
		self.connection.execute("DELETE FROM conversation_messages")
		self.connection.execute("DELETE FROM conversations")
		self.connection.execute("DELETE FROM memories")
		self.connection.execute("DELETE FROM events")
		self.connection.execute(
			"""
			UPDATE characters
			SET last_completed_turn = 0
			"""
		)
		self.connection.commit()

	def clear_world(self) -> None:
		"""
		Purpose:
			Clear the entire persisted world, including rooms and characters.

		Inputs:
			None.

		Outputs:
			None.
		"""
		self.connection.execute("DELETE FROM conversation_messages")
		self.connection.execute("DELETE FROM conversations")
		self.connection.execute("DELETE FROM memories")
		self.connection.execute("DELETE FROM events")
		self.connection.execute("DELETE FROM characters")
		self.connection.execute("DELETE FROM rooms")
		self.connection.commit()
