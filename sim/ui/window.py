import sys

import pygame

from sim.ui.layout import (
	HEADER_HEIGHT,
	build_layout,
	compute_all_token_rects,
	get_character_color,
)
from sim.ui.scene_state import SceneState


BACKGROUND = (20, 20, 28)
PANEL = (28, 31, 42)
PANEL_BORDER = (85, 90, 110)
TEXT = (235, 235, 240)
SUBTLE_TEXT = (180, 183, 195)
DISABLED = (90, 94, 108)
BUTTON = (57, 84, 128)
BUTTON_ACTIVE = (74, 112, 170)
BUTTON_DANGER = (134, 62, 62)
BUTTON_WARNING = (124, 98, 48)


class Window:
	"""
	Purpose:
		Create and run the main pygame window for the project.
	"""

	def __init__(self, simulation) -> None:
		self.simulation = simulation
		self.width = 1280
		self.height = 720
		self.title = "DevOps Town"
		self.scene_state = SceneState(animation_duration=0.3)
		self._buttons: dict[str, pygame.Rect] = {}

	def run(self) -> None:
		"""
		Purpose:
			Start the pygame app loop, update the simulation, and render the
			current world state.
		"""
		pygame.init()
		screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
		pygame.display.set_caption(self.title)
		clock = pygame.time.Clock()
		font = pygame.font.SysFont(None, 22)
		small_font = pygame.font.SysFont(None, 18)
		token_font = pygame.font.SysFont(None, 20)

		self.simulation.load_from_db()
		running = True

		while running:
			dt = clock.tick(60) / 1000.0
			now = pygame.time.get_ticks() / 1000.0
			snapshot = self.simulation.get_scene_state()

			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					running = False
				elif event.type == pygame.VIDEORESIZE:
					self.width = max(960, event.w)
					self.height = max(640, event.h)
					screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
				elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
					self._handle_click(event.pos, snapshot)

			self.simulation.update(dt)
			snapshot = self.simulation.get_scene_state()
			self._draw(screen, snapshot, font, small_font, token_font, now)
			pygame.display.flip()

		self.simulation.shutdown()
		pygame.quit()
		sys.exit()

	def _handle_click(self, position: tuple[int, int], snapshot: dict) -> None:
		if self._buttons.get("start", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
			if snapshot.get("can_start"):
				self.simulation.start()
			return

		if self._buttons.get("pause", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
			if snapshot.get("is_running") and not snapshot.get("is_paused"):
				self.simulation.pause()
			return

		if self._buttons.get("reset_sim", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
			self.simulation.reset_simulation()
			return

		if self._buttons.get("reset_world", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
			self.simulation.reset_world()

	def _draw(
		self,
		screen: pygame.Surface,
		snapshot: dict,
		font: pygame.font.Font,
		small_font: pygame.font.Font,
		token_font: pygame.font.Font,
		now: float,
	) -> None:
		screen.fill(BACKGROUND)
		layout = build_layout(self.width, self.height, snapshot["rooms"])
		token_rects = compute_all_token_rects(
			layout["room_rects"],
			snapshot["rooms"],
			snapshot["characters"],
		)
		self.scene_state.sync(snapshot["characters"], token_rects, now)
		draw_rects = self.scene_state.resolve_draw_rects(token_rects, now)

		self._draw_header(screen, snapshot, layout["header_rect"], font, small_font)
		self._draw_rooms(screen, snapshot, layout["room_rects"], draw_rects, font, token_font)
		self._draw_event_panel(screen, snapshot, layout["event_rect"], small_font)

	def _draw_header(
		self,
		screen: pygame.Surface,
		snapshot: dict,
		header_rect: pygame.Rect,
		font: pygame.font.Font,
		small_font: pygame.font.Font,
	) -> None:
		pygame.draw.rect(screen, PANEL, header_rect)
		pygame.draw.line(screen, PANEL_BORDER, header_rect.bottomleft, header_rect.bottomright, 1)

		title = font.render(f"Turn {snapshot['turn_number']}  |  {snapshot['status'].title()}", True, TEXT)
		screen.blit(title, (16, 16))

		world_message = self._get_world_message(snapshot)
		world_surface = small_font.render(world_message, True, SUBTLE_TEXT)
		screen.blit(world_surface, (16, 44))

		if snapshot.get("startup_warning"):
			warning_surface = small_font.render(str(snapshot["startup_warning"]), True, (232, 176, 90))
			screen.blit(warning_surface, (16, 64))

		self._buttons = self._draw_buttons(screen, snapshot, header_rect, font)

	def _get_world_message(self, snapshot: dict) -> str:
		if snapshot.get("world_empty"):
			return "World is empty. Restart the app to re-seed the starter world, or create rooms and characters later."
		if snapshot.get("pause_requested"):
			return "Pause requested. The current character will finish before advancement stops."
		return f"{len(snapshot['rooms'])} rooms  |  {len(snapshot['characters'])} characters"

	def _draw_buttons(
		self,
		screen: pygame.Surface,
		snapshot: dict,
		header_rect: pygame.Rect,
		font: pygame.font.Font,
	) -> dict[str, pygame.Rect]:
		buttons: dict[str, pygame.Rect] = {}
		button_specs = [
			("start", "Start", BUTTON_ACTIVE, bool(snapshot.get("can_start"))),
			(
				"pause",
				"Pause",
				BUTTON_WARNING,
				bool(snapshot.get("is_running")) and not bool(snapshot.get("is_paused")),
			),
			("reset_sim", "Reset Simulation", BUTTON, True),
			("reset_world", "Reset World", BUTTON_DANGER, True),
		]
		button_width = 160
		button_height = 36
		gap = 12
		start_x = header_rect.width - (button_width * len(button_specs)) - (gap * (len(button_specs) - 1)) - 18
		y = 18

		for index, (key, label, color, enabled) in enumerate(button_specs):
			rect = pygame.Rect(start_x + index * (button_width + gap), y, button_width, button_height)
			fill = color if enabled else DISABLED
			pygame.draw.rect(screen, fill, rect, border_radius=8)
			pygame.draw.rect(screen, PANEL_BORDER, rect, width=1, border_radius=8)
			label_surface = font.render(label, True, TEXT if enabled else SUBTLE_TEXT)
			label_rect = label_surface.get_rect(center=rect.center)
			screen.blit(label_surface, label_rect)
			buttons[key] = rect

		return buttons

	def _draw_rooms(
		self,
		screen: pygame.Surface,
		snapshot: dict,
		room_rects: dict[str, pygame.Rect],
		draw_rects: dict[str, pygame.Rect],
		font: pygame.font.Font,
		token_font: pygame.font.Font,
	) -> None:
		characters_by_id = {str(character["id"]): character for character in snapshot["characters"]}

		for room in snapshot["rooms"]:
			room_id = str(room["id"])
			room_rect = room_rects.get(room_id)
			if room_rect is None:
				continue

			pygame.draw.rect(screen, PANEL, room_rect, border_radius=10)
			pygame.draw.rect(screen, PANEL_BORDER, room_rect, width=1, border_radius=10)
			label = font.render(room_id, True, TEXT)
			screen.blit(label, (room_rect.x + 12, room_rect.y + 8))

		for character_id, draw_rect in draw_rects.items():
			character = characters_by_id.get(character_id)
			if character is None:
				continue

			pygame.draw.rect(
				screen,
				get_character_color(character_id),
				draw_rect,
				border_radius=6,
			)
			pygame.draw.rect(screen, (18, 18, 22), draw_rect, width=1, border_radius=6)
			initial = str(character.get("name", "?"))[:1].upper()
			label_surface = token_font.render(initial, True, (18, 18, 22))
			label_rect = label_surface.get_rect(center=draw_rect.center)
			screen.blit(label_surface, label_rect)

	def _draw_event_panel(
		self,
		screen: pygame.Surface,
		snapshot: dict,
		panel_rect: pygame.Rect,
		font: pygame.font.Font,
	) -> None:
		pygame.draw.rect(screen, PANEL, panel_rect, border_radius=10)
		pygame.draw.rect(screen, PANEL_BORDER, panel_rect, width=1, border_radius=10)
		title = font.render("Recent Events", True, TEXT)
		screen.blit(title, (panel_rect.x + 12, panel_rect.y + 10))

		log_lines = snapshot["event_log"][-12:] if snapshot["event_log"] else ["No events yet."]
		y = panel_rect.y + 40
		for line in log_lines:
			if y > panel_rect.bottom - 22:
				break
			surface = font.render(str(line), True, SUBTLE_TEXT)
			screen.blit(surface, (panel_rect.x + 12, y))
			y += 22
