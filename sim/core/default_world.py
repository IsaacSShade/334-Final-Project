from __future__ import annotations

from sim.core.database import Database


DEFAULT_ROOMS: tuple[dict[str, object], ...] = (
	{
		"id": "lobby",
		"size": 20,
		"description": "A grand lobby with marble floors and a large chandelier.",
	},
	{
		"id": "library",
		"size": 15,
		"description": "A quiet library filled with dusty books and comfortable chairs.",
	},
)

DEFAULT_CONNECTIONS: tuple[tuple[str, str], ...] = (
	("lobby", "library"),
)

DEFAULT_CHARACTERS: tuple[dict[str, object], ...] = (
	{
		"id": "ava",
		"name": "Ava",
		"background": "Ava is a thoughtful organizer who likes to keep shared spaces welcoming.",
		"personality": "Warm, observant, and practical.",
		"current_room_id": "lobby",
	},
	{
		"id": "blake",
		"name": "Blake",
		"background": "Blake is a curious neighbor who enjoys conversation and wandering.",
		"personality": "Friendly, impulsive, curious, and eager to explore new places.",
		"current_room_id": "lobby",
	},
	{
		"id": "casey",
		"name": "Casey",
		"background": "Casey is an artist who notices small details and likes changing environments.",
		"personality": "Creative, reflective, and a little dramatic.",
		"current_room_id": "library",
	},
	{
		"id": "drew",
		"name": "Drew",
		"background": "Drew prefers calm spaces and often checks in on what others are doing.",
		"personality": "Patient, steady, and prefers staying where things feel calm.",
		"current_room_id": "library",
	},
)


def seed_default_world(database: Database) -> None:
	"""
	Purpose:
		Seed a small starter world when the runtime database is empty.

	Inputs:
		database: The active database gateway.

	Outputs:
		None.
	"""
	if database.get_all_rooms() and database.get_all_characters():
		return

	database.clear_world()

	for room in DEFAULT_ROOMS:
		database.create_room(
			size=int(room["size"]),
			description=str(room["description"]),
			room_id=str(room["id"]),
		)

	for room_a, room_b in DEFAULT_CONNECTIONS:
		database.connect_rooms(room_a, room_b)

	for character in DEFAULT_CHARACTERS:
		database.create_character(
			name=str(character["name"]),
			background=str(character["background"]),
			personality=str(character["personality"]),
			current_room_id=str(character["current_room_id"]),
			character_id=str(character["id"]),
		)
