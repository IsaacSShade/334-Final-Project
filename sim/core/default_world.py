from __future__ import annotations

from sim.core.database import Database


DEFAULT_ROOMS: tuple[dict[str, object], ...] = (
	{
		"id": "commons",
		"size": 14,
		"description": "A shared commons with couches, plants, and a coffee table.",
	},
	{
		"id": "kitchen",
		"size": 12,
		"description": "A bright kitchen with a long counter and a half-full fruit bowl.",
	},
	{
		"id": "studio",
		"size": 10,
		"description": "A quiet studio filled with sketch pads, lamps, and a messy desk.",
	},
	{
		"id": "garden",
		"size": 16,
		"description": "A small enclosed garden with stone paths and a wooden bench.",
	},
)

DEFAULT_CHARACTERS: tuple[dict[str, object], ...] = (
	{
		"id": "ava",
		"name": "Ava",
		"background": "Ava is a thoughtful organizer who likes to keep shared spaces welcoming.",
		"personality": "Warm, observant, and practical.",
		"current_room_id": "commons",
	},
	{
		"id": "blake",
		"name": "Blake",
		"background": "Blake is a curious neighbor who enjoys conversation and wandering.",
		"personality": "Friendly, impulsive, curious, and eager to explore new places.",
		"current_room_id": "kitchen",
	},
	{
		"id": "casey",
		"name": "Casey",
		"background": "Casey is an artist who notices small details and likes changing environments.",
		"personality": "Creative, reflective, and a little dramatic.",
		"current_room_id": "studio",
	},
	{
		"id": "drew",
		"name": "Drew",
		"background": "Drew prefers calm spaces and often checks in on what others are doing.",
		"personality": "Patient, steady, and prefers staying where things feel calm.",
		"current_room_id": "garden",
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

	for character in DEFAULT_CHARACTERS:
		database.create_character(
			name=str(character["name"]),
			background=str(character["background"]),
			personality=str(character["personality"]),
			current_room_id=str(character["current_room_id"]),
			character_id=str(character["id"]),
		)
