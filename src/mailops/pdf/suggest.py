from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from .text_density import percentile
from .page_signals import PageSignals


@dataclass(frozen=True)
class SuggestConfig:
    abs_min_chars: int = 250

    # Image dominance
    dominant_pixels_threshold: int = 1_000_000  # tune after seeing a few days

    # Relative gating
    rel_percentile: float = 15.0
    rel_apply_only_if_chars_below: int = 350  # gate percentile to avoid false positives


def suggest_excludes(signals: Sequence[PageSignals], cfg: SuggestConfig = SuggestConfig()) -> List[int]:
    if not signals:
        return []

    # Absolute: low chars
    absolute = {s.page_index for s in signals if s.char_count < cfg.abs_min_chars}

    # Absolute: image dominant
    image_dom = {s.page_index for s in signals if s.image_dominant}

    # Relative: only among “somewhat low text” candidates (gating)
    candidates = [s for s in signals if s.char_count < cfg.rel_apply_only_if_chars_below]
    if candidates:
        # Use char_count (not density) for relative ranking; density was misleading.
        values = [s.char_count for s in candidates]
        cutoff = percentile(values, cfg.rel_percentile)
        relative = {s.page_index for s in candidates if s.char_count <= cutoff}
    else:
        relative = set()

    flagged = sorted(absolute | image_dom | relative)
    return flagged
