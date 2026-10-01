"""그룹 내부 선택 상태. 카드가 아직 없어도 경로만으로 고를 수 있다."""


def apply_select(selected: set[str], paths: list[str], on: bool) -> None:
    for path in paths:
        if on:
            selected.add(path)
        else:
            selected.discard(path)


def selected_in_group(group_paths: list[str], selected: set[str]) -> list[str]:
    return [path for path in group_paths if path in selected]


def range_paths(order: list[str], anchor: str, current: str) -> list[str]:
    try:
        start, end = order.index(anchor), order.index(current)
    except ValueError:
        return [current] if current in order else []
    lo, hi = (start, end) if start <= end else (end, start)
    return order[lo : hi + 1]


def selected_bytes(sizes: dict[str, int], paths: list[str]) -> int:
    return sum(int(sizes.get(path) or 0) for path in paths)
