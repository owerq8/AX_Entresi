# run-pipeline.ps1 — 기획서(.md) → QA 체크리스트(.csv) 재현 파이프라인 (Windows / PowerShell)
#
# 새 기획서(.md)를 넣으면 구조분석 → 케이스설계 → 우선순위분류 → 엣지보완 → CSV 생성까지
# /spec-to-qa 스킬을 headless(claude -p)로 호출해 한 번에 자동 수행한다.
#
# 사용법 (프로젝트 루트에서 실행):
#   ./scripts/run-pipeline.ps1 data/product_spec_petbbi_v1.md      # 특정 기획서 1건
#   ./scripts/run-pipeline.ps1                                      # data/*.md 전체 일괄
#   ./scripts/run-pipeline.ps1 -SpecPath data/xxx.md -PermissionMode acceptEdits
#
# 산출물: output/qa-checklist-<기획서파일명>.csv  (+ 커버리지 리포트/릴리즈 게이트는 대화 로그로 출력)

param(
    [Parameter(Position = 0)]
    [string]$SpecPath,

    # 파일 쓰기(CSV 저장)를 자동 승인하려면 acceptEdits. 완전 무인 실행은 bypassPermissions.
    [ValidateSet('acceptEdits', 'bypassPermissions', 'default')]
    [string]$PermissionMode = 'acceptEdits'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

# claude CLI 존재 확인
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Error "claude CLI를 찾을 수 없습니다. Claude Code가 설치돼 있어야 합니다."
    exit 1
}

# 대상 기획서 목록 결정
if ($SpecPath) {
    if (-not (Test-Path -LiteralPath $SpecPath)) {
        Write-Error "기획서를 찾을 수 없습니다: $SpecPath"
        exit 1
    }
    $specs = @((Resolve-Path -LiteralPath $SpecPath).Path)
}
else {
    $specs = Get-ChildItem -Path (Join-Path $root 'data') -Filter '*.md' -File | Select-Object -ExpandProperty FullName
    if (-not $specs) {
        Write-Error "data/ 폴더에 .md 기획서가 없습니다. 경로를 인자로 지정하세요."
        exit 1
    }
    Write-Host "[i] 경로 미지정 → data/*.md 전체 $($specs.Count)건을 처리합니다." -ForegroundColor Cyan
}

if (-not (Test-Path (Join-Path $root 'output'))) {
    New-Item -ItemType Directory -Path (Join-Path $root 'output') | Out-Null
}

$idx = 0
foreach ($spec in $specs) {
    $idx++
    # 프로젝트 루트 기준 상대경로로 스킬에 전달
    $rel = (Resolve-Path -LiteralPath $spec -Relative) -replace '\\', '/'
    $rel = $rel -replace '^\./', ''

    # 출력 파일명 미리보기 (스킬 규칙: product_spec_ 접두어 + 확장자 제거)
    $base = [IO.Path]::GetFileNameWithoutExtension($spec) -replace '^product_spec_', ''
    $outCsv = "output/qa-checklist-$base.csv"

    Write-Host ""
    Write-Host "===== [$idx/$($specs.Count)] $rel → $outCsv =====" -ForegroundColor Green

    # /spec-to-qa 스킬을 headless로 실행 (STEP 1~5 자동 수행)
    claude -p "/spec-to-qa $rel" --permission-mode $PermissionMode

    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[$rel] 실행이 0이 아닌 종료코드로 끝났습니다 (exit=$LASTEXITCODE)."
        continue
    }

    if (Test-Path -LiteralPath (Join-Path $root $outCsv)) {
        Write-Host "[✓] 생성 완료: $outCsv" -ForegroundColor Green
    }
    else {
        Write-Warning "[!] $outCsv 이 생성되지 않았습니다. 위 로그(자가점검/미달 사유)를 확인하세요."
    }
}

Write-Host ""
Write-Host "파이프라인 종료. output/ 폴더에서 CSV와 커버리지 리포트를 확인하세요." -ForegroundColor Cyan
