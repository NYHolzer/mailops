from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple


POINTS_PER_INCH = 72.0


@dataclass(frozen=True)
class PageTextStats:
    page_index: int  # 0-based index
    char_count: int
    area_sq_in: float
    density: float  # chars per square inch


def extract_page_text(page) -> str:
    """
    pypdf PageObject.extract_text() returns str|None depending on content.
    We normalize to a string.
    """
    text = page.extract_text()
    if text is None:
        return ""
    return text


def page_area_sq_in(page) -> float:
    w_pt = float(page.mediabox.width)
    h_pt = float(page.mediabox.height)
    w_in = w_pt / POINTS_PER_INCH
    h_in = h_pt / POINTS_PER_INCH
    return max(w_in * h_in, 0.0)


def page_text_stats(page, page_index: int) -> PageTextStats:
    text = extract_page_text(page)
    char_count = len("".join(text.split()))  # remove whitespace noise
    area = page_area_sq_in(page)
    density = (char_count / area) if area > 0 else 0.0
    return PageTextStats(
        page_index=page_index,
        char_count=char_count,
        area_sq_in=area,
        density=density,
    )


def percentile(values: Sequence[float], p: float) -> float:
    """
    Simple deterministic percentile:
    - p is 0..100
    - uses linear interpolation between sorted points
    """
    if not values:
        return 0.0
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)

    xs = sorted(values)
    n = len(xs)
    # rank in [0, n-1]
    r = (p / 100.0) * (n - 1)
    lo = int(r)
    hi = min(lo + 1, n - 1)
    frac = r - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def suggest_excludes_hybrid(
    stats: Sequence[PageTextStats],
    *,
    abs_min_chars: int = 250,
    abs_min_density: float = 25.0,
    rel_percentile: float = 20.0,
    max_suggestions: Optional[int] = None,
) -> List[int]:
    """
    Hybrid rule:
      1) Absolute: exclude if char_count < abs_min_chars OR density < abs_min_density
      2) Relative: also exclude pages in the bottom rel_percentile by density
         (to catch ad-heavy pages even if they have some text).

    Returns 0-based page indices, sorted.
    """
    if not stats:
        return []

    densities = [s.density for s in stats]
    cutoff = percentile(densities, rel_percentile)

    flagged = []
    for s in stats:
        absolute_flag = (s.char_count < abs_min_chars) or (s.density < abs_min_density)
        relative_flag = s.density <= cutoff
        if absolute_flag or relative_flag:
            flagged.append(s.page_index)

    flagged = sorted(set(flagged))

    if max_suggestions is not None:
        # Keep lowest density pages first
        flagged_sorted = sorted(flagged, key=lambda idx: next(st.density for st in stats if st.page_index == idx))
        return flagged_sorted[:max_suggestions]

    return flagged
