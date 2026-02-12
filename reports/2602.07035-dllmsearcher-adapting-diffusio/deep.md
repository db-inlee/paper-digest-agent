# DLLM-Searcher: Adapting Diffusion Large Language Model for Search Agents

**날짜**: 2026-02-11
**arXiv**: [2602.07035](https://arxiv.org/abs/2602.07035)
**PDF**: [다운로드](https://arxiv.org/pdf/2602.07035.pdf)
**점수**: 11/15 (읽어볼 만함)

## 한 줄 요약
이 논문은 기존의 ReARTeR 및 R1Searcher의 구조적 한계를 Agentic SFT, Agentic VRPO, P-ReAct를 통해 개선한다

## 왜 이 논문인가?
총점: 11/15

🎯 점수 상세:
  - Practicality (실용성): 4/5
  - Codeability (구현 가능성): 3/5
  - Signal (신뢰도): 4/5

💡 평가 근거:
이 논문은 기존 dLLM의 한계를 개선하기 위한 다양한 방법론을 제안하고 있으며, 실질적인 문제 해결 가능성이 높다. 특히, 도구 호출 능력과 정보 검색 행동을 강화하는 접근 방식은 실제 응용에 유용할 것으로 보인다.

**주요 강점**: 기존 모델의 구조적 한계를 개선하기 위한 다양한 방법론을 제안하고, 실질적인 문제 해결 가능성을 높인다.

**주요 우려**: 구현의 복잡성이 다소 존재할 수 있으며, 실제 환경에서의 성능 검증이 필요하다.

## 문제 정의
기존의 dLLM은 에이전트 시나리오에서 약한 추론 및 도구 호출 능력을 보이며, 이는 실질적인 배포를 방해합니다. 또한 ReAct 에이전트 패러다임 하에서의 직렬 실행으로 인해 심각한 지연 문제가 발생합니다.

**기존 방법의 한계**: 기존 dLLM은 에이전트 시나리오에서 약한 추론 및 도구 호출 능력을 보이며, 이는 실질적인 배포를 방해합니다.

## 핵심 기여 (Delta)
### Delta 1: 추론 및 도구 호출 능력
- **기존**: 기존 dLLM은 에이전트 시나리오에서 약한 추론 및 도구 호출 능력을 보임
- **변경**: Agentic Supervised Fine-Tuning (Agentic SFT)을 통해 도구 호출 형식 준수 능력을 향상시킴
- **이유**: 대규모 블록 생성 하에서 정보 검색과 추론을 결합하는 초기 능력을 획득하도록 돕기 때문 

### Delta 2: 정보 검색 행동
- **기존**: 기존 모델은 정보 검색 행동이 강력하지 않음
- **변경**: Agentic Variance-Reduced Preference Optimization (Agentic VRPO)을 통해 강력한 정보 검색 행동을 강화
- **이유**: SFT 모델에서 시작하여, 올바른 경로로 모델을 정렬하여 정보 검색 행동을 강화하기 때문 

### Delta 3: 지연 문제
- **기존**: ReAct 에이전트 패러다임 하에서의 직렬 실행으로 인해 심각한 지연 문제가 발생
- **변경**: Parallel-Reasoning and Acting (P-ReAct)을 통해 도구 호출 지시를 우선적으로 디코딩
- **이유**: 도구 실행 중에도 모델이 계속 생각할 수 있도록 하여 지연 문제를 완화 

## 방법론
### Agentic Supervised Fine-Tuning (Agentic SFT)
dLLM의 도구 호출 형식 준수 능력을 향상시키고, 대규모 블록 생성 하에서 정보 검색과 추론을 결합하는 초기 능력을 획득하도록 돕습니다.
- **입력**: query Q, teacher trajectory Hteacher
- **출력**: improved dLLM with better tool-call format adherence (Evidence: §4.2 Agentic SFT)

### Agentic Variance-Reduced Preference Optimization (Agentic VRPO)
SFT 모델에서 시작하여, 올바른 경로로 모델을 정렬하여 강력한 정보 검색 행동을 강화합니다.
- **입력**: query Q, winner trajectory Hw, loser trajectory Hl
- **출력**: further refined dLLM with enhanced reasoning and retrieval performance (Evidence: §4.3 Agentic VRPO)

### Parallel-Reasoning and Acting (P-ReAct)
도구 호출 지시를 우선적으로 디코딩하도록 모델을 안내하여, 도구 실행 중에도 모델이 계속 생각할 수 있도록 합니다.
- **입력**: query Q
- **출력**: prioritized tool-call decoding (Evidence: §4.4 P-ReAct Agent Paradigm)

## 트레이드오프
- **복잡성**
  - 이점: 강력한 정보 검색 및 추론 능력
  - 비용: 모델의 복잡성이 증가
  - 수용 가능 조건: 복잡성을 감수하고서라도 성능 향상이 필요한 경우

## 언제 사용해야 하는가?
✅ **사용 권장**: 에이전트 시나리오에서 강력한 추론 및 도구 호출 능력이 필요한 경우

❌ **사용 비권장**: 모델의 복잡성이 중요한 제약 조건인 경우

## 주요 클레임
### 방법론 클레임
- DLLM-Searcher는 dLLM의 정보 검색 및 추론 능력을 향상시킵니다. (Evidence: §Abstract)
### 결과 클레임
- DLLM-Searcher는 ReAct 패러다임에 비해 약 15%의 추론 가속을 제공합니다. (Evidence: §Abstract)
### 비교 클레임
- DLLM-Searcher는 주류 LLM 기반 검색 에이전트와 비교할 만한 성능을 달성합니다. (Evidence: §Abstract)
### 한계 클레임
- 기존 dLLM은 에이전트 시나리오에서 약한 추론 및 도구 호출 능력을 보입니다. (Evidence: §Introduction)

---
*Generated at 2026-02-11 22:05:39*
