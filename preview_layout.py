"""Layout contract for the maximized screenshot preview."""

from __future__ import annotations


PREVIEW_CARD_CLASSES = "w-full h-full flex flex-col overflow-hidden"
PREVIEW_HEADER_CLASSES = "items-center w-full gap-2 shrink-0"
PREVIEW_IMAGE_WRAPPER_CLASSES = (
    "flex-1 min-h-0 w-full overflow-hidden flex items-center justify-center"
)
PREVIEW_IMAGE_WRAPPER_STYLE = (
    "height:calc(100vh - 11rem);max-height:calc(100vh - 11rem)"
)
PREVIEW_IMAGE_CLASSES = "w-full h-full"
PREVIEW_IMAGE_PROPS = "fit=contain"
PREVIEW_METADATA_CLASSES = "w-full shrink-0 items-center gap-0"


def contained_size(
    source: tuple[float, float], bounds: tuple[float, float]
) -> tuple[float, float]:
    """Return the largest aspect-preserving size that fits inside *bounds*."""
    source_width, source_height = source
    bound_width, bound_height = bounds
    if min(source_width, source_height, bound_width, bound_height) <= 0:
        raise ValueError("source and bounds dimensions must be positive")
    scale = min(bound_width / source_width, bound_height / source_height)
    return source_width * scale, source_height * scale
