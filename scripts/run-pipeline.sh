#!/usr/bin/env bash
# run-pipeline.sh — 기획서(.md) → QA 체크리스트(.csv) 재현 파이프라인 (macOS / Linux / Git Bash)
#
# 새 기획서(.md)를 넣으면 구조분석 → 케이스설계 → 우선순위분류 → 엣지보완 → CSV 생성까지
# /spec-to-qa 스킬을 headless(claude -p)로 호출해 한 번에 자동 수행한다.
#
# 사용법 (프로젝트 루트에서 실행):
#   ./scripts/run-pipeline.sh data/product_spec_petbbi_v1.md      # 특정 기획서 1건
#   ./scripts/run-pipeline.sh                                     # data/*.md 전체 일괄
#   PERMISSION_MODE=bypassPermissions ./scripts/run-pipeline.sh data/xxx.md
#
# 산출물: output/qa-checklist-<기획서파일명>.csv

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 파일 쓰기(CSV 저장) 자동 승인: acceptEdits(기본) / bypassPermissions(완전 무인)
PERMISSION_MODE="${PERMISSION_MODE:-acceptEdits}"

if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI를 찾을 수 없습니다. Claude Code가 설치돼 있어야 합니다." >&2
  exit 1
fi

# 대상 기획서 목록 결정
specs=()
if [ "$#" -ge 1 ]; then
  if [ ! -f "$1" ]; then
    echo "기획서를 찾을 수 없습니다: $1" >&2
    exit 1
  fi
  specs+=("$1")
else
  shopt -s nullglob
  for f in data/*.md; do specs+=("$f"); done
  shopt -u nullglob
  if [ "${#specs[@]}" -eq 0 ]; then
    echo "data/ 폴더에 .md 기획서가 없습니다. 경로를 인자로 지정하세요." >&2
    exit 1
  fi
  echo "[i] 경로 미지정 → data/*.md 전체 ${#specs[@]}건을 처리합니다."
fi

mkdir -p output

total="${#specs[@]}"
idx=0
for spec in "${specs[@]}"; do
  idx=$((idx + 1))
  rel="${spec#./}"
  base="$(basename "$spec" .md)"
  base="${base#product_spec_}"
  out_csv="output/qa-checklist-${base}.csv"

  echo ""
  echo "===== [${idx}/${total}] ${rel} → ${out_csv} ====="

  # /spec-to-qa 스킬을 headless로 실행 (STEP 1~5 자동 수행)
  if ! claude -p "/spec-to-qa ${rel}" --permission-mode "$PERMISSION_MODE"; then
    echo "[!] ${rel} 실행이 실패했습니다. 위 로그를 확인하세요." >&2
    continue
  fi

  if [ -f "$out_csv" ]; then
    echo "[✓] 생성 완료: ${out_csv}"
  else
    echo "[!] ${out_csv} 이 생성되지 않았습니다. 자가점검/미달 사유 로그를 확인하세요." >&2
  fi
done

echo ""
echo "파이프라인 종료. output/ 폴더에서 CSV와 커버리지 리포트를 확인하세요."
