# Tree of Thoughts: Deliberate Problem Solving with Large Language Models

**날짜**: 2026-02-13
**arXiv**: [2305.10601](https://arxiv.org/abs/2305.10601)
**PDF**: [다운로드](https://arxiv.org/pdf/2305.10601.pdf)
**점수**: 11/15 (읽어볼 만함)

## 한 줄 요약
이 논문은 기존의 Chain-of-Thought (CoT) 및 Self-consistency with CoT (CoT-SC)의 구조적 한계를 Tree of Thoughts 프레임워크를 통해 개선한다

## 왜 이 논문인가?
총점: 11/15

🎯 점수 상세:
  - Practicality (실용성): 4/5
  - Codeability (구현 가능성): 3/5
  - Signal (신뢰도): 4/5

💡 평가 근거:
Tree of Thoughts 프레임워크는 기존의 문제 해결 방식의 한계를 개선하고, 다양한 탐색 알고리즘을 적용할 수 있는 가능성을 보여준다. 이는 실제 문제 해결에 기여할 수 있는 방향성을 제시한다.

**주요 강점**: 기존의 Chain-of-Thought 방식의 한계를 극복하고, 문제 해결을 위한 새로운 접근 방식을 제안한다.

**주요 우려**: 탐색 알고리즘의 효과성과 실제 적용 가능성에 대한 검증이 필요할 수 있다.

## 문제 정의
기존의 언어 모델은 토큰 수준의 좌에서 우로의 결정 과정에 국한되어 있어 탐색이나 전략적 예측이 필요한 문제에서 한계를 가집니다. 이를 해결하기 위해 'Tree of Thoughts'라는 새로운 프레임워크를 제안합니다.

**기존 방법의 한계**: 기존 방법들은 문제 해결 과정에서 다양한 경로를 탐색하지 않으며, 계획, 예측, 또는 백트래킹을 포함하지 않습니다.

## 핵심 기여 (Delta)
### Delta 1: 문제 해결 프레임워크
- **기존**: Chain-of-Thought (CoT) 및 Self-consistency with CoT (CoT-SC) 방식은 각 사고 단계 내에서 지역 탐색이 없고, 출력 공간이 제한된 경우에만 효과적임
- **변경**: Tree of Thoughts 프레임워크는 문제를 중간 사고 단계로 분해하고, 다양한 탐색 알고리즘을 트리 구조에 적용하여 문제 해결을 지원함
- **이유**: 이 접근법은 문제 해결 과정에서 더 깊이 있는 탐색과 전략적 예측을 가능하게 하여, 기존 방법의 한계를 극복하고자 함 

### Delta 2: 탐색 알고리즘
- **기존**: 기존 CoT 및 CoT-SC는 각 체인 내에서 지역 탐색이 없었음
- **변경**: Tree of Thoughts는 다양한 탐색 알고리즘을 플러그 앤 플레이 방식으로 적용 가능
- **이유**: 탐색 알고리즘의 유연성을 높여 다양한 문제에 적합한 탐색 전략을 선택할 수 있도록 함 

## 방법론
### Thought Decomposition
문제의 특성에 따라 중간 사고 단계를 설계하고 분해하는 과정.
- **입력**: 문제의 특성
- **출력**: 중간 사고 단계 (Evidence: p.3 §Tree of Thoughts: Deliberate Problem Solving with LM)

### Thought Generator
다음 사고 단계를 생성하기 위한 후보를 생성하는 전략.
- **입력**: 현재 상태
- **출력**: 다음 사고 단계 후보 (Evidence: p.3 §Tree of Thoughts: Deliberate Problem Solving with LM)

### State Evaluator
문제 해결을 위한 진행 상황을 평가하여 탐색 알고리즘이 어떤 상태를 계속 탐색할지 결정하는 휴리스틱 역할을 합니다.
- **입력**: 다양한 상태의 전선
- **출력**: 상태의 평가 값 (Evidence: p.3 §Tree of Thoughts: Deliberate Problem Solving with LM)

### Search Algorithm
트리 구조에 따라 다양한 탐색 알고리즘을 플러그 앤 플레이할 수 있습니다.
- **입력**: 트리 구조
- **출력**: 탐색 결과 (Evidence: p.4 §Tree of Thoughts: Deliberate Problem Solving with LM)

## 트레이드오프
- **복잡성**
  - 이점: 더 깊이 있는 탐색과 전략적 예측 가능
  - 비용: 구현 및 계산 복잡도가 증가할 수 있음
  - 수용 가능 조건: 문제 해결의 정확성과 깊이가 중요한 경우

## 언제 사용해야 하는가?
✅ **사용 권장**: 탐색이나 전략적 예측이 필요한 복잡한 문제를 해결할 때

❌ **사용 비권장**: 단순한 문제나 계산 자원이 제한된 환경에서는 사용하지 않는 것이 좋음

## 주요 클레임
### 방법론 클레임
- Tree of Thoughts (ToT) 프레임워크는 언어 모델이 다양한 사고 경로를 탐색하고, 자기 평가를 통해 다음 행동을 결정할 수 있게 합니다. (Evidence: p.1 §Abstract)
### 결과 클레임
- ToT는 Game of 24, Creative Writing, Mini Crosswords와 같은 문제에서 언어 모델의 문제 해결 능력을 크게 향상시킵니다. (Evidence: p.1 §Abstract)
### 비교 클레임
- ToT는 IO, CoT, CoT-SC와 같은 기존 방법들보다 더 나은 성능을 보입니다. (Evidence: p.5 §Experiments)
### 한계 클레임
- ToT는 더 많은 자원을 필요로 하며, 성능-비용 절충을 사용자에게 맞출 수 있는 유연성을 제공합니다. (Evidence: p.9 §Discussion)

---
*Generated at 2026-02-13 11:57:05*
