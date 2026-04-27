from __future__ import annotations

from hashlib import sha256
import math

import pygame


HEADER_HEIGHT = 92
GRID_PADDING = 16
ROOM_CARD_PADDING = 12
ROOM_HEADER_HEIGHT = 28
EVENT_PANEL_WIDTH = 320


def build_layout(
	window_width: int,
	window_height: int,
	rooms: list[dict],
	connections: list[dict] | None = None,
) -> dict[str, object]:
	"""
	Purpose:
		Compute the main HUD, room-graph, and event-panel rectangles for the
		current window size.
	"""
	header_rect = pygame.Rect(0, 0, window_width, HEADER_HEIGHT)
	grid_rect = pygame.Rect(
		GRID_PADDING,
		HEADER_HEIGHT + GRID_PADDING,
		max(120, window_width - EVENT_PANEL_WIDTH - (GRID_PADDING * 3)),
		max(120, window_height - HEADER_HEIGHT - (GRID_PADDING * 2)),
	)
	event_rect = pygame.Rect(
		grid_rect.right + GRID_PADDING,
		HEADER_HEIGHT + GRID_PADDING,
		EVENT_PANEL_WIDTH - GRID_PADDING,
		grid_rect.height,
	)
	room_rects = compute_room_layout(grid_rect, rooms, connections or [])

	return {
		"header_rect": header_rect,
		"grid_rect": grid_rect,
		"event_rect": event_rect,
		"room_rects": room_rects,
	}


def compute_room_layout(
	container_rect: pygame.Rect,
	rooms: list[dict],
	connections: list[dict],
) -> dict[str, pygame.Rect]:
	"""
	Purpose:
		Position rooms in a circular layout so connection lines between them
		are visible and no room is strictly grid-locked.
	"""
	if not rooms:
		return {}

	room_count = len(rooms)
	room_w = max(140, min(220, (container_rect.width - GRID_PADDING * 2) // max(1, room_count) - GRID_PADDING))
	room_h = max(96, min(160, (container_rect.height - GRID_PADDING * 2) // 2))

	cx = container_rect.x + container_rect.width // 2
	cy = container_rect.y + container_rect.height // 2

	if room_count == 1:
		rx = cx - room_w // 2
		ry = cy - room_h // 2
		return {str(rooms[0]["id"]): pygame.Rect(rx, ry, room_w, room_h)}

	radius_x = max(room_w, (container_rect.width - room_w * 2) // 2)
	radius_y = max(room_h, (container_rect.height - room_h * 2) // 2)

	room_rects: dict[str, pygame.Rect] = {}
	for index, room in enumerate(rooms):
		angle = (2 * math.pi * index / room_count) - (math.pi / 2)
		rx = int(cx + radius_x * math.cos(angle)) - room_w // 2
		ry = int(cy + radius_y * math.sin(angle)) - room_h // 2
		rx = max(container_rect.x, min(container_rect.right - room_w, rx))
		ry = max(container_rect.y, min(container_rect.bottom - room_h, ry))
		room_rects[str(room["id"])] = pygame.Rect(rx, ry, room_w, room_h)

	return room_rects


def compute_room_token_rects(
	room_rect: pygame.Rect,
	characters: list[dict],
) -> dict[str, pygame.Rect]:
	"""
	Purpose:
		Compute token rectangles for the characters inside one room.
	"""
	if not characters:
		return {}

	content = pygame.Rect(
		room_rect.x + ROOM_CARD_PADDING,
		room_rect.y + ROOM_HEADER_HEIGHT + ROOM_CARD_PADDING,
		max(20, room_rect.width - ROOM_CARD_PADDING * 2),
		max(20, room_rect.height - ROOM_HEADER_HEIGHT - ROOM_CARD_PADDING * 2),
	)

	count = len(characters)
	columns = max(1, math.ceil(math.sqrt(count)))
	rows = max(1, math.ceil(count / columns))
	cell_width = max(20, content.width // columns)
	cell_height = max(20, content.height // rows)
	token_size = max(18, min(40, int(min(cell_width, cell_height) * 0.7)))

	token_rects: dict[str, pygame.Rect] = {}
	for index, character in enumerate(characters):
		column = index % columns
		row = index // columns
		cell_x = content.x + column * cell_width
		cell_y = content.y + row * cell_height
		x = cell_x + (cell_width - token_size) // 2
		y = cell_y + (cell_height - token_size) // 2
		token_rects[str(character["id"])] = pygame.Rect(x, y, token_size, token_size)

	return token_rects


def compute_all_token_rects(
	room_rects: dict[str, pygame.Rect],
	rooms: list[dict],
	characters: list[dict],
) -> dict[str, pygame.Rect]:
	"""
	Purpose:
		Compute token rectangles for every character in the current world.
	"""
	characters_by_room: dict[str, list[dict]] = {}
	for character in sorted(characters, key=lambda row: str(row.get("name", "")).lower()):
		room_id = character.get("current_room_id")
		if room_id is None:
			continue
		characters_by_room.setdefault(str(room_id), []).append(character)

	token_rects: dict[str, pygame.Rect] = {}
	for room in rooms:
		room_id = str(room["id"])
		room_rect = room_rects.get(room_id)
		if room_rect is None:
			continue

		token_rects.update(
			compute_room_token_rects(room_rect, characters_by_room.get(room_id, []))
		)

	return token_rects


def get_character_color(character_id: str) -> tuple[int, int, int]:
	"""
	Purpose:
		Derive a stable pseudo-random token color from a character identifier.
	"""
	digest = sha256(character_id.encode("utf-8")).digest()
	return (
		80 + digest[0] % 140,
		80 + digest[1] % 140,
		80 + digest[2] % 140,
	)
