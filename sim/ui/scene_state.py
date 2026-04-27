from __future__ import annotations

from dataclasses import dataclass

import pygame


@dataclass(slots=True)
class TokenAnimation:
	"""
	Purpose:
		Represent one active room-to-room token animation.
	"""

	start_pos: tuple[float, float]
	end_pos: tuple[float, float]
	start_time: float
	duration: float


class SceneState:
	"""
	Purpose:
		Track snapshot-to-snapshot token movement so the UI can animate room
		changes without the orchestrator owning render details.
	"""

	def __init__(self, animation_duration: float = 0.3) -> None:
		self.animation_duration = animation_duration
		self._last_room_ids: dict[str, str | None] = {}
		self._last_target_centers: dict[str, tuple[float, float]] = {}
		self._animations: dict[str, TokenAnimation] = {}

	def sync(
		self,
		characters: list[dict],
		target_rects: dict[str, pygame.Rect],
		now: float,
	) -> None:
		"""
		Purpose:
			Update animation state from the latest scene snapshot.
		"""
		active_character_ids = {str(character["id"]) for character in characters}

		for character in characters:
			character_id = str(character["id"])
			target_rect = target_rects.get(character_id)
			if target_rect is None:
				continue

			room_id = character.get("current_room_id")
			target_center = (float(target_rect.centerx), float(target_rect.centery))
			previous_room_id = self._last_room_ids.get(character_id)
			previous_center = self._last_target_centers.get(character_id, target_center)

			if previous_room_id is not None and previous_room_id != room_id:
				self._animations[character_id] = TokenAnimation(
					start_pos=previous_center,
					end_pos=target_center,
					start_time=now,
					duration=self.animation_duration,
				)

			self._last_room_ids[character_id] = None if room_id is None else str(room_id)
			self._last_target_centers[character_id] = target_center

		for character_id in list(self._last_room_ids):
			if character_id not in active_character_ids:
				self._last_room_ids.pop(character_id, None)
				self._last_target_centers.pop(character_id, None)
				self._animations.pop(character_id, None)

	def resolve_draw_rects(
		self,
		target_rects: dict[str, pygame.Rect],
		now: float,
	) -> dict[str, pygame.Rect]:
		"""
		Purpose:
			Resolve the current draw rectangles for each token, including active
			movement animations.
		"""
		draw_rects: dict[str, pygame.Rect] = {}

		for character_id, target_rect in target_rects.items():
			animation = self._animations.get(character_id)
			if animation is None:
				draw_rects[character_id] = target_rect.copy()
				continue

			progress = (now - animation.start_time) / max(animation.duration, 0.001)
			if progress >= 1.0:
				self._animations.pop(character_id, None)
				draw_rects[character_id] = target_rect.copy()
				continue

			x = animation.start_pos[0] + (animation.end_pos[0] - animation.start_pos[0]) * progress
			y = animation.start_pos[1] + (animation.end_pos[1] - animation.start_pos[1]) * progress
			draw_rect = target_rect.copy()
			draw_rect.center = (round(x), round(y))
			draw_rects[character_id] = draw_rect

		return draw_rects
