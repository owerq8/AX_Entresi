# QA 체크리스트 자동 생성 파이프라인 (재현성 산출물)

기획서(`.md`) 하나를 넣으면 **구조분석 → 케이스설계 → 우선순위분류 → 엣지보완 → CSV 생성**까지
한 번의 실행으로 자동 수행하는 재현 파이프라인입니다. (Standard "파이프라인 재현성" 요건)

## 구성

| 파일 | 역할 |
|---|---|
| `.claude/skills/spec-to-qa.md` | 파이프라인 본체(스킬). STEP 1~5 규칙(구조분석·규칙엔진·우선순위 점수화·릴리즈 게이트)을 정의 |
| `run-pipeline.ps1` | Windows(PowerShell) 실행 래퍼 — 스킬을 headless로 호출 |
| `run-pipeline.sh` | macOS/Linux/Git Bash 실행 래퍼 |

> 스킬(`/spec-to-qa`)이 파이프라인의 "두뇌"이고, 래퍼 스크립트는 새 기획서를 넣어 무인으로 돌리는 "실행기"입니다.
> 채점 기준의 "**/명령 또는 스크립트**" 두 형태를 모두 제공합니다.

## 사용법

### 방법 A — 슬래시 커맨드 (대화 중)
Claude Code 세션 안에서:
```
/spec-to-qa data/product_spec_petbbi_v1.md
```

### 방법 B — 스크립트 (터미널, 무인 실행)

**Windows (PowerShell):**
```powershell
# 특정 기획서 1건
./run-pipeline.ps1 data/product_spec_petbbi_v1.md

# data/*.md 전체 일괄
./run-pipeline.ps1
```

**macOS / Linux / Git Bash:**
```bash
chmod +x run-pipeline.sh          # 최초 1회
./run-pipeline.sh data/product_spec_petbbi_v1.md
./run-pipeline.sh                 # data/*.md 전체 일괄
```

## 입력 / 출력

- **입력**: `data/` 아래 기획서 `.md` (H2=기능섹션, H3=세부항목 구조 권장)
- **출력**: `output/qa-checklist-<기획서파일명>.csv`
  (파일명은 `product_spec_` 접두어와 `.md` 확장자를 제거해 생성)
- **부가 출력**(대화 로그): STEP 4 커버리지 리포트 4종 + STEP 5 릴리즈 게이트·우선순위 점수화·테스트 실행 플랜

### CSV 컬럼 (고정 9개)
```
기능섹션, 테스트케이스ID, 테스트케이스제목, 테스트유형, 사전조건, 테스트절차, 기대결과, 우선순위, 출처
```

## 재현성 보장 포인트

1. **엣지케이스 규칙엔진** — 기획서 동작 키워드(업로드·생성·한도·조회·삭제·결제)를 표에 대입해 엣지 후보를 기계적으로 도출. 사람이 매번 새로 떠올리지 않음.
2. **우선순위 점수화(100점, 3축)** — 서비스중단(50)·영향범위(30)·가역성(20) 가중합 + 도메인 즉시승격 규칙. 같은 기획서는 항상 같은 P0/P1/P2.
3. **릴리즈 게이트(3-tier)** — 미해결 P0>0 → 🔴 출시보류 / P0=0 & P1≤2 → 🟡 조건부 / P0=0 & P1=0 → 🟢 출시가능.
4. **정직한 미달 보고** — 스펙이 빈약하면 케이스를 지어내지 않고 미달 사유를 보고(신뢰성 우선).

## 요구 사항

- Claude Code CLI 설치(`claude --version`) — 별도 API 키 불필요, 대화 세션 자격증명 사용
- 스크립트는 파일 쓰기(CSV 저장) 자동 승인을 위해 `--permission-mode acceptEdits`로 실행.
  완전 무인 배치가 필요하면 `PERMISSION_MODE=bypassPermissions`(sh) 또는 `-PermissionMode bypassPermissions`(ps1).

## 검증 이력

`data/product_spec_petbbi_v1~v4`(펫삐 본편·구독·건강·예약 4종) 기획서로 실행해 동일 품질의
9컬럼 CSV·커버리지 리포트·릴리즈 게이트가 재생성됨을 확인. 상세는 `output/scoring-validation.md` 및
`output/coverage-report-*.md` 참조.
