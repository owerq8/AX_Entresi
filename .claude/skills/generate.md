---
name: generate
description: QA 체크리스트 CSV를 레벨(Basic/Standard/Challenge)에 맞춰 생성한다
---

# /generate — QA 체크리스트 생성

/insight에서 확정한 기준으로 output/qa-checklist-petbbi.csv 를 생성한다.

## CSV 컬럼 (고정 9개)
```
기능섹션,테스트케이스ID,테스트케이스제목,테스트유형,사전조건,테스트절차,기대결과,우선순위,출처
```
- 테스트케이스ID: TC-001 형식 연번
- 테스트유형: Happy Path / Unhappy Path / Edge Case
- 우선순위: P0 / P1 / P2
- 출처: 기획서기반 / AI추가
- 쉼표·줄바꿈 포함 값은 큰따옴표로 감쌀 것, UTF-8

## 레벨 분기

### 🟢 Basic
- 기능 섹션 6개 전체 커버
- 섹션마다 Happy Path + Unhappy Path 최소 1개씩
- 엣지케이스(AI추가) 최소 6건, 4유형 중 3유형 이상
- 모든 행에 P0/P1/P2 + 출처 표기
- 기대결과는 구체적으로 (모호한 "정상 동작" 금지)

### 🟡 Standard (+ 위 전체)
- 새 기획서(.md)를 넣으면 동일 컬럼·품질로 재생성되도록 /analyze→/insight→/generate 파이프라인화
- 섹션별 커버리지 리포트(섹션 × 케이스 수 × P0 포함 여부) 생성
- 체크리스트 양식·분류 기준을 본인 설계로 문서화

### 🔴 Challenge (+ 위 전체)
- 릴리즈 게이트 기준표: "P0 미해결 0건 = 출시 가능" 등
- 테스트 실행 우선순위 플랜 1~2건 (근거 케이스·리스크 포함)
- 우선순위 점수화 방식(영향도·범위 가중) 본인 설계

## 출력
- output/qa-checklist-petbbi.csv
- (Standard↑) 커버리지 리포트 / (Challenge) 릴리즈 게이트·실행 플랜
> 산출 후 반드시 /review 로 자가 점검.
