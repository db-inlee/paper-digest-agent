"""Deterministic trend aggregation over accumulated skim data.

Pure functions only: no file IO, no settings access, no LLM calls. Everything
is derived from the arguments, so the same input always yields the same
TrendSummary and the module can be tested from fixtures alone.
"""

from collections import Counter
from typing import Iterable, Optional

from rtc.schemas.skim import DailySkimOutput, SkimSummary
from rtc.schemas.trend import CountDelta, TrendRepresentative, TrendSummary


def aggregate_trends(
    window: list[DailySkimOutput],
    previous: Optional[list[DailySkimOutput]] = None,
    effective_vocab: Optional[Iterable[str]] = None,
    *,
    top_tags: int = 5,
    min_count: int = 2,
) -> TrendSummary:
    """Aggregate a window of daily skim outputs into countable signals.

    Args:
        window: 집계 대상 일별 스킴 결과 (순서 무관)
        previous: 직전 창. 없으면 증감·신규 등장은 생략된다.
        effective_vocab: 호출자가 해석한 유효 키워드 어휘. None이면
            창의 effective_keywords 스냅샷 → 관측된 matched_keywords 순으로 폴백.
        top_tags: 태그/신호 축에서 보여줄 상위 개수
        min_count: 태그 기반 축(상위 태그·필터 밖 신호·신규 등장)의 최소 빈도

    Returns:
        집계 결과. 입력이 비면 빈 TrendSummary.
    """
    if not window:
        return TrendSummary()

    papers = _all_papers(window)
    if not papers:
        return TrendSummary(window_dates=_dates(window))

    prev_papers = _all_papers(previous or [])
    has_previous = bool(prev_papers)

    keyword_papers = [p for p in papers if p.matched_keywords]
    keyword_dates = [
        out.date for out in _sorted_window(window) if any(p.matched_keywords for p in out.papers)
    ]

    vocab = _resolve_vocab(window, papers, effective_vocab)

    return TrendSummary(
        window_dates=_dates(window),
        window_papers=len(papers),
        keyword_dates=keyword_dates,
        keyword_papers=len(keyword_papers),
        has_previous=has_previous,
        keywords=_keyword_counts(keyword_papers, prev_papers, has_previous),
        categories=_category_counts(papers, prev_papers, has_previous),
        top_tags=_tag_counts(papers, top_tags, min_count),
        outside_signals=_outside_signals(papers, vocab, top_tags, min_count),
        new_keywords=_new_keywords(keyword_papers, prev_papers, has_previous, top_tags),
        new_tags=_new_tags(papers, prev_papers, has_previous, top_tags, min_count),
        vocabulary_changed=_vocabulary_changed(window),
        representatives=_representatives(window, vocab, top_tags, min_count),
    )


# ---------------------------------------------------------------------------
# window helpers
# ---------------------------------------------------------------------------


def _sorted_window(window: list[DailySkimOutput]) -> list[DailySkimOutput]:
    """Oldest first, so rendered date lists read chronologically."""
    return sorted(window, key=lambda out: out.date)


def _dates(window: list[DailySkimOutput]) -> list[str]:
    return [out.date for out in _sorted_window(window)]


def _all_papers(window: list[DailySkimOutput]) -> list[SkimSummary]:
    return [paper for out in _sorted_window(window) for paper in out.papers]


def _resolve_vocab(
    window: list[DailySkimOutput],
    papers: list[SkimSummary],
    effective_vocab: Optional[Iterable[str]],
) -> set[str]:
    """Pick the vocabulary used to decide what counts as an outside signal.

    Caller-provided vocabulary wins. Otherwise fall back to the stored
    snapshots, and finally to the keywords actually observed in the window -
    older files predate the snapshot field and would otherwise have none.
    """
    if effective_vocab is not None:
        return {kw.lower() for kw in effective_vocab}

    snapshot = {kw.lower() for out in window for kw in (out.effective_keywords or [])}
    if snapshot:
        return snapshot

    return {kw.lower() for paper in papers for kw in paper.matched_keywords}


# ---------------------------------------------------------------------------
# counting axes
# ---------------------------------------------------------------------------


def _with_previous(
    counts: Counter, prev_counts: Counter, has_previous: bool
) -> list[CountDelta]:
    """Order by count desc, name asc; attach previous counts when comparable."""
    return [
        CountDelta(
            name=name,
            count=count,
            previous=prev_counts.get(name, 0) if has_previous else None,
        )
        for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _keyword_counts(
    keyword_papers: list[SkimSummary], prev_papers: list[SkimSummary], has_previous: bool
) -> list[CountDelta]:
    """matched_keywords frequency. Records without keywords never contribute."""
    counts = Counter(kw for paper in keyword_papers for kw in paper.matched_keywords)
    prev = Counter(kw for paper in prev_papers for kw in paper.matched_keywords)
    return _with_previous(counts, prev, has_previous)


def _category_counts(
    papers: list[SkimSummary], prev_papers: list[SkimSummary], has_previous: bool
) -> list[CountDelta]:
    counts = Counter(paper.category for paper in papers)
    prev = Counter(paper.category for paper in prev_papers)
    return _with_previous(counts, prev, has_previous)


def _tag_frequency(papers: list[SkimSummary]) -> Counter:
    """Raw tag counts, lowercased only - no normalisation (out of scope)."""
    return Counter(tag.lower() for paper in papers for tag in paper.tags)


def _tag_counts(papers: list[SkimSummary], top_k: int, min_count: int) -> list[CountDelta]:
    counts = _tag_frequency(papers)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        CountDelta(name=name, count=count)
        for name, count in ranked
        if count >= min_count
    ][:top_k]


def _outside_signals(
    papers: list[SkimSummary], vocab: set[str], top_k: int, min_count: int
) -> list[CountDelta]:
    """Tags that rose without being part of the keyword filter's vocabulary."""
    counts = _tag_frequency(papers)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        CountDelta(name=name, count=count)
        for name, count in ranked
        if count >= min_count and name not in vocab
    ][:top_k]


def _new_keywords(
    keyword_papers: list[SkimSummary],
    prev_papers: list[SkimSummary],
    has_previous: bool,
    top_k: int,
) -> list[CountDelta]:
    """Keywords absent from the previous window. Omitted without a baseline."""
    if not has_previous:
        return []

    seen = {kw for paper in prev_papers for kw in paper.matched_keywords}
    counts = Counter(kw for paper in keyword_papers for kw in paper.matched_keywords)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [CountDelta(name=name, count=count) for name, count in ranked if name not in seen][
        :top_k
    ]


def _new_tags(
    papers: list[SkimSummary],
    prev_papers: list[SkimSummary],
    has_previous: bool,
    top_k: int,
    min_count: int,
) -> list[CountDelta]:
    """Tags absent from the previous window.

    Tags have a long one-off tail (most appear exactly once), so min_count and
    the top-K cap are what keep this from swamping the section.
    """
    if not has_previous:
        return []

    seen = _tag_frequency(prev_papers).keys()
    counts = _tag_frequency(papers)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        CountDelta(name=name, count=count)
        for name, count in ranked
        if count >= min_count and name not in seen
    ][:top_k]


def _vocabulary_changed(window: list[DailySkimOutput]) -> bool:
    """True when the window holds more than one distinct keyword snapshot.

    Files written before the snapshot field existed carry none and are ignored,
    so old-only windows always report no change rather than a false positive.
    """
    snapshots = {
        tuple(sorted(out.effective_keywords)) for out in window if out.effective_keywords
    }
    return len(snapshots) > 1


# ---------------------------------------------------------------------------
# representatives
# ---------------------------------------------------------------------------


def _representatives(
    window: list[DailySkimOutput], vocab: set[str], top_k: int, min_count: int
) -> list[TrendRepresentative]:
    """One paper for the leading keyword and one for the leading outside signal."""
    dated = [(out.date, paper) for out in _sorted_window(window) for paper in out.papers]
    papers = [paper for _, paper in dated]

    result: list[TrendRepresentative] = []

    keywords = _keyword_counts([p for p in papers if p.matched_keywords], [], False)
    if keywords:
        signal = keywords[0].name
        pick = _pick_paper(dated, lambda p: signal in p.matched_keywords)
        if pick is not None:
            result.append(_to_representative(signal, "keyword", pick))

    outside = _outside_signals(papers, vocab, top_k, min_count)
    if outside:
        signal = outside[0].name
        pick = _pick_paper(dated, lambda p: signal in {t.lower() for t in p.tags})
        if pick is not None:
            result.append(_to_representative(signal, "outside", pick))

    return result


def _pick_paper(dated: list[tuple[str, SkimSummary]], predicate) -> Optional[SkimSummary]:
    """Highest interest_score wins; ties go to the most recent date."""
    matches = [(date, paper) for date, paper in dated if predicate(paper)]
    if not matches:
        return None
    return max(matches, key=lambda pair: (pair[1].interest_score, pair[0]))[1]


def _to_representative(signal: str, kind: str, paper: SkimSummary) -> TrendRepresentative:
    return TrendRepresentative(
        signal=signal,
        signal_kind=kind,
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        one_liner=paper.one_liner,
        link=paper.link,
    )
