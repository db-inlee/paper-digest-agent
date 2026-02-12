---
layout: default
title: Paper Digest
---

# Paper Digest

> 매일 HuggingFace에서 LLM/Agent 관련 논문을 자동 수집하고 분석합니다.

## Daily Reports

<!-- 자동 생성되는 영역 -->
{% assign reports = site.static_files | where_exp: "file", "file.path contains '/daily/'" | sort: "name" | reverse %}
{% for report in reports %}
{% if report.extname == ".md" %}
- [{{ report.name | remove: ".md" }}]({{ report.path | relative_url }})
{% endif %}
{% endfor %}

---

## About

이 프로젝트는 LangGraph 기반의 자동화된 연구 논문 분석 파이프라인입니다.

- **자동 논문 수집**: HuggingFace Daily Papers에서 최신 논문 수집
- **LLM 기반 평가**: 실용성, 구현 가능성, 신뢰도 점수 산출
- **자기 교정**: Verification → Correction 루프로 정확성 보장

[GitHub Repository](https://github.com/your-username/paper-digest-agent)
