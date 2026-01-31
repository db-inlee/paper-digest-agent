"""
Online Research Generation

원본: https://github.com/AgentAlphaAGI/Idea2Paper
파일: frontend/server/app.py

사용자가 제공한 연구 아이디어를 기반으로 지식 그래프에서 관련 연구 패턴을 검색하고, 이를 구체적인 연구 방향으로 구성합니다.

코드 설명:
이 코드는 사용자가 제공한 연구 아이디어를 기반으로 파이프라인을 실행하는 HTTP 요청을 처리합니다. '_handle_run' 메서드는 클라이언트로부터 아이디어를 받아 환경 변수를 설정하고, 'subprocess.Popen'을 통해 'idea2story_pipeline.py' 스크립트를 실행합니다. 실행 결과는 'RunRegistry'에 저장되어 추후 조회할 수 있습니다.
"""

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