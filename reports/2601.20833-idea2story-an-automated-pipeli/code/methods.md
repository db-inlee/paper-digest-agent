# 2601.20833 - GitHub Method Analysis

**Repository**: [https://github.com/AgentAlphaAGI/Idea2Paper](https://github.com/AgentAlphaAGI/Idea2Paper)
**Language**: Python

## 프로젝트 구조

이 프로젝트는 사용자의 연구 아이디어를 기반으로 과학적 내러티브를 자동으로 생성하는 파이프라인을 제공합니다. 주요 모듈은 아이디어를 구조화된 스토리로 변환하는 'Idea2StoryPipeline'과 지식 그래프를 구축하는 'Offline Knowledge Construction'으로 구성됩니다.

## 방법론 구현

### 1. Offline Knowledge Construction

**설명**: 기존 과학 문헌에서 재사용 가능한 방법론적 기초를 구축하는 단계로, 피어 리뷰된 논문을 수집하고, 핵심 방법론적 기여를 추출하여 구조화된 지식 그래프로 조직합니다.

**위치**: `Paper-KG-Pipeline/scripts/idea2story_pipeline.py`
**함수/클래스**: `Idea2StoryPipeline`

```python
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
```

**코드 설명**: 이 코드는 지식 그래프를 구축하기 위해 필요한 인덱스를 준비하는 과정입니다. 'ensure_required_indexes' 함수는 'novelty index'와 'recall index'의 유효성을 검사하고, 필요시 인덱스를 생성합니다. 'validate_novelty_index' 함수를 통해 인덱스의 상태를 확인하고, 문제가 있을 경우 'build_novelty_index'를 호출하여 인덱스를 생성합니다. 이 과정에서 로그를 기록하여 진행 상황을 추적합니다.

### 2. Online Research Generation

**설명**: 사용자가 제공한 연구 아이디어를 기반으로 지식 그래프에서 관련 연구 패턴을 검색하고, 이를 구체적인 연구 방향으로 구성합니다.

**위치**: `frontend/server/app.py`
**함수/클래스**: `Handler`

```python
def _handle_run(self):
    payload = _read_json(self)
    if not payload or "idea" not in payload:
        return _json_response(self, {"ok": False, "error": "invalid payload"}, status=400)

    idea = payload.get("idea", "").strip()
    llm = payload.get("llm", {}) or {}
    toggles = payload.get("toggles", {}) or {}

    ui_run_id = f"ui_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    env = os.environ.copy()
    api_key = llm.get("api_key")
    if api_key:
        env["SILICONFLOW_API_KEY"] = api_key
    if llm.get("api_url"):
        env["LLM_API_URL"] = llm.get("api_url")
    if llm.get("model"):
        env["LLM_MODEL"] = llm.get("model")

    if "novelty" in toggles:
        env["I2P_NOVELTY_ENABLE"] = "1" if toggles.get("novelty") else "0"
    if "verification" in toggles:
        env["I2P_VERIFICATION_ENABLE"] = "1" if toggles.get("verification") else "0"

    env["I2P_ENABLE_LOGGING"] = "1"
    env["I2P_RESULTS_ENABLE"] = "1"

    cmd = ["python", str(PIPELINE_SCRIPT), idea]
    try:
        popen = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        registry.create(ui_run_id, popen, _safe_env_meta(env))
        return _json_response(self, {"ok": True, "ui_run_id": ui_run_id})
    except Exception as e:
        return _json_response(self, {"ok": False, "error": str(e)}, status=500)
```

**코드 설명**: 이 코드는 사용자가 제공한 연구 아이디어를 기반으로 파이프라인을 실행하는 HTTP 요청을 처리합니다. '_handle_run' 메서드는 클라이언트로부터 아이디어를 받아 환경 변수를 설정하고, 'subprocess.Popen'을 통해 'idea2story_pipeline.py' 스크립트를 실행합니다. 실행 결과는 'RunRegistry'에 저장되어 추후 조회할 수 있습니다.
