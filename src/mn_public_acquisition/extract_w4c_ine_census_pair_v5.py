from __future__ import annotations

import time
from typing import Any

from . import extract_w4c_ine_census_pair as base
from . import extract_w4c_ine_census_pair_v4 as v4

_ORIGINAL_PUT = base._put_text


def _put_text_retry(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Retry transient optimistic branch-head conflicts only.

    Every retry re-enters the original helper, which re-reads the target path and
    therefore never overwrites a non-identical append-only artifact. Immutable
    output conflicts remain fatal; only HTTP 409 branch-head races are retried.
    """
    delays = (0.5, 1.0, 2.0, 4.0, 8.0)
    last: Exception | None = None
    for attempt in range(len(delays) + 1):
        try:
            return _ORIGINAL_PUT(*args, **kwargs)
        except RuntimeError as exc:
            last = exc
            text = str(exc)
            if ":409:" not in text or attempt >= len(delays):
                raise
            time.sleep(delays[attempt])
    assert last is not None
    raise last


def run(cfg: dict[str, Any], read_token: str, write_token: str) -> dict[str, Any]:
    old_base = base._put_text
    old_v4 = v4._put_text
    base._put_text = _put_text_retry
    v4._put_text = _put_text_retry
    try:
        return v4.run(cfg, read_token, write_token)
    finally:
        base._put_text = old_base
        v4._put_text = old_v4
