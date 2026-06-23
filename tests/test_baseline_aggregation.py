"""Tests for read-time baseline aggregation + confidence labels."""

from rtc.obsidian.aggregate import aggregate_baselines, label_distribution, label_key


def test_label_key_structural_signals():
    # @<digit> -> metric
    assert label_key("NDCG@5", "0.0148") == "metric"
    assert label_key("Recall@10", "0.0391") == "metric"
    # clean numeric score, proper-noun key -> model
    assert label_key("GPT-5.2", "57.1") == "model"
    assert label_key("Gemma3-4B-IT", "33.33, 40.65") == "model"
    # % on a model-looking key -> uncertain
    assert label_key("SigLIP2", "50.1%") == "uncertain"
    # % on a plain-word key -> metric
    assert label_key("Sequence accuracy", "16.94%") == "metric"
    # non-standard value (colon/text) -> uncertain, regardless of proper-noun
    assert label_key("cudaLLM", "Level 1: Exec 46.0, fast1/fast") == "uncertain"


def test_aggregate_promotes_fake_zero():
    # baselines empty but benchmark has a model comparison (16122-like)
    ext = {
        "baselines": [],
        "benchmarks": [{"baseline_results": {"Gemma3-4B-IT": "33.33, 40.65"}}],
    }
    agg = aggregate_baselines(ext)
    names = {it["name"]: it for it in agg}
    assert "Gemma3-4B-IT" in names
    assert names["Gemma3-4B-IT"]["label"] == "model"
    assert names["Gemma3-4B-IT"]["source"] == "benchmark"


def test_combo_keeps_original_plus_uncertain_fragments():
    ext = {
        "baselines": [],
        "benchmarks": [{"baseline_results": {"Qwen2.5-Omni-7B + AVCD": "50.0"}}],
    }
    agg = aggregate_baselines(ext)
    names = {it["name"]: it["label"] for it in agg}
    # original combo kept (not replaced)
    assert "Qwen2.5-Omni-7B + AVCD" in names
    # fragments added as bonus, uncertain
    assert names["Qwen2.5-Omni-7B"] == "uncertain"
    assert names["AVCD"] == "uncertain"


def test_dedup_model_wins():
    # ConvS2S appears both in baselines[] and baseline_results -> single, model
    ext = {
        "baselines": [{"name": "ConvS2S", "description": "d"}],
        "benchmarks": [{"baseline_results": {"ConvS2S": "25.0", "MoE": "26.0"}}],
    }
    agg = aggregate_baselines(ext)
    convs2s = [it for it in agg if it["name"] == "ConvS2S"]
    assert len(convs2s) == 1
    assert convs2s[0]["label"] == "model"
    assert convs2s[0]["source"] == "baselines"
    # MoE promoted as model
    assert any(it["name"] == "MoE" and it["label"] == "model" for it in agg)


def test_metric_leak_not_dropped():
    ext = {
        "baselines": [],
        "benchmarks": [{"baseline_results": {"NDCG@5": "0.01", "Recall@10": "0.03"}}],
    }
    agg = aggregate_baselines(ext)
    # nothing dropped: both kept, labeled metric
    assert {it["name"] for it in agg} == {"NDCG@5", "Recall@10"}
    assert all(it["label"] == "metric" for it in agg)


def test_distribution_counts():
    items = [
        {"name": "a", "label": "model", "source": "x"},
        {"name": "b", "label": "metric", "source": "x"},
        {"name": "c", "label": "model", "source": "x"},
    ]
    assert label_distribution(items) == {"model": 2, "metric": 1}
