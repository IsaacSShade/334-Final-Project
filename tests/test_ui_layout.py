import unittest

import pygame

from sim.ui.layout import compute_all_token_rects, compute_room_grid, get_character_color
from sim.ui.scene_state import SceneState


class TestUILayout(unittest.TestCase):
	def test_room_grid_and_token_layout_cover_all_entities(self) -> None:
		container = pygame.Rect(0, 0, 800, 500)
		rooms = [
			{"id": "commons"},
			{"id": "kitchen"},
			{"id": "studio"},
			{"id": "garden"},
		]
		characters = [
			{"id": "ava", "name": "Ava", "current_room_id": "commons"},
			{"id": "blake", "name": "Blake", "current_room_id": "commons"},
			{"id": "casey", "name": "Casey", "current_room_id": "studio"},
		]

		room_rects = compute_room_grid(container, rooms)
		token_rects = compute_all_token_rects(room_rects, rooms, characters)

		self.assertEqual(set(room_rects), {"commons", "kitchen", "studio", "garden"})
		self.assertEqual(set(token_rects), {"ava", "blake", "casey"})
		for rect in token_rects.values():
			self.assertGreater(rect.width, 0)
			self.assertGreater(rect.height, 0)

	def test_character_color_is_stable(self) -> None:
		self.assertEqual(get_character_color("ava"), get_character_color("ava"))
		self.assertNotEqual(get_character_color("ava"), get_character_color("blake"))

	def test_scene_state_animates_room_changes(self) -> None:
		scene_state = SceneState(animation_duration=0.3)
		first_rects = {"ava": pygame.Rect(10, 10, 20, 20)}
		scene_state.sync(
			[{"id": "ava", "current_room_id": "commons"}],
			first_rects,
			now=0.0,
		)

		second_rects = {"ava": pygame.Rect(110, 110, 20, 20)}
		scene_state.sync(
			[{"id": "ava", "current_room_id": "studio"}],
			second_rects,
			now=1.0,
		)
		draw_rects = scene_state.resolve_draw_rects(second_rects, now=1.1)

		self.assertNotEqual(draw_rects["ava"].center, second_rects["ava"].center)
