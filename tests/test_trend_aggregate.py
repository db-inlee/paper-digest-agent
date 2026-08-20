"""Trend aggregation is deterministic and degrades quietly on thin data."""

from rtc.schemas.skim import DailySkimOutput, SkimSummary
from rtc.trend import aggregate_trends


def paper(
    arxiv_id: str,
    *,
    keywords: list[str] | None = None,
    tags: list[str] | None = None,
    category: str = "agent",
    score: int = 4,
) -> SkimSummary:
    return SkimSummary(
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        one_liner=f"summary {arxiv_id}",
        tags=tags or [],
        interest_score=score,
        interest_reason="reason",
        category=category,
        link=f"https://arxiv.org/abs/{arxiv_id}",
        matched_keywords=keywords if keywords is not None else ["agent"],
    )


def day(date: str, papers: list[SkimSummary], vocab: list[str] | None = None) -> DailySkimOutput:
    return DailySkimOutput(
        date=date,
        total_collected=len(papers),
        total_skimmed=len(papers),
        papers=papers,
        effective_keywords=vocab or [],
    )


def counts(items) -> dict[str, int]:
    return {item.name: item.count for item in items}


# --- keyword axis ----------------------------------------------------------


def test_keyword_counts_skip_records_without_keywords():
    """Legacy records with no matched_keywords must not distort the counts."""
    window = [
        day("2026-01-01", [paper("1", keywords=["agent", "RAG"]), paper("2", keywords=[])]),
        day("2026-01-02", [paper("3", keywords=["agent"])]),
    ]

    summary = aggregate_trends(window)

    assert counts(summary.keywords) == {"agent": 2, "RAG": 1}
    assert summary.window_papers == 3
    assert summary.keyword_papers == 2
    assert summary.keyword_dates == ["2026-01-01", "2026-01-02"]
    assert summary.window_dates == ["2026-01-01", "2026-01-02"]


def test_category_counts_cover_every_paper():
    """Category counts use the whole window, keywords or not."""
    window = [
        day(
            "2026-01-01",
            [
                paper("1", category="agent"),
                paper("2", category="agent", keywords=[]),
                paper("3", category="rag"),
            ],
        )
    ]

    summary = aggregate_trends(window)

    assert counts(summary.categories) == {"agent": 2, "rag": 1}


# --- deltas ----------------------------------------------------------------


def test_deltas_are_omitted_without_a_previous_window():
    window = [day("2026-01-02", [paper("1", keywords=["agent"])])]

    summary = aggregate_trends(window, previous=[])

    assert summary.has_previous is False
    assert all(item.previous is None and item.delta is None for item in summary.keywords)


def test_deltas_appear_once_a_previous_window_exists():
    window = [day("2026-01-02", [paper("1", keywords=["agent", "RAG"])])]
    previous = [
        day("2026-01-01", [paper("9", keywords=["agent"]), paper("8", keywords=["agent"])])
    ]

    summary = aggregate_trends(window, previous)
    by_name = {item.name: item for item in summary.keywords}

    assert summary.has_previous is True
    assert by_name["agent"].delta == -1
    assert by_name["RAG"].delta == 1


# --- tag axis: min_count and caps -----------------------------------------


def test_outside_signals_exclude_vocabulary_and_respect_min_count():
    """Only tags outside the vocabulary, seen at least min_count times."""
    window = [
        day(
            "2026-01-01",
            [
                paper("1", tags=["reinforcement learning", "agent"]),
                paper("2", tags=["reinforcement learning", "agent"]),
                paper("3", tags=["one-off tag"]),
            ],
        )
    ]

    summary = aggregate_trends(window, effective_vocab=["agent"], min_count=2)

    assert counts(summary.outside_signals) == {"reinforcement learning": 2}
    # "agent" is in the vocabulary, "one-off tag" is below min_count.
    assert counts(summary.top_tags) == {"reinforcement learning": 2, "agent": 2}


def test_top_tags_are_capped():
    papers = [paper(str(i), tags=[f"tag{i}", f"tag{i}"]) for i in range(10)]
    summary = aggregate_trends([day("2026-01-01", papers)], top_tags=3, min_count=2)

    assert len(summary.top_tags) == 3


def test_new_signals_are_omitted_without_history():
    """No baseline means nothing can be called new."""
    window = [day("2026-01-01", [paper("1", keywords=["agent"], tags=["rl", "rl"])])]

    summary = aggregate_trends(window)

    assert summary.new_keywords == []
    assert summary.new_tags == []


def test_new_tags_respect_min_count_and_cap():
    """The one-off tail is exactly what min_count and the cap exist to hold back."""
    fresh = [
        paper("1", tags=["alpha", "alpha", "solo"]),
        paper("2", tags=["beta", "beta", "another solo"]),
        paper("3", tags=["gamma", "gamma"]),
    ]
    window = [day("2026-01-02", fresh)]
    previous = [day("2026-01-01", [paper("9", tags=["old"])])]

    summary = aggregate_trends(window, previous, top_tags=2, min_count=2)

    names = [item.name for item in summary.new_tags]
    assert len(names) == 2
    assert "solo" not in names and "another solo" not in names


def test_new_keywords_are_those_absent_from_the_previous_window():
    window = [day("2026-01-02", [paper("1", keywords=["agent", "RAG"])])]
    previous = [day("2026-01-01", [paper("9", keywords=["agent"])])]

    summary = aggregate_trends(window, previous)

    assert counts(summary.new_keywords) == {"RAG": 1}


# --- vocabulary resolution -------------------------------------------------


def test_legacy_window_without_snapshot_falls_back_to_observed_keywords():
    """Old files carry no snapshot, so observed keywords define the vocabulary."""
    window = [
        day("2026-01-01", [paper("1", keywords=["agent"], tags=["agent", "agent", "rl", "rl"])])
    ]

    summary = aggregate_trends(window)

    assert counts(summary.outside_signals) == {"rl": 2}


def test_snapshot_defines_the_vocabulary_when_present():
    window = [
        day(
            "2026-01-01",
            [paper("1", keywords=["agent"], tags=["rl", "rl", "agent", "agent"])],
            vocab=["rl"],
        )
    ]

    summary = aggregate_trends(window)

    assert counts(summary.outside_signals) == {"agent": 2}


def test_explicit_vocabulary_overrides_the_snapshot():
    window = [
        day("2026-01-01", [paper("1", tags=["rl", "rl", "agent", "agent"])], vocab=["rl"])
    ]

    summary = aggregate_trends(window, effective_vocab=["agent"])

    assert counts(summary.outside_signals) == {"rl": 2}


def test_vocabulary_change_detection():
    same = [
        day("2026-01-01", [paper("1")], vocab=["a"]),
        day("2026-01-02", [paper("2")], vocab=["a"]),
    ]
    changed = [
        day("2026-01-01", [paper("1")], vocab=["a"]),
        day("2026-01-02", [paper("2")], vocab=["a", "b"]),
    ]
    legacy = [day("2026-01-01", [paper("1")]), day("2026-01-02", [paper("2")])]

    assert aggregate_trends(same).vocabulary_changed is False
    assert aggregate_trends(changed).vocabulary_changed is True
    # Files predating the snapshot field must not read as a change.
    assert aggregate_trends(legacy).vocabulary_changed is False


# --- representatives and empty input ---------------------------------------


def test_representative_prefers_score_then_recency():
    window = [
        day("2026-01-01", [paper("old-high", keywords=["agent"], score=5)]),
        day("2026-01-02", [paper("new-high", keywords=["agent"], score=5)]),
        day("2026-01-03", [paper("new-low", keywords=["agent"], score=3)]),
    ]

    summary = aggregate_trends(window)
    keyword_rep = [r for r in summary.representatives if r.signal_kind == "keyword"][0]

    assert keyword_rep.arxiv_id == "new-high"


def test_empty_and_paperless_windows_do_not_crash():
    assert aggregate_trends([]).is_empty is True

    paperless = aggregate_trends([day("2026-01-01", [])])
    assert paperless.is_empty is True
    assert paperless.keywords == []
