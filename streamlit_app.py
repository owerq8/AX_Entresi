# -*- coding: utf-8 -*-
"""
Petbbi QA 체크리스트 대시보드 (Streamlit)
─────────────────────────────────────────
기획서 → QA 체크리스트 자동 생성 파이프라인(/spec-to-qa)의 산출물(CSV)을
인터랙티브하게 시각화한다. 별도 API 키 없이 output/의 CSV만 읽어 동작하므로
Streamlit Community Cloud(공개 GitHub repo)에 그대로 배포된다.

탭 구성
  📋 QA 체크리스트   : 필터/검색 가능한 케이스 테이블 + CSV 다운로드   (Basic)
  📊 커버리지 리포트 : 섹션×유형 매트릭스 · 엣지 세부유형 분포 · 글로벌/다국어 분포 · 우선순위 (Basic/Standard)
  🚦 릴리즈 게이트   : 점수화 기준 + 게이트 3-tier 라이브 시뮬레이터      (Challenge)
  🔁 재현성          : v1~v4 기획서별 자동 생성 결과 비교               (Standard)
"""
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ────────────────────────────────────────────────────────────
# 기본 설정 & 브랜딩
# ────────────────────────────────────────────────────────────
BRAND = "#c85f3d"  # Petbbi 브랜드 톤 — 로고 원색(#e95528)과 차분한 무드 사이 절충 톤
# (.streamlit/config.toml의 theme.primaryColor와 동일 값 유지)
ROOT = Path(__file__).parent
FONT_STACK = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans KR', sans-serif"

st.set_page_config(
    page_title="Petbbi QA 체크리스트 대시보드",
    page_icon="🐾",
    layout="wide",
)

# ────────────────────────────────────────────────────────────
# 색상 토큰 — output/ 산출물(qa-checklist-petbbi.html, release-gate-challenge.html)의
# 브랜드 배지 색을 그대로 재사용. 표에 선례가 없는 신규 UI(커버리지 매트릭스
# 조건부 서식)만 검증된 시맨틱 팔레트(SEMANTIC)를 사용한다.
# ────────────────────────────────────────────────────────────
TYPE_BADGE = {
    "Happy Path": ("#d0ebe0", "#1f5c3d"),
    "Unhappy Path": ("#ffe3cf", "#b5560a"),
    "Edge Case": ("#ede0ff", "#5b2bb0"),
}
PRIORITY_BADGE = {
    "P0": ("#ffe0e3", "#c9323e"),
    "P1": ("#fff3cd", "#856404"),
    "P2": ("#e9ecef", "#495057"),
}
SOURCE_BADGE = {
    "기획서기반": ("#e2ecff", "#2d51c4"),
    "AI추가": ("#ffe9f4", "#c11a6b"),
}
SEMANTIC = {"warning": "#fab219", "critical": "#d03b3b"}

TYPE_ORDER = ["Happy Path", "Unhappy Path", "Edge Case"]
PRIORITY_ORDER = ["P0", "P1", "P2"]
SOURCE_ORDER = ["기획서기반", "AI추가"]
EDGE_ORDER = ["권한", "네트워크", "빈상태", "AI폴백", "상태정합성", "경계값"]

# 차트 마커 색도 배지 색에서 파생 — "P0의 색"을 정의하는 곳을 하나로 유지
CHART_COLOR = {k: v[1] for d in (TYPE_BADGE, PRIORITY_BADGE, SOURCE_BADGE) for k, v in d.items()}

st.markdown(
    f"""
    <style>
      /* base */
      .stApp {{ background: #f4f5f7; }}
      .stApp h1 {{ color: {BRAND}; font-weight: 800; letter-spacing: -.3px; }}
      div[data-testid="stMetricValue"] {{ color: {BRAND}; font-weight: 700; }}
      .stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}

      /* 브랜드 로고+타이틀 — 아이콘과 글자 사이 기본 stVerticalBlock 간격(16px)을 좁힘 */
      div[class*="st-key-brand_header"], div[class*="st-key-brand_sidebar"] {{ gap: 2px !important; }}
      div[class*="st-key-brand_header"] h1 {{ margin-top: 4px; }}
      div[class*="st-key-brand_sidebar"] h1 {{ margin-top: 2px; }}

      /* 섹션 카드 — st.container(border=True, key="section_*")의 공개 CSS 훅 */
      div[class*="st-key-section_"] {{
        background: #fff; border-radius: 12px; border-color: transparent !important;
        box-shadow: 0 1px 4px rgba(0,0,0,.06); padding: 6px 6px 2px;
      }}
      .section-title {{
        font-size: 15px; font-weight: 700; padding-bottom: 12px; margin-bottom: 12px;
        border-bottom: 1px solid #eee;
      }}

      /* KPI 스탯 타일 — pct 줄 유무와 무관하게 4장 높이를 고정해 정렬 맞춤 */
      .stat-tile {{
        background: #fff; border-radius: 10px; padding: 20px; text-align: center;
        box-shadow: 0 1px 4px rgba(0,0,0,.06); border-top: 4px solid currentColor;
        min-height: 138px; box-sizing: border-box;
        display: flex; flex-direction: column; justify-content: center;
      }}
      .stat-n {{ font-size: 40px; font-weight: 800; line-height: 1.1; }}
      .stat-label {{ font-size: 13px; color: #666; margin-top: 2px; }}
      .stat-pct {{ font-size: 13px; font-weight: 600; margin-top: 6px; min-height: 18px; }}
      .stat-c-red {{ color: {SEMANTIC['critical']}; }}
      .stat-c-purple {{ color: #6c5ce7; }}
      .stat-c-blue {{ color: #4361ee; }}
      .stat-c-gray {{ color: #6c757d; }}

      /* 릴리즈 게이트 verdict 카드 */
      .verdict {{
        background: #fff; border: 1.5px solid; border-left-width: 6px; border-radius: 12px;
        padding: 20px 26px; display: flex; align-items: center; gap: 22px; flex-wrap: wrap;
        box-shadow: 0 1px 4px rgba(0,0,0,.05);
      }}
      .verdict-flag {{ font-size: 34px; }}
      .verdict-body {{ flex: 1; min-width: 240px; }}
      .verdict-status {{ font-size: 18px; font-weight: 900; }}
      .verdict-desc {{ font-size: 12.5px; color: #666; margin-top: 3px; }}
      .verdict-nums {{ display: flex; gap: 8px; }}
      .vn {{ border-radius: 9px; padding: 10px 15px; text-align: center; min-width: 62px; }}
      .vn-n {{ font-size: 23px; font-weight: 900; line-height: 1; }}
      .vn-l {{ font-size: 10.5px; margin-top: 4px; font-weight: 600; }}

      /* 빈 상태 */
      .empty-state {{ text-align: center; padding: 48px 24px; color: #6c757d; }}
      .empty-state .icon {{ font-size: 32px; margin-bottom: 8px; }}
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
# 기획서 원문(.md) — H2 섹션 목록을 뽑아 "케이스가 0건이라 표에 아예 안 잡히는 섹션"까지 감지하는 데 사용
SPEC_MD = {
    "v1 · AI 캐릭터·소셜 (기본 · 53건)": "data/product_spec_petbbi_v1.md",
    "v2 · 구독·결제": "data/product_spec_petbbi_v2_subscription.md",
    "v3 · 건강기록 (CRUD)": "data/product_spec_petbbi_v3_health.md",
    "v4 · 예약·일정": "data/product_spec_petbbi_v4_booking.md",
}
COLUMNS = ["기능섹션", "테스트케이스ID", "테스트케이스제목", "테스트유형",
           "사전조건", "테스트절차", "기대결과", "우선순위", "출처"]


@st.cache_data(show_spinner=False)
def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(ROOT / path, dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]
    # 멀티라인 셀에 낀 개행 정리
    for c in df.columns:
        df[c] = df[c].str.replace(r"\s+", " ", regex=True).str.strip()
    return df


def parse_h2_sections(md_text: str) -> list[str]:
    """기획서 원문에서 H2("## ") 제목을 순서대로 뽑는다 — 케이스 0건이라 표에 행 자체가
    안 생기는 섹션까지 잡기 위해, CSV가 아니라 기획서 원문을 기준(ground truth)으로 삼는다."""
    return [line.removeprefix("## ").strip() for line in md_text.splitlines() if line.startswith("## ")]


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


GLOBAL_KEYWORDS = ["다국어", "언어", "영어", "일본어", "한국어", "해외", "글로벌", "국가", "타임존", "번역"]


def is_global_related(row: pd.Series) -> bool:
    """다국어·해외 동시 출시(Petbbi 핵심 비즈니스 축) 관련 케이스인지 키워드로 태깅.
    Happy/Unhappy/Edge를 가로지르는 별도 축이라 엣지세부유형과 별개로 태깅한다."""
    text = f"{row['테스트케이스제목']} {row['테스트절차']} {row['사전조건']} {row['기대결과']}"
    return any(k in text for k in GLOBAL_KEYWORDS)


# ────────────────────────────────────────────────────────────
# UI 컴포넌트 헬퍼
# ────────────────────────────────────────────────────────────
def stat_tile(label: str, value: str, pct: str, color_class: str) -> str:
    return (
        f"<div class='stat-tile {color_class}'>"
        f"<div class='stat-n'>{value}</div>"
        f"<div class='stat-label'>{label}</div>"
        f"<div class='stat-pct'>{pct}</div>"
        f"</div>"
    )


def section(title: str, *, key: str, caption: str | None = None):
    """카드형 섹션 컨테이너. 반환된 컨테이너를 `with box:`로 재사용해 내용을 이어붙인다."""
    box = st.container(border=True, key=f"section_{key}")
    with box:
        st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)
        if caption:
            st.caption(caption)
    return box


def _badge_css(value: str, badge_dict: dict) -> str:
    bg, fg = badge_dict.get(value, ("", ""))
    if not bg:
        return ""
    return f"background-color:{bg};color:{fg};font-weight:700;border-radius:4px"


def style_checklist(view: pd.DataFrame):
    """9컬럼 체크리스트에 우선순위/유형/출처 배지 배경색을 입힌 Styler.
    (Styler는 셀에 임의 HTML을 렌더링하지 못하므로 배경색/폰트굵기 등 CSS 속성만 적용한다.)"""
    styler = view.style
    styler = styler.map(lambda v: _badge_css(v, TYPE_BADGE), subset=["테스트유형"])
    styler = styler.map(lambda v: _badge_css(v, PRIORITY_BADGE), subset=["우선순위"])
    styler = styler.map(lambda v: _badge_css(v, SOURCE_BADGE), subset=["출처"])
    return styler


def style_matrix(matrix: pd.DataFrame):
    """섹션×유형 매트릭스에 공백(Happy/Unhappy 0건)·P0 존재 여부를 시맨틱 색으로 강조."""
    def _zero_warn(v):
        return f"background-color:{SEMANTIC['warning']}33;color:#7a5200;font-weight:700" if v == 0 else ""

    def _p0_flag(v):
        return f"background-color:{SEMANTIC['critical']}33;color:#8a1f1f;font-weight:700" if v > 0 else ""

    styler = matrix.style
    styler = styler.map(_zero_warn, subset=["Happy Path", "Unhappy Path"])
    styler = styler.map(_p0_flag, subset=["P0 포함"])
    return styler


def plotly_bar(df: pd.DataFrame, x: str, y: str, *, color: str | None = None,
               orientation: str = "v", category_orders: dict | None = None,
               color_discrete_map: dict | None = None,
               color_discrete_sequence: list | None = None, barmode: str = "group"):
    fig = px.bar(
        df, x=x, y=y, color=color, orientation=orientation,
        category_orders=category_orders or {},
        color_discrete_map=color_discrete_map,
        color_discrete_sequence=color_discrete_sequence,
        barmode=barmode, text_auto=True,
    )
    fig.update_traces(marker_line_width=0, textfont_size=11)
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_family=FONT_STACK,
        margin=dict(l=8, r=8, t=8, b=8),
        showlegend=color is not None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        height=280,
    )
    # automargin=True — 두 축 모두 좁은 고정 margin(8px)에 라벨이 잘리거나 겹치지 않도록 함
    value_axis = dict(showgrid=True, gridcolor="#e9ecef", zeroline=False, title=None, automargin=True)
    cat_axis = dict(showgrid=False, title=None, automargin=True)
    if orientation == "h":
        fig.update_xaxes(**value_axis)
        fig.update_yaxes(**cat_axis)
    else:
        fig.update_yaxes(**value_axis)
        fig.update_xaxes(**cat_axis)
    return fig


def verdict_card(flag: str, status: str, desc: str, border_color: str,
                  p0: int, p1: int, p2: int) -> str:
    chips = "".join(
        f"<div class='vn' style='background:{bg};color:{fg}'>"
        f"<div class='vn-n'>{n}</div><div class='vn-l'>{label}</div></div>"
        for label, n, (bg, fg) in (
            ("P0", p0, PRIORITY_BADGE["P0"]),
            ("P1", p1, PRIORITY_BADGE["P1"]),
            ("P2", p2, PRIORITY_BADGE["P2"]),
        )
    )
    return (
        f"<div class='verdict' style='border-color:{border_color}'>"
        f"<div class='verdict-flag'>{flag}</div>"
        f"<div class='verdict-body'>"
        f"<div class='verdict-status' style='color:{border_color}'>{status}</div>"
        f"<div class='verdict-desc'>{desc}</div>"
        f"</div>"
        f"<div class='verdict-nums'>{chips}</div>"
        f"</div>"
    )


# ────────────────────────────────────────────────────────────
# 기획서(.md) → QA 체크리스트 자동 생성 (로컬 Claude Code CLI 헤드리스 호출)
# ────────────────────────────────────────────────────────────
CLAUDE_BIN = shutil.which("claude")


@st.cache_data(show_spinner="AI가 기획서를 분석해 QA 체크리스트를 생성하는 중입니다 (최대 5분 소요)…")
def generate_checklist_from_spec(md_bytes: bytes, filename: str) -> pd.DataFrame:
    """업로드된 .md를 임시 파일로 저장해 로컬 claude CLI로 /spec-to-qa를 헤드리스 실행하고
    결과 CSV를 읽어 DataFrame으로 반환한다. 입력·출력 임시 파일은 읽은 뒤 바로 정리한다.
    임시 디렉터리는 반드시 프로젝트 안(data/)에 만든다 — OS 임시 폴더(프로젝트 밖)에 두면
    claude CLI가 신뢰하지 않는 경로라 파일 읽기 권한이 승인되지 않아 헤드리스 실행이 막힌다."""
    with tempfile.TemporaryDirectory(dir=ROOT / "data", prefix="_upload_") as tmp:
        stem = Path(filename).stem.replace("product_spec_", "") or "spec"
        spec_path = Path(tmp) / f"{stem}_{uuid.uuid4().hex[:8]}.md"
        spec_path.write_bytes(md_bytes)
        out_csv = ROOT / "output" / f"qa-checklist-{spec_path.stem}.csv"
        try:
            result = subprocess.run(
                [CLAUDE_BIN, "-p", f"/spec-to-qa {spec_path}", "--permission-mode", "acceptEdits"],
                cwd=ROOT, capture_output=True, text=True, timeout=300,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("생성이 5분 내에 끝나지 않았습니다(타임아웃).") from e

        if not out_csv.exists():
            tail = ((result.stdout or "")[-800:] + "\n" + (result.stderr or "")[-800:]).strip()
            raise RuntimeError(f"CSV가 생성되지 않았습니다.\n\n{tail or '(로그 없음)'}")

        gen = pd.read_csv(out_csv, dtype=str).fillna("")
        gen.columns = [c.strip() for c in gen.columns]
        out_csv.unlink(missing_ok=True)
        return gen


# ────────────────────────────────────────────────────────────
# 사이드바 — 데이터 선택 / 업로드
# ────────────────────────────────────────────────────────────
with st.sidebar.container(key="brand_sidebar"):
    st.image(str(ROOT / "assets" / "petbbi_icon.png"), width=48)
    st.title("Petbbi QA")

choice = st.sidebar.radio("기획서 선택", list(SPECS.keys()), index=0)

uploaded_spec = st.sidebar.file_uploader(
    "기획서(.md) 업로드 → QA 체크리스트 자동 생성",
    type=["md"],
    label_visibility="collapsed",
    help="/spec-to-qa 파이프라인이 실행돼 표준 9컬럼 체크리스트를 생성합니다. "
         "Claude Code CLI가 설치된 로컬 환경에서만 동작하며 최대 5분 정도 걸릴 수 있습니다.",
    disabled=CLAUDE_BIN is None,
)
if CLAUDE_BIN is None:
    st.sidebar.caption("⚠️ 이 환경에는 Claude Code CLI가 없어 자동 생성 기능을 사용할 수 없습니다. 위에서 기존 산출물을 선택하세요.")

df = None
source_label = None
if uploaded_spec is not None and CLAUDE_BIN is not None:
    try:
        df = generate_checklist_from_spec(uploaded_spec.getvalue(), uploaded_spec.name)
        source_label = f"AI 생성: {uploaded_spec.name}"
    except Exception as e:
        st.sidebar.error(f"체크리스트 생성 실패: {e}")

if df is None:
    df = load_csv(SPECS[choice])
    source_label = choice

spec_md_text = ""
if source_label and source_label.startswith("AI 생성") and uploaded_spec is not None:
    spec_md_text = uploaded_spec.getvalue().decode("utf-8", errors="ignore")
elif choice in SPEC_MD:
    try:
        spec_md_text = (ROOT / SPEC_MD[choice]).read_text(encoding="utf-8")
    except OSError:
        spec_md_text = ""
expected_sections = parse_h2_sections(spec_md_text)

missing = [c for c in COLUMNS if c not in df.columns]
if missing:
    st.error(f"CSV에 필수 컬럼이 없습니다: {missing}\n\n필요 컬럼: {COLUMNS}")
    st.stop()

if df.empty:
    st.warning("데이터가 비어 있습니다. CSV 내용을 확인하거나 다른 기획서를 선택하세요.")
    st.stop()

df["엣지세부유형"] = df.apply(edge_subtype, axis=1)
df["글로벌관련"] = df.apply(is_global_related, axis=1)

# ────────────────────────────────────────────────────────────
# 헤더 & KPI
# ────────────────────────────────────────────────────────────
with st.container(key="brand_header"):
    st.image(str(ROOT / "assets" / "petbbi_logo.png"), width=90)
    st.title("Petbbi(펫삐) QA 체크리스트")
st.caption(f"현재 데이터: **{source_label}**  ·  기획서 기반 QA 체크리스트 자동 생성 파이프라인 산출물입니다.")

n_total = len(df)
n_p0 = int((df["우선순위"] == "P0").sum())
n_p1 = int((df["우선순위"] == "P1").sum())
n_p2 = int((df["우선순위"] == "P2").sum())
n_ai = int((df["출처"] == "AI추가").sum())
n_sections = df["기능섹션"].nunique()

k1, k2, k3, k4 = st.columns(4)
k1.markdown(stat_tile("총 테스트 케이스", f"{n_total}건", "", "stat-c-purple"), unsafe_allow_html=True)
k2.markdown(stat_tile("P0 (출시 블로커)", f"{n_p0}건", f"{n_p0 / n_total:.0%} 비중", "stat-c-red"), unsafe_allow_html=True)
k3.markdown(stat_tile("AI 추가 엣지케이스", f"{n_ai}건", f"{n_ai / n_total:.0%} 비중", "stat-c-blue"), unsafe_allow_html=True)
k4.markdown(stat_tile("커버 기능섹션", f"{n_sections}개", f"섹션당 평균 {n_total / n_sections:.1f}건", "stat-c-gray"), unsafe_allow_html=True)

st.write("")
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

    box = section("필터 결과", key="checklist")
    with box:
        st.caption(f"필터 결과: **{len(view)}건** / 전체 {n_total}건")
        if view.empty:
            st.markdown(
                "<div class='empty-state'><div class='icon'>🔍</div>"
                "조건에 맞는 테스트 케이스가 없습니다. 필터를 조정해 보세요.</div>",
                unsafe_allow_html=True,
            )
        else:
            st.dataframe(
                style_checklist(view[COLUMNS]),
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
    _edges_all = df[df["테스트유형"] == "Edge Case"]
    # 기획서 원문(H2)을 기준으로 비교 — CSV만 보면 케이스 0건인 섹션은 표에 행 자체가 안 생겨 못 잡는다
    _missing_sections = [s for s in expected_sections if s not in set(df["기능섹션"])]
    st.info(
        f"**커버리지 요약**  ·  P0 {n_p0}건  ·  "
        f"미커버 섹션 {len(_missing_sections)}개  ·  "
        f"엣지 {_edges_all['엣지세부유형'].nunique() if len(_edges_all) else 0}유형 {len(_edges_all)}건"
    )
    if _missing_sections:
        st.warning(f"기획서엔 있는데 케이스가 하나도 없는 섹션: {', '.join(_missing_sections)}")

    box = section("기능 섹션 x 테스트 유형 매트릭스", key="matrix",
                   caption="섹션별로 Happy/Unhappy 누락 여부와 P0 포함 여부를 확인합니다.")
    with box:
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
        matrix.index.name = "기능 섹션"

        st.dataframe(style_matrix(matrix), use_container_width=True)

    box = section("분포 차트", key="distributions")
    with box:
        c1, c2 = st.columns(2)
        with c1:
            st.caption("우선순위 분포")
            pri_df = (
                df["우선순위"].value_counts().reindex(PRIORITY_ORDER).fillna(0).astype(int)
                .rename_axis("우선순위").reset_index(name="건수")
            )
            fig = plotly_bar(pri_df, x="건수", y="우선순위", orientation="h",
                              category_orders={"우선순위": PRIORITY_ORDER},
                              color="우선순위", color_discrete_map=CHART_COLOR)
            st.plotly_chart(fig, use_container_width=True, theme=None, config={"displayModeBar": False})
        with c2:
            st.caption("테스트 유형 분포 (출처별)")
            by_src = df.pivot_table(index="테스트유형", columns="출처",
                                    values="테스트케이스ID", aggfunc="count", fill_value=0)
            for t in TYPE_ORDER:
                if t not in by_src.index:
                    by_src.loc[t] = 0
            by_src_long = by_src.reset_index().melt(id_vars="테스트유형", var_name="출처", value_name="건수")
            SOURCE_DISPLAY = {"기획서기반": "기획서 기반", "AI추가": "AI 추가"}
            by_src_long["출처"] = by_src_long["출처"].map(SOURCE_DISPLAY)
            fig = plotly_bar(by_src_long, x="테스트유형", y="건수", color="출처",
                              category_orders={"테스트유형": TYPE_ORDER,
                                                "출처": [SOURCE_DISPLAY[s] for s in SOURCE_ORDER]},
                              color_discrete_map={SOURCE_DISPLAY[k]: v[1] for k, v in SOURCE_BADGE.items()},
                              barmode="stack")
            st.plotly_chart(fig, use_container_width=True, theme=None, config={"displayModeBar": False})

    box = section("엣지 세부유형 분포 — 실패 클래스 공백 감시", key="edge-dist")
    with box:
        edges = df[df["테스트유형"] == "Edge Case"]
        if len(edges):
            dist_df = (
                edges["엣지세부유형"].value_counts()
                .rename_axis("엣지세부유형").reset_index(name="건수")
            )
            fig = plotly_bar(dist_df, x="건수", y="엣지세부유형", orientation="h",
                              category_orders={"엣지세부유형": EDGE_ORDER},
                              color_discrete_sequence=["#6c5ce7"])
            st.plotly_chart(fig, use_container_width=True, theme=None, config={"displayModeBar": False})
            missing_kinds = set(EDGE_ORDER) - set(dist_df["엣지세부유형"])
            if missing_kinds:
                st.warning(f"엣지 유형 공백: {', '.join(sorted(missing_kinds))} — 해당 실패 클래스 미커버")
            else:
                st.success("엣지 6유형 모두 커버됨 (6/6)")
        else:
            st.info("Edge Case가 없습니다.")

    box = section("글로벌/다국어 커버리지", key="i18n-dist",
                   caption="언어·해외 관련 케이스가 얼마나 있는지 확인합니다.")
    with box:
        n_global = int(df["글로벌관련"].sum())
        if not n_global:
            st.warning("다국어 동시 출시가 목표인데, 다국어/글로벌 관련 케이스가 하나도 없습니다.")
        st.caption(f"다국어/글로벌 관련 케이스 {n_global}건 / 전체 {n_total}건 ({n_global / n_total:.0%})")

# ────────────────────────────────────────────────────────────
# 🚦 릴리즈 게이트 (Challenge) — 라이브 시뮬레이터
# ────────────────────────────────────────────────────────────
with tab_gate:
    box = section("릴리즈 게이트 라이브 시뮬레이터", key="gate-sim",
                   caption="출시 직전 **미해결(테스트 실패)** 케이스 수로 go/no-go를 기계 판정합니다. "
                           "아래에서 P0·P1 케이스의 통과 여부를 토글하면 게이트가 실시간으로 갱신됩니다.")
    with box:
        p1_threshold = st.slider(
            "P1 허용 상한 — 미해결 P1이 이 건수를 초과하면 스프린트 연장 권장으로 전환",
            min_value=0, max_value=10, value=2, key="p1_threshold",
            help="릴리즈마다 리스크 허용치가 다를 수 있어 PM이 직접 조정합니다. "
                 "예: 결제·계정처럼 민감한 출시는 낮게, 커뮤니티 UI 개선은 높게.",
        )
        kpi_slot = st.container()
        verdict_slot = st.container()

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
            flag, status, border_color, note = (
                "🔴", "출시 보류 (Block)", "#e63946",
                f"미해결 P0 {unresolved_p0}건 — 1건이라도 있으면 출시 불가. 핫픽스 후 재검증 필요.",
            )
        elif unresolved_p1 > p1_threshold:
            flag, status, border_color, note = (
                "🟠", "스프린트 연장 권장", "#e76f51",
                f"P0=0 이지만 미해결 P1 {unresolved_p1}건 > 상한 {p1_threshold} → 스프린트 연장 권장.",
            )
        elif unresolved_p1 > 0:
            flag, status, border_color, note = (
                "🟡", "조건부 출시 (Warn)", "#f4a261",
                f"P0=0, 미해결 P1 {unresolved_p1}건(≤{p1_threshold}) — PM 승인 하 출시 + 차기 스프린트 핫픽스 등록.",
            )
        else:
            flag, status, border_color, note = (
                "🟢", "출시 가능 (Pass)", "#2a9d8f",
                "P0=0 AND P1=0 — 정상 출시. P2는 백로그 이관.",
            )

        with kpi_slot:
            g1, g2, g3 = st.columns(3)
            g1.markdown(stat_tile("미해결 P0", f"{unresolved_p0}건", "", "stat-c-red"), unsafe_allow_html=True)
            g2.markdown(stat_tile("미해결 P1", f"{unresolved_p1}건", "", "stat-c-blue"), unsafe_allow_html=True)
            g3.markdown(stat_tile("게이트 상한(P1)", f"≤ {p1_threshold}건", "", "stat-c-gray"), unsafe_allow_html=True)
        with verdict_slot:
            st.markdown(
                verdict_card(flag, status, note, border_color, n_p0, n_p1, n_p2),
                unsafe_allow_html=True,
            )

    box = section("테스트 실행 우선순위 플랜", key="exec-plan")
    with box:
        st.markdown(
            "- **플랜 1 — 출시 차단 P0 우선** (Day 1 오전): P0 전량 일괄 실행. "
            "1건 실패 = 즉시 🔴 보류 확정 → 출시 가부 리드타임 최소화.\n"
            "- **플랜 2 — 이탈·글로벌 P1 회귀** (P0 PASS 후 Day 1 오후): 다국어·다묘·권한 등 "
            "세그먼트 리스크 위주. 미해결 P1이 상한(≤2) 초과 여부가 게이트 입력값."
        )

    box = section("우선순위 점수화 (100점)", key="scoring")
    with box:
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

# ────────────────────────────────────────────────────────────
# 🔁 재현성 (Standard) — v1~v4 비교
# ────────────────────────────────────────────────────────────
with tab_repro:
    box = section("재현성 검증 — 성격이 다른 기획서 4건에 동일 파이프라인 적용", key="repro",
                   caption="건수·P0 비율이 매번 다른 것은 기획서마다 리스크 구조가 다르기 때문. "
                           "규칙(2축 점수·6개 승격·엣지 규칙엔진)은 4건 모두 동일하게 적용됨.")
    with box:
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

        if not rows:
            st.warning("비교할 기획서 CSV를 찾을 수 없습니다. output/ 하위 산출물이 있는지 확인하세요.")
        else:
            repro = pd.DataFrame(rows)
            st.dataframe(repro, use_container_width=True, hide_index=True)

            c1, c2 = st.columns(2)
            with c1:
                st.caption("기획서별 케이스 수")
                fig = plotly_bar(repro, x="기획서", y="총 케이스",
                                  category_orders={"기획서": list(SPECS.keys())},
                                  color_discrete_sequence=[BRAND])
                st.plotly_chart(fig, use_container_width=True, theme=None, config={"displayModeBar": False})
            with c2:
                st.caption("기획서별 P0(블로커) 수 — 도메인마다 리스크 구조가 다름")
                fig = plotly_bar(repro, x="기획서", y="P0",
                                  category_orders={"기획서": list(SPECS.keys())},
                                  color_discrete_sequence=["#6c5ce7"])
                st.plotly_chart(fig, use_container_width=True, theme=None, config={"displayModeBar": False})

st.divider()
st.caption("Petbbi QA Pipeline · 엔트레씨 QA·PM /spec-to-qa 산출물 시각화 · Streamlit")
