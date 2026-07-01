# Petbbi QA 대시보드 — Streamlit 배포 가이드

기획서 → QA 체크리스트 자동 생성 파이프라인(`/spec-to-qa`)의 산출물(CSV)을 웹 대시보드로 배포한다.
**별도 API 키가 필요 없다** — `output/`의 CSV만 읽어 동작하므로 공개 GitHub repo만 있으면 배포된다.

## 구성 파일
| 파일 | 역할 |
|---|---|
| `streamlit_app.py` | 대시보드 본체 (Streamlit Cloud 기본 진입점) |
| `requirements.txt` | 의존성 (`streamlit`, `pandas`) |
| `.streamlit/config.toml` | Petbbi 브랜드 테마(#e63946) |
| `output/**/*.csv` | 파이프라인이 생성한 QA 체크리스트 (v1~v4) |

## 1) 로컬 실행
```powershell
pip install -r requirements.txt
streamlit run streamlit_app.py
```
→ 브라우저에서 http://localhost:8501 자동 오픈

## 2) Streamlit Community Cloud 배포 (무료 · 권장)
1. 이 저장소를 **공개(public) GitHub repo**로 푸시
   ```powershell
   git add streamlit_app.py requirements.txt .streamlit/ output/
   git commit -m "Add Streamlit QA dashboard"
   git push
   ```
2. https://share.streamlit.io → **New app** → GitHub 계정 연결
3. Repository / Branch(`main`) / Main file path = **`streamlit_app.py`** 선택
4. **Deploy** → 1~2분 후 `https://<앱이름>.streamlit.app` 공개 URL 발급
   - 이 URL을 과제 제출 링크로 사용 가능

> 비공개 repo도 배포되지만, 무료 플랜에서 공개 링크 공유가 필요하면 public 권장.

## 3) 대시보드 기능 (레벨 매핑)
| 탭 | 내용 | 채점 레벨 |
|---|---|---|
| 📋 QA 체크리스트 | 섹션/유형/우선순위/출처 필터 + 검색 + CSV 다운로드 | Basic |
| 📊 커버리지 리포트 | 섹션×유형 매트릭스 · 엣지 세부유형 분포 · 우선순위 분포 | Basic/Standard |
| 🚦 릴리즈 게이트 | 점수화 기준 + **게이트 3-tier 라이브 시뮬레이터**(P0/P1 통과 토글→판정) | Challenge |
| 🔁 재현성 | v1~v4 기획서별 자동 생성 결과 비교 | Standard |

- 사이드바 **CSV 업로드**: `/spec-to-qa`로 새로 만든 9컬럼 체크리스트를 올리면 동일 화면으로 분석된다.

## 트러블슈팅
- **한글 깨짐**: CSV는 UTF-8(BOM)로 저장되어 있어야 함. 다운로드 버튼은 `utf-8-sig`로 인코딩.
- **CSV를 못 찾음**: `output/` 폴더가 repo에 커밋됐는지 확인(`.gitignore`가 제외하지 않음).
- **의존성 오류**: `requirements.txt`의 버전 범위 유지(`streamlit>=1.40`은 `st.data_editor` CheckboxColumn 필요).
