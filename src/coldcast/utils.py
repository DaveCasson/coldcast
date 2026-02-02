from __future__ import annotations

from typing import Iterable, List, Union


NumberSpec = Union[int, str]


def expand_sequence(definition: Union[Iterable[NumberSpec], dict]) -> List[int]:
    if isinstance(definition, dict):
        start = int(definition.get("start", 0))
        end = int(definition["end"])
        step = int(definition.get("step", 1))
        return list(range(start, end + step, step))
    return [int(value) for value in definition]
