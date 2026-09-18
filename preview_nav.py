"""Pure navigation state for the maximized screenshot preview."""

from __future__ import annotations

from dataclasses import dataclass

EDITABLE_TAGS = frozenset({"input", "textarea", "select"})

_PREVIEW_ACTIONS = {
    "arrowleft": "prev",
    "left": "prev",
    "arrowright": "next",
    "right": "next",
    "escape": "close",
    "esc": "close",
    "delete": "delete",
    "backspace": "delete",
}
_OPEN_KEYS = frozenset({" ", "space", "enter"})


@dataclass
class PreviewNav:
    items: list[dict]
    index: int = 0

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("items must not be empty")
        if not 0 <= self.index < len(self.items):
            raise ValueError("index out of range")

    @classmethod
    def for_item(cls, items: list[dict], current: dict) -> "PreviewNav":
        ordered = list(items)
        path = current["path"]
        index = next((i for i, it in enumerate(ordered) if it["path"] == path), None)
        if index is None:
            ordered = [current]
            index = 0
        return cls(items=ordered, index=index)

    @property
    def current(self) -> dict:
        return self.items[self.index]

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def position(self) -> str:
        return f"{self.index + 1} / {self.total}"

    @property
    def has_prev(self) -> bool:
        return self.index > 0

    @property
    def has_next(self) -> bool:
        return self.index + 1 < self.total

    def prev(self) -> bool:
        if not self.has_prev:
            return False
        self.index -= 1
        return True

    def next(self) -> bool:
        if not self.has_next:
            return False
        self.index += 1
        return True


def shortcut_action(
    key: str, *, preview_open: bool, focused_tag: str | None = None
) -> str | None:
    if (focused_tag or "").lower() in EDITABLE_TAGS:
        return None
    name = key.lower()
    if preview_open:
        return _PREVIEW_ACTIONS.get(name)
    if name in _OPEN_KEYS:
        return "open"
    return None
