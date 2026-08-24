"""Benchmark normalisation, key-shape branching, and hint absorption."""

import pytest

analysis = pytest.importorskip("toslack.analysis")
converter = pytest.importorskip("toslack.converter")
enrich = pytest.importorskip("toslack.enrich")
models = pytest.importorskip("toslack.models")

SINGULAR = {
    "dataset": "Game of 24",
    "metrics": ["Success Rate"],
    "baseline_results": {"IO prompt": "7.3%"},
    "proposed_results": {"ToT": "74%"},
}
PLURAL = {
    "dataset": "AIME",
    "metrics": ["Avg@32"],
    "baseline_results": {"GRPO": "61.2"},
    "proposed_results": {"SPADE": "62.8"},
}


def paper() -> models.PaperSummary:
    return models.PaperSummary(
        title="P", arxiv_id="2608.19197", arxiv_url="https://arxiv.org/abs/2608.19197",
        score=12, max_score=15, stars=4, summary="s", problem="p",
        contributions="c", methodology="m", when_to_use="w", when_not_to_use="n",
    )


def enriched(extraction: dict, **detail) -> models.PaperSummary:
    payload = {"extraction": extraction, **detail}
    analysis.normalize_benchmarks(extraction)
    return enrich.enrich_papers([paper()], loader=lambda _: payload)[0]


# --- singular / plural fallback -------------------------------------------


def test_benchmark_singular_and_plural_both_read():
    """Legacy singular and current plural fields both reach the renderer."""
    assert enriched({"benchmark": SINGULAR}).benchmarks[0].dataset == "Game of 24"
    assert enriched({"benchmarks": [PLURAL]}).benchmarks[0].dataset == "AIME"


def test_normalization_preserves_the_legacy_key():
    """The web detail view reads `benchmark` directly; removing it blanks the table."""
    extraction = {"benchmark": SINGULAR}
    analysis.normalize_benchmarks(extraction)

    assert extraction["benchmark"] == SINGULAR
    assert extraction["benchmarks"] == [SINGULAR]


def test_normalization_does_not_duplicate_when_both_present():
    extraction = {"benchmarks": [SINGULAR], "benchmark": SINGULAR}
    analysis.normalize_benchmarks(extraction)

    assert extraction["benchmarks"] == [SINGULAR]


def test_benchmark_display_is_capped_at_two_with_a_count():
    """Papers carry up to seven benchmarks; the message shows two and says so."""
    many = [dict(PLURAL, dataset=f"D{i}") for i in range(7)]
    enriched_paper = enriched({"benchmarks": many})

    assert len(enriched_paper.benchmarks) == 2
    assert enriched_paper.benchmark_total == 7
    assert "(7개 중 2개)" in converter._paper_body_text(enriched_paper)


# --- key shape branching --------------------------------------------------


def test_benchmark_key_intersection_branch():
    """Shared keys are metric names, so baseline and proposed pair up directly."""
    metric_keyed = {
        "dataset": "CDs",
        "metrics": ["NDCG@5"],
        "baseline_results": {"NDCG@5": "0.0148", "NDCG@10": "0.0182"},
        "proposed_results": {"NDCG@5": "0.0198", "NDCG@10": "0.0282"},
    }
    body = converter._paper_body_text(enriched({"benchmarks": [metric_keyed]}))

    assert "NDCG@5 0.0148→0.0198" in body
    assert "NDCG@10 0.0182→0.0282" in body


def test_benchmark_without_key_intersection_lists_both_sides():
    """Disjoint keys are system names; pairing them would invent a comparison."""
    system_keyed = {
        "dataset": "SWE-Bench-Pro",
        "metrics": ["Pass@1"],
        "baseline_results": {"base": "48.7", "s1": "49.3"},
        "proposed_results": {"ours": "52.0"},
    }
    body = converter._paper_body_text(enriched({"benchmarks": [system_keyed]}))

    assert "base 48.7 / s1 49.3 → *ours 52.0*" in body
    assert "→*" not in body.replace("→ *", "")


def test_benchmark_absent_section_omitted():
    """Two of 33 papers have no benchmark at all - no header, no placeholder."""
    body = converter._paper_body_text(enriched({"benchmarks": []}))

    assert "📊" not in body
    assert "벤치마크" not in body


# --- hint absorption ------------------------------------------------------


def _detail(hint: str, new_approach: str = "adaptive environment generation"):
    return {
        "delta": {"core_deltas": [
            {"axis": "환경 생성 방식", "old_approach": "fixed", "new_approach": new_approach},
        ]},
        "extraction": {"benchmarks": [], "method_components": [
            {"name": "Environment Designer", "description": new_approach,
             "implementation_hint": hint},
        ]},
    }


def test_hint_is_absorbed_into_the_delta_line():
    enriched_paper = enrich.enrich_papers(
        [paper()], loader=lambda _: _detail("힌트 기반 후회 신호를 사용하여 환경을 생성")
    )[0]

    assert enriched_paper.delta_axes[0].hint == "힌트 기반 후회 신호를 사용하여 환경을 생성"
    body = converter._paper_body_text(enriched_paper)
    assert "_구현: 힌트 기반 후회 신호를 사용하여 환경을 생성_" in body


def test_hint_below_threshold_is_omitted():
    """An unrelated component prints nothing rather than a wrong pairing."""
    detail = _detail("blah", new_approach="적응형 환경 생성")
    detail["extraction"]["method_components"] = [
        {"name": "zzz", "description": "qqq", "implementation_hint": "wwwww"},
    ]
    enriched_paper = enrich.enrich_papers([paper()], loader=lambda _: detail)[0]

    assert enriched_paper.delta_axes[0].hint is None
    assert "_구현:" not in converter._paper_body_text(enriched_paper)


def test_missing_implementation_hint_still_renders_the_axis():
    """A third of papers carry no hints at all; the delta line stands alone."""
    detail = _detail("x")
    detail["extraction"]["method_components"][0]["implementation_hint"] = None
    enriched_paper = enrich.enrich_papers([paper()], loader=lambda _: detail)[0]

    assert enriched_paper.delta_axes[0].hint is None
    assert "*환경 생성 방식*" in converter._paper_body_text(enriched_paper)


def test_english_hint_uses_the_longer_budget():
    """Clipping Latin script at the Korean budget lands mid-word."""
    english = ("Operates through a four-stage pipeline: World Model Pre-training, "
               "Policy Training with World Model Conditioning, Rollout Collection.")
    korean = ("힌트 유무에 따른 성과 차이를 기반으로 후회 신호를 계산하며 "
              "환경 생성기를 갱신하고 반복한다")

    assert 46 < len(enrich.clip_hint(english)) <= 80
    assert len(enrich.clip_hint(korean)) <= 47
