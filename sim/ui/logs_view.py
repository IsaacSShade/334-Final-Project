from __future__ import annotations
import pygame
from typing import Any

BACKGROUND = (20, 20, 28)
PANEL = (28, 31, 42)
PANEL_BORDER = (85, 90, 110)
TEXT = (235, 235, 240)
SUBTLE_TEXT = (180, 183, 195)
ACCENT = (74, 112, 170)
DIM = (120, 124, 140)
CONVERSATION_BG = (32, 38, 55)
ROOM_CARD_BG = (24, 28, 40)

LINE_H = 22
INDENT = 20
ROOM_CARD_H = 80
ROOM_CARD_W = 200
ROOM_CARD_GAP = 12


class LogsView:
    """
    Purpose:
        Render the detailed Logs tab -- room snapshots plus a scrollable,
        collapsible event timeline.
    """

    def __init__(self) -> None:
        self._scroll_offset: int = 0
        self._expanded: set[int] = set()
        self._last_header_rects: dict[int, pygame.Rect] = {}

    def handle_event(self, event: pygame.event.Event, content_rect: pygame.Rect) -> None:
        """Process scroll and click events for the logs panel."""
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_offset = max(0, self._scroll_offset - event.y * LINE_H * 3)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos, content_rect)

    def _handle_click(self, pos: tuple[int, int], content_rect: pygame.Rect) -> None:
        if not content_rect.collidepoint(pos):
            return
        for entry_id, header_rect in self._last_header_rects.items():
            if header_rect.collidepoint(pos):
                if entry_id in self._expanded:
                    self._expanded.discard(entry_id)
                else:
                    self._expanded.add(entry_id)
                return

    def render(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
        detailed_logs: dict[str, Any],
        font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        """Render the full logs tab into content_rect."""
        self._last_header_rects = {}
        pygame.draw.rect(screen, BACKGROUND, content_rect)

        rooms = detailed_logs.get("rooms", [])
        entries = detailed_logs.get("entries", [])

        # --- Room snapshot strip ---
        room_strip_h = ROOM_CARD_H + 32
        room_strip_rect = pygame.Rect(content_rect.x, content_rect.y, content_rect.width, room_strip_h)
        self._draw_room_strip(screen, room_strip_rect, rooms, font, small_font)

        # --- Event list ---
        list_rect = pygame.Rect(
            content_rect.x,
            content_rect.y + room_strip_h + 8,
            content_rect.width,
            content_rect.height - room_strip_h - 8,
        )
        self._draw_event_list(screen, list_rect, entries, font, small_font)

    def _draw_room_strip(
        self,
        screen: pygame.Surface,
        strip_rect: pygame.Rect,
        rooms: list[dict],
        font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        label = small_font.render("Current Rooms", True, SUBTLE_TEXT)
        screen.blit(label, (strip_rect.x + 12, strip_rect.y + 6))
        x = strip_rect.x + 12
        y = strip_rect.y + 26
        for room in rooms:
            card = pygame.Rect(x, y, ROOM_CARD_W, ROOM_CARD_H)
            pygame.draw.rect(screen, ROOM_CARD_BG, card, border_radius=8)
            pygame.draw.rect(screen, PANEL_BORDER, card, width=1, border_radius=8)
            rid = font.render(str(room.get("id", "")), True, TEXT)
            screen.blit(rid, (card.x + 8, card.y + 6))
            desc_words = str(room.get("description", "")).split()
            desc_line = ""
            for w in desc_words:
                test = f"{desc_line} {w}".strip()
                if small_font.size(test)[0] < ROOM_CARD_W - 16:
                    desc_line = test
                else:
                    break
            if desc_line:
                suffix = "..." if len(desc_words) > len(desc_line.split()) else ""
                ds = small_font.render(desc_line + suffix, True, SUBTLE_TEXT)
                screen.blit(ds, (card.x + 8, card.y + 26))
            occupants = ", ".join(room.get("occupants", []))
            if occupants:
                os_ = small_font.render(f"In: {occupants}", True, DIM)
                screen.blit(os_, (card.x + 8, card.y + 54))
            x += ROOM_CARD_W + ROOM_CARD_GAP
            if x + ROOM_CARD_W > strip_rect.right - 12:
                break

    def _draw_event_list(
        self,
        screen: pygame.Surface,
        list_rect: pygame.Rect,
        entries: list[dict],
        font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        screen.set_clip(list_rect)

        label = small_font.render("Event Timeline", True, SUBTLE_TEXT)
        screen.blit(label, (list_rect.x + 12, list_rect.y + 4))

        y = list_rect.y + 26 - self._scroll_offset
        pad = 12

        for entry in entries:
            entry_id = entry.get("id", 0)
            entry_type = entry.get("type", "generic")
            is_expandable = entry_type in ("conversation", "room_update")
            is_expanded = entry_id in self._expanded

            # Header row
            header_h = LINE_H + 8
            header_rect = pygame.Rect(list_rect.x + pad, y, list_rect.width - pad * 2, header_h)

            if list_rect.y <= y <= list_rect.bottom:
                color = CONVERSATION_BG if is_expanded else PANEL
                pygame.draw.rect(screen, color, header_rect, border_radius=6)
                pygame.draw.rect(screen, PANEL_BORDER, header_rect, width=1, border_radius=6)

                prefix = "v " if is_expanded else ("> " if is_expandable else "  ")
                turn_label = small_font.render(f"T{entry.get('turn', '?')}", True, DIM)
                screen.blit(turn_label, (header_rect.x + 6, header_rect.y + 6))
                summary_text = f"{prefix}[{entry_type}] {entry.get('summary', '')}"
                wrapped = self._wrap(summary_text, font, header_rect.width - 60)
                summary_surf = font.render(wrapped[0], True, TEXT)
                screen.blit(summary_surf, (header_rect.x + 48, header_rect.y + 5))

                if is_expandable:
                    self._last_header_rects[entry_id] = header_rect

            y += header_h + 2

            # Expanded content
            if is_expanded and list_rect.y <= y <= list_rect.bottom + 200:
                if entry_type == "conversation":
                    transcript = entry.get("transcript", [])
                    for msg in transcript:
                        speaker = str(msg.get("speaker", "?"))
                        message = str(msg.get("message", ""))
                        lines = self._wrap(f"{speaker}: {message}", small_font, list_rect.width - pad * 2 - INDENT * 2)
                        for line in lines:
                            if list_rect.y <= y <= list_rect.bottom:
                                surf = small_font.render(line, True, SUBTLE_TEXT)
                                screen.blit(surf, (list_rect.x + pad + INDENT, y))
                            y += LINE_H
                        y += 2

                elif entry_type == "room_update":
                    before = entry.get("before_description", "")
                    after = entry.get("after_description", "")
                    for label_text, desc in [("Before:", before), ("After:", after)]:
                        if list_rect.y <= y <= list_rect.bottom:
                            lbl = small_font.render(label_text, True, ACCENT)
                            screen.blit(lbl, (list_rect.x + pad + INDENT, y))
                        y += LINE_H
                        for line in self._wrap(desc, small_font, list_rect.width - pad * 2 - INDENT * 2):
                            if list_rect.y <= y <= list_rect.bottom:
                                surf = small_font.render(line, True, SUBTLE_TEXT)
                                screen.blit(surf, (list_rect.x + pad + INDENT * 2, y))
                            y += LINE_H
                        y += 4

            y += 4

        # Max scroll
        content_height = max(0, y + self._scroll_offset - list_rect.y - 26)
        self._scroll_offset = min(self._scroll_offset, max(0, content_height - list_rect.height + 40))

        screen.set_clip(None)

    def _wrap(self, text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        if max_width <= 0:
            return [text]
        words = text.split(" ")
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [text]
