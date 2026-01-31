"""
Offline Knowledge Construction

원본: https://github.com/AgentAlphaAGI/Idea2Paper
파일: Paper-KG-Pipeline/scripts/idea2story_pipeline.py

기존 과학 문헌에서 재사용 가능한 방법론적 기초를 구축하는 단계로, 피어 리뷰된 논문을 수집하고, 핵심 방법론적 기여를 추출하여 구조화된 지식 그래프로 조직합니다.

코드 설명:
이 코드는 지식 그래프를 구축하기 위해 필요한 인덱스를 준비하는 과정입니다. 'ensure_required_indexes' 함수는 'novelty index'와 'recall index'의 유효성을 검사하고, 필요시 인덱스를 생성합니다. 'validate_novelty_index' 함수를 통해 인덱스의 상태를 확인하고, 문제가 있을 경우 'build_novelty_index'를 호출하여 인덱스를 생성합니다. 이 과정에서 로그를 기록하여 진행 상황을 추적합니다.
"""

def ensure_required_indexes(logger=None):
    if not PipelineConfig.INDEX_AUTO_PREPARE:
        return

    _log_event(logger, "index_preflight_start", {
        "novelty_enable": NOVELTY_ENABLE,
        "recall_use_offline_index": PipelineConfig.RECALL_USE_OFFLINE_INDEX,
        "allow_build": PipelineConfig.INDEX_ALLOW_BUILD,
    })

    if NOVELTY_ENABLE:
        nodes_paper_path = OUTPUT_DIR / "nodes_paper.json"
        status = validate_novelty_index(NOVELTY_INDEX_DIR, nodes_paper_path, EMBEDDING_MODEL)
        if status.get("ok"):
            _log_event(logger, "index_preflight_ok", {"index": "novelty", "status": status})
        else:
            _log_event(logger, "index_preflight_failed", {"index": "novelty", "status": status})
            if PipelineConfig.INDEX_ALLOW_BUILD:
                lock_path = NOVELTY_INDEX_DIR / ".build.lock"
                _log_event(logger, "index_preflight_build_start", {
                    "index": "novelty",
                    "index_dir": str(NOVELTY_INDEX_DIR),
                })
                with acquire_lock(lock_path):
                    build_novelty_index(
                        index_dir=NOVELTY_INDEX_DIR,
                        batch_size=NOVELTY_INDEX_BUILD_BATCH_SIZE,
                        resume=NOVELTY_INDEX_BUILD_RESUME,
                        max_retries=NOVELTY_INDEX_BUILD_MAX_RETRIES,
                        sleep_sec=NOVELTY_INDEX_BUILD_SLEEP_SEC,
                        force_rebuild=False,
                        logger=logger,
                    )
                status = validate_novelty_index(NOVELTY_INDEX_DIR, nodes_paper_path, EMBEDDING_MODEL)
                _log_event(logger, "index_preflight_build_done", {"index": "novelty", "status": status})
                if not status.get("ok") and NOVELTY_REQUIRE_EMBEDDING:
                    raise RuntimeError("Novelty index build failed or incomplete. Please run build_novelty_index.py manually.")
            else:
                if NOVELTY_REQUIRE_EMBEDDING:
                    raise RuntimeError(
                        "Novelty index missing or mismatched. Please run: "
                        "python Paper-KG-Pipeline/scripts/tools/build_novelty_index.py --resume"
                    )
                print("⚠️ Novelty index missing/mismatch. Continuing because require_embedding=false.")