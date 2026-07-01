# -*- coding: utf-8 -*-
"""
Petbbi QA 체크리스트 대시보드 (Streamlit)
─────────────────────────────────────────
기획서 → QA 체크리스트 자동 생성 파이프라인(/spec-to-qa)의 산출물(CSV)을
인터랙티브하게 시각화한다. 별도 API 키 없이 output/의 CSV만 읽어 동작하므로
Streamlit Community Cloud(공개 GitHub repo)에 그대로 배포된다.

탭 구성
  📋 QA 체크리스트   : 필터/검색 가능한 케이스 테이블 + CSV 다운로드   (Basic)
  📊 커버리지 리포트 : 섹션×유형 매트릭스 · 엣지 세부유형 분포 · 우선순위 (Basic/Standard)
  🚦 릴리즈 게이트   : 점수화 기준 + 게이트 3-tier 라이브 시뮬레이터      (Challenge)
  🔁 재현성          : v1~v4 기획서별 자동 생성 결과 비교               (Standard)
"""
from pathlib import Path

import pandas as pd
import streamlit as st

# ────────────────────────────────────────────────────────────
# 기본 설정 & 브랜딩
# ────────────────────────────────────────────────────────────
BRAND = "#e63946"  # Petbbi coral (sample HTML 시안과 통일)
ROOT = Path(__file__).parent

st.set_page_config(
    page_title="Petbbi QA 체크리스트 대시보드",
    page_icon="🐾",
    layout="wide",
)

st.markdown(
    f"""
    <style>
      .stApp h1 {{ color: {BRAND}; }}
      div[data-testid="stMetricValue"] {{ color: {BRAND}; font-weight: 700; }}
      .stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}
      .pill {{ display:inline-block; padding:2px 10px; border-radius:12px;
              font-size:0.8rem; font-weight:600; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ────────────────────────────────────────────────────────────
# 데이터 소스 (파이프라인이 생성한 CSV)
# ────────────────────────────────────────────────────────────
SPECS = {
    "v1 · AI 캐릭터·소셜 (기본 · 53건)": "output/basic/qa-checklist-petbbi.csv",
    "v2 · 구독·결제": "output/standard/qa-checklist-petbbi-v2-subscription.csv",
    "v3 · 건강기록 (CRUD)": "output/standard/qa-checklist-petbbi-v3-health.csv",
    "v4 · 예약·일정": "output/standard/qa-checklist-petbbi_v4_booking.csv",
}
COLUMNS = ["기능섹션", "테스트케이스ID", "테스트케이스제목", "테스트유형",
           "사전조건", "테스트절차", "기대결과", "우선순위", "출처"]

PRIORITY_COLORS = {"P0": "#e63946", "P1": "#f4a261", "P2": "#8d99ae"}
TYPE_COLORS = {"Happy Path": "#2a9d8f", "Unhappy Path": "#e76f51", "Edge Case": "#6c5ce7"}


@st.cache_data(show_spinner=False)
def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(ROOT / path, dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]
    # 멀티라인 셀에 낀 개행 정리
    for c in df.columns:
        df[c] = df[c].str.replace(r"\s+", " ", regex=True).str.strip()
    return df


def edge_subtype(row: pd.Series) -> str:
    """Edge Case를 제목·절차 키워드로 세부유형 태깅 (파이프라인 '이면 태깅' 재현)."""
    if row["테스트유형"] != "Edge Case":
        return ""
    text = f"{row['테스트케이스제목']} {row['테스트절차']} {row['사전조건']}"
    rules = [
        ("권한", ["권한", "카메라", "갤러리"]),
        ("네트워크", ["네트워크", "끊김", "타임아웃", "연결"]),
        ("빈상태", ["0건", "0마리", "빈 상태", "없는", "없이", "미등록", "0마리"]),
        ("AI폴백", ["폴백", "미달", "재생성", "기준", "대체", "언어"]),
        ("상태정합성", ["정합성", "강제종료", "삭제", "복구", "중복"]),
    ]
    for name, kws in rules:
        if any(k in text for k in kws):
            return name
    return "경계값"


def pill(text: str, color: str) -> str:
    return (f"<span class='pill' style='background:{color}22;color:{color};"
            f"border:1px solid {color}55'>{text}</span>")


# ────────────────────────────────────────────────────────────
# 사이드바 — 데이터 선택 / 업로드
# ────────────────────────────────────────────────────────────
st.sidebar.title("🐾 Petbbi QA")
st.sidebar.caption("기획서 → QA 체크리스트 자동 생성 파이프라인 산출물")

uploaded = st.sidebar.file_uploader(
    "직접 만든 QA CSV 보기 (9컬럼)", type=["csv"],
    help="/spec-to-qa 로 새로 생성한 체크리스트 CSV를 올리면 동일 화면으로 분석됩니다.",
)

if uploaded is not None:
    df = pd.read_csv(uploaded, dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]
    source_label = f"업로드: {uploaded.name}"
else:
    choice = st.sidebar.radio("기획서 선택", list(SPECS.keys()), index=0)
    df = load_csv(SPECS[choice])
    source_label = choice

missing = [c for c in COLUMNS if c not in df.columns]
if missing:
    st.error(f"CSV에 필수 컬럼이 없습니다: {missing}\n\n필요 컬럼: {COLUMNS}")
    st.stop()

df["엣지세부유형"] = df.apply(edge_subtype, axis=1)

st.sidebar.divider()
st.sidebar.markdown(
    "**레벨 가이드**\n\n"
    "- 📋 체크리스트 · 📊 커버리지 → **Basic**\n"
    "- 🔁 재현성 → **Standard**\n"
    "- 🚦 릴리즈 게이트 → **Challenge**"
)

# ────────────────────────────────────────────────────────────
# 헤더 & KPI
# ────────────────────────────────────────────────────────────
st.title("Petbbi QA 체크리스트 대시보드")
st.caption(f"현재 데이터: **{source_label}**  ·  기획서(.md) → 구조분석 → 케이스설계 → 우선순위 → 엣지보완 → CSV")

n_total = len(df)
n_p0 = (df["우선순위"] == "P0").sum()
n_ai = (df["출처"] == "AI추가").sum()
n_sections = df["기능섹션"].nunique()

k1, k2, k3, k4 = st.columns(4)
k1.metric("총 테스트 케이스", f"{n_total}건")
k2.metric("P0 (출시 블로커)", f"{n_p0}건")
k3.metric("AI 추가 엣지케이스", f"{n_ai}건")
k4.metric("커버 기능섹션", f"{n_sections}개")

tab_list, tab_cov, tab_gate, tab_repro = st.tabs(
    ["📋 QA 체크리스트", "📊 커버리지 리포트", "🚦 릴리즈 게이트", "🔁 재현성"]
)

# ────────────────────────────────────────────────────────────
# 📋 QA 체크리스트
# ────────────────────────────────────────────────────────────
with tab_list:
    f1, f2, f3, f4 = st.columns(4)
    sel_sec = f1.multiselect("기능섹션", sorted(df["기능섹션"].unique()))
    sel_type = f2.multiselect("테스트유형", ["Happy Path", "Unhappy Path", "Edge Case"])
    sel_pri = f3.multiselect("우선순위", ["P0", "P1", "P2"])
    sel_src = f4.multiselect("출처", ["기획서기반", "AI추가"])
    kw = st.text_input("🔎 제목·절차·기대결과 검색", placeholder="예: 네트워크, 재생성, 삭제 …")

    view = df.copy()
    if sel_sec:
        view = view[view["기능섹션"].isin(sel_sec)]
    if sel_type:
        view = view[view["테스트유형"].isin(sel_type)]
    if sel_pri:
        view = view[view["우선순위"].isin(sel_pri)]
    if sel_src:
        view = view[view["출처"].isin(sel_src)]
    if kw:
        mask = (view["테스트케이스제목"].str.contains(kw, case=False, na=False)
                | view["테스트절차"].str.contains(kw, case=False, na=False)
                | view["기대결과"].str.contains(kw, case=False, na=False))
        view = view[mask]

    st.caption(f"필터 결과: **{len(view)}건** / 전체 {n_total}건")
    st.dataframe(
        view[COLUMNS],
        use_container_width=True,
        hide_index=True,
        column_config={
            "테스트케이스제목": st.column_config.TextColumn(width="medium"),
            "테스트절차": st.column_config.TextColumn(width="large"),
            "기대결과": st.column_config.TextColumn(width="large"),
        },
    )
    st.download_button(
        "⬇️ 필터 결과 CSV 다운로드",
        view[COLUMNS].to_csv(index=False).encode("utf-8-sig"),
        file_name="qa-checklist-filtered.csv",
        mime="text/csv",
    )

# ────────────────────────────────────────────────────────────
# 📊 커버리지 리포트
# ────────────────────────────────────────────────────────────
with tab_cov:
    st.subheader("섹션 × 테스트유형 매트릭스")
    st.caption("출시 직전 PM의 두 질문 — ①빈 섹션이 있나 ②그 섹션에 블로커(P0)가 잡혔나")

    matrix = (
        df.pivot_table(index="기능섹션", columns="테스트유형",
                       values="테스트케이스ID", aggfunc="count", fill_value=0)
    )
    for t in ["Happy Path", "Unhappy Path", "Edge Case"]:
        if t not in matrix.columns:
            matrix[t] = 0
    matrix = matrix[["Happy Path", "Unhappy Path", "Edge Case"]]
    p0_by_sec = df[df["우선순위"] == "P0"].groupby("기능섹션")["테스트케이스ID"].count()
    matrix["P0 포함"] = matrix.index.map(lambda s: int(p0_by_sec.get(s, 0)))
    matrix["소계"] = matrix[["Happy Path", "Unhappy Path", "Edge Case"]].sum(axis=1)

    def flag_row(r):
        warn = []
        if r["Happy Path"] == 0:
            warn.append("⚠️Happy 없음")
        if r["Unhappy Path"] == 0:
            warn.append("⚠️Unhappy 없음")
        return " ".join(warn) if warn else "✅"
    matrix["점검"] = matrix.apply(flag_row, axis=1)

    st.dataframe(matrix, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("우선순위 분포")
        pri = df["우선순위"].value_counts().reindex(["P0", "P1", "P2"]).fillna(0).astype(int)
        st.bar_chart(pri, color=BRAND, horizontal=True)
    with c2:
        st.subheader("테스트유형 분포 (출처별)")
        by_src = df.pivot_table(index="테스트유형", columns="출처",
                                values="테스트케이스ID", aggfunc="count", fill_value=0)
        st.bar_chart(by_src)

    st.subheader("엣지 세부유형 분포 — 실패 클래스 공백 감시")
    st.caption("평평한 'Edge N건'은 편중을 숨긴다. 세부 태깅으로 통째로 빈 실패 클래스를 잡는다.")
    edges = df[df["테스트유형"] == "Edge Case"]
    if len(edges):
        dist = edges["엣지세부유형"].value_counts()
        st.bar_chart(dist, color="#6c5ce7", horizontal=True)
        missing_kinds = {"권한", "네트워크", "빈상태", "경계값"} - set(dist.index)
        if missing_kinds:
            st.warning(f"엣지 유형 공백: {', '.join(sorted(missing_kinds))} — 해당 실패 클래스 미커버")
        else:
            st.success("엣지 4유형(권한·네트워크·빈상태·경계값) 모두 커버됨")
    else:
        st.info("Edge Case가 없습니다.")

    st.info(
        f"**릴리즈 준비도 한 줄**  ·  P0 {n_p0}건  ·  "
        f"미커버 섹션 {int((matrix['소계'] == 0).sum())}개  ·  "
        f"엣지 {edges['엣지세부유형'].nunique() if len(edges) else 0}유형 {len(edges)}건"
    )

# ────────────────────────────────────────────────────────────
# 🚦 릴리즈 게이트 (Challenge) — 라이브 시뮬레이터
# ────────────────────────────────────────────────────────────
with tab_gate:
    st.subheader("우선순위 점수화 (100점)")
    st.markdown(
        "2축 정성 판단(서비스 중단·영향 범위)에 **가역성** 축을 더한 3요소 가중합. "
        "총점 **≥80 = P0 / 50~79 = P1 / <50 = P2**."
    )
    score_tbl = pd.DataFrame({
        "요소": ["F1 서비스 중단 심각도", "F2 영향 사용자 범위", "F3 가역성/우회"],
        "배점": [50, 30, 20],
        "상(만점)": ["크래시·무한로딩·비가역 손실·핵심 플로우 불가",
                   "전체 사용자·전 신규 유입", "비가역(데이터·자원 영구 손실·규제 위반)"],
        "중": ["재시도로 복구 가능한 주요기능 실패", "특정 조건·세그먼트(다묘·해외·네트워크)",
              "우회는 되나 사용자 혼자 못 벗어남"],
        "하": ["표시·문구·경미 UX", "희소·비핵심", "즉시 재시도 복구"],
    })
    st.dataframe(score_tbl, use_container_width=True, hide_index=True)
    st.caption(
        "**도메인 즉시승격(점수 무관 P0)**: ①AI 생성 중 크래시·무한로딩 ②결제 이중청구·혜택 미반영 "
        "③추억 데이터 손실 ④계정 삭제 정합성 파괴 ⑤만14세 미만 미차단(규제) "
        "⑥사별·장기 비활동 반려동물 자동 콘텐츠 지속 생성(펫추모 정서신뢰)"
    )

    st.divider()
    st.subheader("릴리즈 게이트 라이브 시뮬레이터")
    st.markdown(
        "출시 직전 **미해결(테스트 실패)** 케이스 수로 go/no-go를 기계 판정한다. "
        "아래에서 P0·P1 케이스의 통과 여부를 토글하면 게이트가 실시간으로 갱신된다."
    )

    blockers = df[df["우선순위"].isin(["P0", "P1"])].copy()
    blockers["미해결(실패)"] = blockers["우선순위"] == "P0"  # 기본: P0는 미해결로 가정
    edit = st.data_editor(
        blockers[["테스트케이스ID", "기능섹션", "테스트케이스제목", "우선순위", "미해결(실패)"]],
        use_container_width=True,
        hide_index=True,
        disabled=["테스트케이스ID", "기능섹션", "테스트케이스제목", "우선순위"],
        column_config={"미해결(실패)": st.column_config.CheckboxColumn(help="체크 = 테스트 실패(미해결)")},
        key="gate_editor",
    )

    unresolved_p0 = int(((edit["우선순위"] == "P0") & edit["미해결(실패)"]).sum())
    unresolved_p1 = int(((edit["우선순위"] == "P1") & edit["미해결(실패)"]).sum())

    if unresolved_p0 > 0:
        verdict, color, note = ("🔴 출시 보류 (Block)", "#e63946",
                                f"미해결 P0 {unresolved_p0}건 — 1건이라도 있으면 출시 불가. 핫픽스 후 재검증 필요.")
    elif unresolved_p1 <= 2:
        verdict, color, note = ("🟡 조건부 출시 (Warn)", "#f4a261",
                                f"P0=0, 미해결 P1 {unresolved_p1}건(≤2) — PM 승인 하 출시 + 차기 스프린트 핫픽스 등록.")
    else:
        verdict, color, note = ("🟢 → 상한 초과", "#e76f51",
                                f"P0=0 이지만 미해결 P1 {unresolved_p1}건 > 상한 2 → 스프린트 연장 권장.")
    if unresolved_p0 == 0 and unresolved_p1 == 0:
        verdict, color, note = ("🟢 출시 가능 (Pass)", "#2a9d8f",
                                "P0=0 AND P1=0 — 정상 출시. P2는 백로그 이관.")

    g1, g2, g3 = st.columns(3)
    g1.metric("미해결 P0", f"{unresolved_p0}건")
    g2.metric("미해결 P1", f"{unresolved_p1}건")
    g3.metric("게이트 상한(P1)", "≤ 2건")
    st.markdown(
        f"<div style='padding:16px;border-radius:10px;background:{color}18;"
        f"border-left:6px solid {color};font-size:1.15rem;font-weight:700;color:{color}'>"
        f"{verdict}</div>",
        unsafe_allow_html=True,
    )
    st.caption(note)

    st.divider()
    st.subheader("테스트 실행 우선순위 플랜")
    st.markdown(
        "- **플랜 1 — 출시 차단 P0 우선** (Day 1 오전): P0 전량 일괄 실행. "
        "1건 실패 = 즉시 🔴 보류 확정 → 출시 가부 리드타임 최소화.\n"
        "- **플랜 2 — 이탈·글로벌 P1 회귀** (P0 PASS 후 Day 1 오후): 다국어·다묘·권한 등 "
        "세그먼트 리스크 위주. 미해결 P1이 상한(≤2) 초과 여부가 게이트 입력값."
    )

# ────────────────────────────────────────────────────────────
# 🔁 재현성 (Standard) — v1~v4 비교
# ────────────────────────────────────────────────────────────
with tab_repro:
    st.subheader("재현성 검증 — 성격이 다른 기획서 4건에 동일 파이프라인 적용")
    st.caption("건수·P0 비율이 매번 다른 것은 기획서마다 리스크 구조가 다르기 때문. "
               "규칙(2축 점수·6개 승격·엣지 규칙엔진)은 4건 모두 동일하게 적용됨.")

    rows = []
    for label, path in SPECS.items():
        p = ROOT / path
        if not p.exists():
            continue
        d = load_csv(path)
        d["엣지세부유형"] = d.apply(edge_subtype, axis=1)
        edge_kinds = d[d["테스트유형"] == "Edge Case"]["엣지세부유형"].nunique()
        rows.append({
            "기획서": label,
            "총 케이스": len(d),
            "Happy": (d["테스트유형"] == "Happy Path").sum(),
            "Unhappy": (d["테스트유형"] == "Unhappy Path").sum(),
            "Edge": (d["테스트유형"] == "Edge Case").sum(),
            "P0": (d["우선순위"] == "P0").sum(),
            "AI추가": (d["출처"] == "AI추가").sum(),
            "엣지유형수": edge_kinds,
            "섹션수": d["기능섹션"].nunique(),
        })
    repro = pd.DataFrame(rows)
    st.dataframe(repro, use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.caption("기획서별 케이스 수")
        st.bar_chart(repro.set_index("기획서")["총 케이스"], color=BRAND)
    with c2:
        st.caption("기획서별 P0(블로커) 수 — 도메인마다 리스크 구조가 다름")
        st.bar_chart(repro.set_index("기획서")["P0"], color="#6c5ce7")

    st.info(
        "**재현 규칙(4건 공통)**: 섹션당 Happy+Unhappy 커버(순수 조회는 사유와 함께 면제) · "
        "엣지 4유형 중 3유형↑ · P0는 2축 판단상 자연 발생 시 포함. "
        "→ 신규 기획서(.md)를 `/spec-to-qa` 또는 `run-pipeline.ps1`에 넣으면 동일 품질로 자동 생성."
    )

st.divider()
st.caption("🐾 Petbbi QA Pipeline · 엔트레씨 QA/PM · /spec-to-qa 산출물 시각화 · Streamlit")
