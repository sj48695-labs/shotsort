"""Small, UI-independent pagination state for lazily rendered image groups."""

from dataclasses import dataclass


@dataclass
class GroupPage:
    """Track which item indexes a group UI still needs to create.

    ``reveal`` is safe to call for every expansion event: an already rendered page
    is never returned again, so collapsing and reopening does not recreate images.
    """

    total: int
    page_size: int = 24
    rendered: int = 0

    def __post_init__(self) -> None:
        if self.total < 0:
            raise ValueError("total must be non-negative")
        if self.page_size <= 0:
            raise ValueError("page_size must be positive")

    @property
    def remaining(self) -> int:
        return self.total - self.rendered

    def reveal(self, *, expanded: bool) -> range:
        if not expanded or self.rendered:
            return range(0, 0)
        return self.more()

    def more(self) -> range:
        if not self.remaining:
            return range(0, 0)
        start = self.rendered
        self.rendered = min(self.total, start + self.page_size)
        return range(start, self.rendered)
