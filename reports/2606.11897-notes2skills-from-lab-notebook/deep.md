# Notes2Skills: From Lab Notebooks to Certainty-Aware Scientific Agent Skills

**날짜**: 2026-06-24
**arXiv**: [2606.11897](https://arxiv.org/abs/2606.11897)
**PDF**: [다운로드](https://arxiv.org/pdf/2606.11897.pdf)
**점수**: 11/15 (읽어볼 만함)

## 한 줄 요약
이 논문은 실험 노트북을 AI 에이전트가 활용할 수 있는 검증 가능한 스킬로 변환하는 문제에 대해 Epistemic Directive Extraction, MetaSkill Compilation, Dual-Evidence Gate 접근법을 제안한다.

## 왜 이 논문인가?
총점: 11/15

🎯 점수 상세:
  - Practicality (실용성): 4/5
  - Codeability (구현 가능성): 3/5
  - Signal (신뢰도): 4/5

💡 평가 근거:
이 논문은 실험 노트북을 AI 에이전트가 활용할 수 있는 검증 가능한 스킬로 변환하는 문제를 다루고 있으며, 제안된 방법들이 실제 문제 해결에 기여할 가능성이 높다. 그러나 구현의 복잡성으로 인해 즉시 적용 가능성은 다소 제한적이다.

**주요 강점**: Epistemic Directive Extraction, MetaSkill Compilation, Dual-Evidence Gate 접근법을 통해 실험 노트북의 활용 가능성을 높인다.

**주요 우려**: 구현 과정에서의 복잡성과 실제 적용 시의 한계

## 문제 정의
실험 노트북을 AI 에이전트가 활용할 수 있는 검증 가능한 스킬로 변환하는 문제를 해결하고자 한다.

**기존 방법의 한계**: 실험 노트북은 관찰, 해석, 제안이 혼합되어 있어 AI 에이전트가 불확실한 과학적 판단을 확정된 결론으로 오인할 수 있다.

## 핵심 기여 (Delta)
### Delta 1: 지침 추출
- **기존**: 해당 영역에 특화된 방법 없음
- **변경**: Epistemic Directive Extraction (EDE)을 통해 노트북의 각 문장을 FACT, JUDGMENT, SUGGESTION으로 라벨링하여 지침으로 식별
- **이유**: 노트북의 내용을 구조화하여 후속 분석에 활용할 수 있도록 지원함 

### Delta 2: 스킬 컴파일
- **기존**: 해당 영역에 특화된 방법 없음
- **변경**: 라벨링된 지침을 에이전트가 로드할 수 있는 Markdown 스킬로 컴파일하는 MetaSkill Compilation
- **이유**: 에이전트가 직접 활용할 수 있는 형태로 지침을 변환하여 실용성을 높임 

### Delta 3: 행동 결정
- **기존**: 해당 영역에 특화된 방법 없음
- **변경**: Dual-Evidence Gate를 통해 LLM의 제안과 캡슐화된 지침을 비교하여 행동을 결정
- **이유**: LLM의 제안과 기존 지침을 비교하여 더 신뢰할 수 있는 행동 결정을 지원함 

## 방법론
**Epistemic Directive Extraction (EDE)**
노트북의 각 문장을 FACT, JUDGMENT, SUGGESTION으로 라벨링하여 후속 분석을 위한 지침으로 식별한다.
- **입력**: 노트북 세그먼트
- **출력**: 지침과 그 확실성 라벨
- **구현 힌트**: 언어적 단서를 기반으로 라벨을 할당한다.
- **역할**: novel (Evidence: §Task Formalization)

**MetaSkill Compilation**
라벨링된 지침을 에이전트가 로드할 수 있는 Markdown 스킬로 컴파일한다.
- **입력**: 라벨링된 지침
- **출력**: MetaSkill Markdown 문서
- **구현 힌트**: 각 지침은 그 확실성 라벨과 출처 링크를 포함한다.
- **역할**: novel (Evidence: §Task Formalization)

**Dual-Evidence Gate**
LLM의 제안과 캡슐화된 지침을 비교하여 강력한 행동을 허용할지 결정한다.
- **입력**: LLM의 제안, 지침 캡슐, 파일의 신호 증거
- **출력**: Authorize, Veto, Substitute, Abstain 중 하나
- **구현 힌트**: 캡슐의 확실성, 승인, 후보 행동을 검사한다.
- **역할**: novel (Evidence: §The Executor)

## 트레이드오프
명시된 트레이드오프 없음

## 언제 사용해야 하는가?
✅ **사용 권장**: 실험 노트북의 내용을 AI 에이전트가 활용할 수 있는 형태로 변환하고자 할 때

❌ **사용 비권장**: 기존에 충분히 구조화된 데이터가 이미 있는 경우

## 주요 클레임
### 방법론 클레임
- Notes2Skills는 실험 노트북을 에이전트가 로드할 수 있는 스킬로 변환하는 최초의 접근법이다. (Evidence: §Introduction)
- Notes2Skills는 실험 노트북의 확실성 보존이 AI 에이전트의 안전한 사용을 위한 핵심 요소임을 보여준다. (Evidence: §Introduction)
### 결과 클레임
- Notes2Skills는 불확실한 노트를 확정된 지침으로 오인하지 않으며, 확정된 지침을 잃지 않는다. (Evidence: §Introduction)
- Notes2Skills는 세 가지 코퍼스에서 461개의 주석 세그먼트를 검증한다. (Evidence: §Task Formalization)
- Notes2Skills는 불확실성 세션에서 불확실한 판독값을 확정된 행동으로 세탁하는 것을 피한다. (Evidence: §Exp 3: Downstream Skill Loading)

---
*Generated at 2026-06-24 00:08:41*
