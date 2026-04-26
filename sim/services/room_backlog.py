from __future__ import annotations

import sqlite3

from sim.core.database import Database


class RoomBacklogService:
	"""
	Purpose:
		Resolve room-local backlog lines that an actor should see during their
		current active turn.
	"""

	def __init__(self, database: Database) -> None:
		self.database = database
		self.turn_floor = 0
		self._delivered_event_ids: set[int] = set()

	def begin_actor_turn(self, turn_floor: int) -> None:
		"""
		Purpose:
			Initialize backlog tracking for one actor turn.

		Inputs:
			turn_floor: The actor's last completed world turn.

		Outputs:
			None.
		"""
		self.turn_floor = turn_floor
		self._delivered_event_ids.clear()

	def get_room_backlog(self, room_id: str) -> list[str]:
		"""
		Purpose:
			Load room-local backlog lines newer than the actor's last completed
			turn, excluding any rows already delivered during this active turn.

		Inputs:
			room_id: The room whose backlog should be returned.

		Outputs:
			A list of natural-language event log lines.
		"""
		rows = self.database.get_room_events_since_turn(room_id, self.turn_floor)
		backlog: list[str] = []

		for row in rows:
			event_id = int(row["id"])
			if event_id in self._delivered_event_ids:
				continue

			self._delivered_event_ids.add(event_id)
			backlog.append(str(row["log"]))

		return backlog

	def mark_rows_delivered(self, rows: list[sqlite3.Row]) -> None:
		"""
		Purpose:
			Mark externally supplied rows as already delivered during the current
			actor turn.

		Inputs:
			rows: Event rows that should be suppressed from later deliveries.

		Outputs:
			None.
		"""
		for row in rows:
			self._delivered_event_ids.add(int(row["id"]))
