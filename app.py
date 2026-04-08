"""
🎯 Dynamic Talent Radar — 동적 인재 레이더
마이리얼트립 TA팀을 위한 채용 마켓 인텔리전스 대시보드

실행: streamlit run app.py --server.port 8502
환경변수: ANTHROPIC_API_KEY (Claude API 키)
"""

import json
import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

import feedparser
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

# ──────────────────────────────────────────────
# 0. 기본 설정 & 상수
# ──────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

TARGETS_FILE = DATA_DIR / "targets.json"
NEWS_CACHE_FILE = DATA_DIR / "news_cache.json"
LINKEDIN_FILE = DATA_DIR / "linkedin_intel.json"
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

DEFAULT_TARGETS = [
    {"name": "아고다", "industry": "여행", "note": "글로벌 OTA, 동남아 강세"},
    {"name": "야놀자", "industry": "여행/숙박", "note": "국내 1위 숙박 플랫폼"},
    {"name": "캐치테이블", "industry": "F&B", "note": "레스토랑 예약 플랫폼"},
    {"name": "배달의민족", "industry": "커머스/딜리버리", "note": "우아한형제들, B2B 영업 강점"},
    {"name": "토스", "industry": "핀테크", "note": "비바리퍼블리카, 공격적 채용"},
    {"name": "무신사", "industry": "패션 커머스", "note": "MZ 패션 플랫폼 1위"},
    {"name": "크림", "industry": "리셀 커머스", "note": "네이버 계열, 한정판 거래"},
    {"name": "채널코퍼레이션", "industry": "SaaS", "note": "채널톡, B2B SaaS 대표주자"},
    {"name": "컬리", "industry": "커머스/식품", "note": "새벽배송, IPO 이후 구조 변화"},
    {"name": "당근", "industry": "로컬 커머스", "note": "당근마켓, 하이퍼로컬 광고"},
]

EXCLUDED_COMPANIES = {"클룩", "klook", "크리에이트립", "creatrip"}

MACRO_KEYWORDS = [
    "시리즈 B", "시리즈 C", "시리즈B", "시리즈C",
    "대규모 투자", "M&A", "유니콘", "구조조정", "희망퇴직",
    "투자 유치", "인수합병", "기업공개", "IPO", "레이오프", "감원",
]

CROSS_INDUSTRY_KEYWORDS = [
    "AI", "핀테크", "SaaS", "모빌리티", "크로스보더 커머스",
    "인공지능", "생성형 AI", "B2B", "클라우드", "블록체인",
]

RSS_FEEDS = [
    ("플래텀", "https://platum.kr/feed"),
    ("벤처스퀘어", "https://www.venturesquare.net/feed"),
    ("아웃스탠딩", "https://outstanding.kr/feed"),
    ("비석세스", "https://www.besuccess.com/feed/"),
    ("IT조선", "https://it.chosun.com/rss/"),
    ("블로터", "https://www.bloter.net/feed"),
    ("지디넷코리아", "https://www.zdnet.co.kr/rss/"),
]

# AI 트렌드 전용 RSS 피드
AI_RSS_FEEDS = [
    ("AI타임스", "https://www.aitimes.com/rss/allArticle.xml"),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
]

# AI 트렌드 키워드 (세분화)
AI_TREND_KEYWORDS = [
    "GPT", "LLM", "생성형 AI", "Generative AI", "AI 에이전트", "AI Agent",
    "RAG", "파인튜닝", "프롬프트", "멀티모달", "Multimodal",
    "AI 채용", "AI 자동화", "AI 도입", "AI 전환", "AX",
    "Claude", "Gemini", "OpenAI", "Anthropic", "Copilot",
    "온디바이스 AI", "AI 반도체", "NPU", "AI SaaS",
    "AI 규제", "AI 윤리", "AI 저작권",
    "ChatGPT", "Llama", "오픈소스 AI",
]

# 회사별 테마 색상
COMPANY_COLORS = {
    "아고다": "#E23744",
    "야놀자": "#FF3478",
    "캐치테이블": "#FF6B35",
    "배달의민족": "#2AC1BC",
    "토스": "#0064FF",
    "무신사": "#000000",
    "크림": "#FF5C00",
    "채널코퍼레이션": "#2962FF",
    "컬리": "#5F0080",
    "당근": "#FF6F0F",
}


# ──────────────────────────────────────────────
# 1. 커스텀 CSS
# ──────────────────────────────────────────────

CUSTOM_CSS = """
<style>
/* 전역 폰트 */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* 메트릭 카드 */
.metric-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px;
    padding: 20px 24px;
    color: white;
    text-align: center;
    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    transition: transform 0.2s;
}
.metric-card:hover { transform: translateY(-2px); }
.metric-card .metric-value {
    font-size: 2.2rem;
    font-weight: 700;
    line-height: 1.2;
}
.metric-card .metric-label {
    font-size: 0.85rem;
    opacity: 0.9;
    margin-top: 4px;
}

.metric-card.blue { background: linear-gradient(135deg, #0064FF 0%, #0047B3 100%); box-shadow: 0 4px 15px rgba(0,100,255,0.3); }
.metric-card.green { background: linear-gradient(135deg, #00C48C 0%, #00A676 100%); box-shadow: 0 4px 15px rgba(0,196,140,0.3); }
.metric-card.orange { background: linear-gradient(135deg, #FF6B35 0%, #E24E1B 100%); box-shadow: 0 4px 15px rgba(255,107,53,0.3); }
.metric-card.red { background: linear-gradient(135deg, #FF3478 0%, #D61C5E 100%); box-shadow: 0 4px 15px rgba(255,52,120,0.3); }

/* 뉴스 카드 */
.news-card {
    background: #ffffff;
    border: 1px solid #e8ecf1;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 10px;
    transition: all 0.2s;
    border-left: 4px solid #667eea;
}
.news-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    border-left-color: #764ba2;
}
.news-card .news-source {
    font-size: 0.75rem;
    color: #8892a4;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.news-card .news-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: #1a1f36;
    margin: 6px 0;
    line-height: 1.4;
}
.news-card .news-title a { color: #1a1f36; text-decoration: none; }
.news-card .news-title a:hover { color: #667eea; }
.news-card .news-tags { margin-top: 8px; }
.news-card .tag {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.72rem;
    font-weight: 600;
    margin-right: 4px;
    margin-bottom: 4px;
}
.tag-company { background: #E8F0FE; color: #1967D2; }
.tag-macro { background: #FFF3E0; color: #E65100; }
.tag-cross { background: #E8F5E9; color: #2E7D32; }

/* 시그널 카드 */
.signal-card {
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 8px;
    border-left: 4px solid;
}
.signal-card.urgent { background: #FFF5F5; border-left-color: #E53E3E; }
.signal-card.watch { background: #FFFAF0; border-left-color: #DD6B20; }
.signal-card.info { background: #F0FFF4; border-left-color: #38A169; }
.signal-card .signal-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: #1a1f36;
}
.signal-card .signal-detail {
    font-size: 0.8rem;
    color: #6b7280;
    margin-top: 4px;
}

/* 회사 바 차트 행 */
.company-bar-row {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
    gap: 10px;
}
.company-bar-name {
    width: 100px;
    font-size: 0.85rem;
    font-weight: 600;
    color: #374151;
    text-align: right;
    flex-shrink: 0;
}
.company-bar-track {
    flex: 1;
    height: 28px;
    background: #f3f4f6;
    border-radius: 6px;
    overflow: hidden;
}
.company-bar-fill {
    height: 100%;
    border-radius: 6px;
    display: flex;
    align-items: center;
    padding-left: 10px;
    font-size: 0.75rem;
    font-weight: 600;
    color: white;
    transition: width 0.5s ease;
    min-width: fit-content;
}

/* 섹션 헤더 */
.section-header {
    font-size: 1.1rem;
    font-weight: 700;
    color: #1a1f36;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid #667eea;
    display: inline-block;
}

/* 리포트 카드 */
.report-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 10px;
}
.report-card .report-date {
    font-size: 0.8rem;
    color: #64748b;
    font-weight: 600;
}

/* 헤더 영역 */
.dashboard-header {
    background: linear-gradient(135deg, #1a1f36 0%, #2d3561 100%);
    border-radius: 16px;
    padding: 28px 32px;
    color: white;
    margin-bottom: 24px;
}
.dashboard-header h1 {
    font-size: 1.6rem;
    font-weight: 700;
    margin: 0;
    color: white;
}
.dashboard-header p {
    font-size: 0.9rem;
    opacity: 0.8;
    margin: 6px 0 0 0;
}

/* LinkedIn 카드 */
.li-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 10px;
    border-left: 4px solid #0A66C2;
}

/* 탭 스타일 */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 8px 20px;
    font-weight: 600;
}

/* 페치 시간 뱃지 */
.fetch-badge {
    display: inline-block;
    background: #EEF2FF;
    color: #4338CA;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
}
</style>
"""


# ──────────────────────────────────────────────
# 2. 데이터 관리
# ──────────────────────────────────────────────

def load_targets() -> list[dict]:
    if not TARGETS_FILE.exists():
        save_targets(DEFAULT_TARGETS)
    with open(TARGETS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_targets(targets: list[dict]):
    with open(TARGETS_FILE, "w", encoding="utf-8") as f:
        json.dump(targets, f, ensure_ascii=False, indent=2)


def load_news_cache() -> dict:
    if NEWS_CACHE_FILE.exists():
        with open(NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"fetched_at": None, "articles": []}


def save_news_cache(cache: dict):
    with open(NEWS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def load_linkedin_intel() -> list[dict]:
    if LINKEDIN_FILE.exists():
        with open(LINKEDIN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_linkedin_intel(data: list[dict]):
    with open(LINKEDIN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────
# 3. 뉴스 수집 엔진
# ──────────────────────────────────────────────

def _article_id(title: str, link: str) -> str:
    return hashlib.md5(f"{title}{link}".encode()).hexdigest()


def _matches_keywords(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _is_excluded(text: str) -> bool:
    text_lower = text.lower()
    return any(exc in text_lower for exc in EXCLUDED_COMPANIES)


def fetch_rss_articles(target_names: list[str], progress_callback=None) -> list[dict]:
    articles = []
    seen_ids = set()

    total = len(RSS_FEEDS)
    for idx, (source_name, feed_url) in enumerate(RSS_FEEDS):
        if progress_callback:
            progress_callback((idx + 1) / total, f"📡 {source_name} 수집 중...")
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:30]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                published = entry.get("published", "")

                summary_clean = BeautifulSoup(summary, "html.parser").get_text()[:500]
                combined_text = f"{title} {summary_clean}"

                aid = _article_id(title, link)
                if aid in seen_ids:
                    continue
                seen_ids.add(aid)

                if _is_excluded(combined_text):
                    continue

                matched_targets = [t for t in target_names if t in combined_text]
                matched_macro = _matches_keywords(combined_text, MACRO_KEYWORDS)
                matched_cross = _matches_keywords(combined_text, CROSS_INDUSTRY_KEYWORDS)

                if matched_targets or matched_macro or matched_cross:
                    articles.append({
                        "id": aid,
                        "source": source_name,
                        "title": title,
                        "link": link,
                        "summary": summary_clean,
                        "published": published,
                        "matched_targets": matched_targets,
                        "matched_macro": matched_macro,
                        "matched_cross": matched_cross,
                        "fetched_at": datetime.now().isoformat(),
                    })
        except Exception as e:
            st.warning(f"⚠️ {source_name} 피드 수집 실패: {e}")

    return articles


def fetch_google_news(target_names: list[str]) -> list[dict]:
    articles = []
    seen_ids = set()

    search_queries = []
    for name in target_names:
        search_queries.append(f"{name} 채용 OR 인재 OR 조직")
        search_queries.append(f"{name} 투자 OR 구조조정 OR 사업확장")
    search_queries.append("스타트업 시리즈B OR 시리즈C OR 투자유치")
    search_queries.append("구조조정 OR 희망퇴직 IT OR 테크 OR 스타트업")

    search_queries.append("AI 에이전트 OR 생성형AI OR LLM 스타트업")

    for query in search_queries[:15]:
        try:
            encoded_q = requests.utils.quote(query)
            feed_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=ko&gl=KR&ceid=KR:ko"
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                published = entry.get("published", "")

                aid = _article_id(title, link)
                if aid in seen_ids:
                    continue
                seen_ids.add(aid)

                if _is_excluded(title):
                    continue

                matched_targets = [t for t in target_names if t in title]
                matched_macro = _matches_keywords(title, MACRO_KEYWORDS)
                matched_cross = _matches_keywords(title, CROSS_INDUSTRY_KEYWORDS)

                if matched_targets or matched_macro or matched_cross:
                    articles.append({
                        "id": aid,
                        "source": "Google News",
                        "title": title,
                        "link": link,
                        "summary": "",
                        "published": published,
                        "matched_targets": matched_targets,
                        "matched_macro": matched_macro,
                        "matched_cross": matched_cross,
                        "fetched_at": datetime.now().isoformat(),
                    })
        except Exception:
            pass

    return articles


def fetch_ai_trend_articles(progress_callback=None) -> list[dict]:
    """AI 트렌드 전용 피드에서 기사 수집"""
    articles = []
    seen_ids = set()

    total = len(AI_RSS_FEEDS)
    for idx, (source_name, feed_url) in enumerate(AI_RSS_FEEDS):
        if progress_callback:
            progress_callback((idx + 1) / total, f"🤖 {source_name} AI 트렌드 수집 중...")
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                published = entry.get("published", "")

                summary_clean = BeautifulSoup(summary, "html.parser").get_text()[:500]
                combined_text = f"{title} {summary_clean}"

                aid = _article_id(title, link)
                if aid in seen_ids:
                    continue
                seen_ids.add(aid)

                matched_ai = _matches_keywords(combined_text, AI_TREND_KEYWORDS)

                if matched_ai:
                    articles.append({
                        "id": aid,
                        "source": source_name,
                        "title": title,
                        "link": link,
                        "summary": summary_clean,
                        "published": published,
                        "matched_targets": [],
                        "matched_macro": [],
                        "matched_cross": [],
                        "matched_ai_trend": matched_ai,
                        "fetched_at": datetime.now().isoformat(),
                    })
        except Exception:
            pass

    return articles


# ──────────────────────────────────────────────
# 4. AI 리포트 생성 (Anthropic Claude API)
# ──────────────────────────────────────────────

def generate_weekly_report(articles: list[dict], targets: list[dict], linkedin_data: list[dict], api_key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    target_news = [a for a in articles if a["matched_targets"]]
    macro_news = [a for a in articles if a["matched_macro"]]
    cross_news = [a for a in articles if a["matched_cross"]]

    def _fmt(arts, max_n=30):
        lines = []
        for a in arts[:max_n]:
            tags = []
            if a["matched_targets"]: tags.append(f"회사: {', '.join(a['matched_targets'])}")
            if a["matched_macro"]: tags.append(f"매크로: {', '.join(a['matched_macro'])}")
            if a["matched_cross"]: tags.append(f"산업: {', '.join(a['matched_cross'])}")
            lines.append(f"- [{a['source']}] {a['title']} ({' | '.join(tags)})")
            if a.get("summary"): lines.append(f"  요약: {a['summary'][:200]}")
        return "\n".join(lines) if lines else "(수집된 기사 없음)"

    li_text = ""
    if linkedin_data:
        li_lines = [f"- [{d.get('signal','')}] {d['title']} ({d.get('company','')}) {d.get('detail','')[:150]}" for d in linkedin_data]
        li_text = "\n".join(li_lines)

    target_details = "\n".join([f"- {t['name']} ({t['industry']}): {t['note']}" for t in targets])
    today = datetime.now()
    week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")

    prompt = f"""당신은 마이리얼트립(여행 테크 기업)의 채용팀을 위한 AI 채용 인텔리전스 분석가입니다.

## 분석 기간: {week_start} ~ {today.strftime("%Y-%m-%d")}

## 타겟 회사 리스트
{target_details}

⚠️ 클룩(Klook), 크리에이트립(Creatrip)은 소싱 타겟에서 절대 제외.

## 수집된 뉴스

### 타겟 회사 관련 ({len(target_news)}건)
{_fmt(target_news)}

### 투자/거시 동향 ({len(macro_news)}건)
{_fmt(macro_news)}

### 타 산업군 ({len(cross_news)}건)
{_fmt(cross_news)}

### LinkedIn 인텔리전스 ({len(linkedin_data)}건)
{li_text if li_text else "(없음)"}

## 리포트 작성 (한국어, 마크다운)

### 📊 1. 타겟 회사 동향
회사별 최신 이슈 + 🛡️ 인재 방어 포인트 + 🎯 소싱 포인트. 기사 없으면 "이번 주 특이사항 없음".

### 💰 2. 거시 투자 기상도
투자 유치, M&A, IPO. "돈과 인재가 몰리는 곳" vs "이탈할 곳". 구조조정 시 BD/영업 인력 동향.

### 🌐 3. 타 산업군 주목할 뉴스
여행업 밖 혁신. 사업개발/영업 인재 소싱에 어떤 의미인지.

### 🎯 4. AI의 소싱 제안
구체적 액션 3~5개. 🔴 긴급 / 🟡 주목 / 🟢 관심 태그. 근거 명시.

리포트 상단에 생성 날짜와 분석 기사 수 표기."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    report = response.content[0].text

    report_path = REPORTS_DIR / f"report_{today.strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    return report


def analyze_signals(articles: list[dict], api_key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    articles_text = "\n".join([f"- [{a['source']}] {a['title']}" for a in articles[:50]])

    prompt = f"""다음 한국 테크/스타트업 뉴스 헤드라인에서 **BD/영업 인재 대규모 이동** 시그널을 찾아주세요.

{articles_text}

판단 기준:
1. 구조조정/희망퇴직/사업 축소 → BD/영업 인재 이탈
2. 대규모 투자 유치 → 공격적 채용, 경쟁사 인재 빼가기
3. M&A 완료 → 중복 조직 통합, 인재 유출
4. 사업 피벗/철수 → 전문가 이직 시장 유입

⚠️ 클룩/크리에이트립 제외.

각 시그널: 🔴/🟡/🟢 태그 + 관련 기사 + 예상 인재 이동 + 마이리얼트립 TA팀 권장 액션.
시그널 없으면 '이번 주기에는 뚜렷한 시그널이 감지되지 않았습니다.'"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ──────────────────────────────────────────────
# 5. UI 헬퍼
# ──────────────────────────────────────────────

def render_metric_card(value, label, color=""):
    color_class = f" {color}" if color else ""
    st.markdown(f"""
    <div class="metric-card{color_class}">
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def render_company_bar(name, count, max_count, color="#667eea"):
    pct = int((count / max_count) * 100) if max_count > 0 else 0
    pct = max(pct, 8)  # 최소 바 너비
    st.markdown(f"""
    <div class="company-bar-row">
        <div class="company-bar-name">{name}</div>
        <div class="company-bar-track">
            <div class="company-bar-fill" style="width:{pct}%; background:{color};">
                {count}건
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_news_card(article):
    tags_html = ""
    for t in article.get("matched_targets", []):
        tags_html += f'<span class="tag tag-company">{t}</span>'
    for kw in article.get("matched_macro", []):
        tags_html += f'<span class="tag tag-macro">{kw}</span>'
    for kw in article.get("matched_cross", []):
        tags_html += f'<span class="tag tag-cross">{kw}</span>'
    for kw in article.get("matched_ai_trend", [])[:3]:
        tags_html += f'<span class="tag" style="background:#FFF5F5;color:#9B1C1C;">{kw}</span>'

    summary_html = ""
    if article.get("summary"):
        summary_html = f'<div style="font-size:0.8rem;color:#6b7280;margin-top:6px;">{article["summary"][:150]}...</div>'

    st.markdown(f"""
    <div class="news-card">
        <div class="news-source">{article['source']}</div>
        <div class="news-title"><a href="{article['link']}" target="_blank">{article['title']}</a></div>
        {summary_html}
        <div class="news-tags">{tags_html}</div>
    </div>
    """, unsafe_allow_html=True)


def render_signal_card(article):
    macro_kws = article.get("matched_macro", [])
    urgency_kws = {"구조조정", "희망퇴직", "레이오프", "감원"}
    has_urgent = any(kw in urgency_kws for kw in macro_kws)
    invest_kws = {"투자 유치", "시리즈 B", "시리즈 C", "시리즈B", "시리즈C", "IPO", "기업공개"}
    has_invest = any(kw in invest_kws for kw in macro_kws)

    if has_urgent:
        card_class = "urgent"
        icon = "🔴"
    elif has_invest:
        card_class = "watch"
        icon = "🟡"
    else:
        card_class = "info"
        icon = "🟢"

    tags = " · ".join(macro_kws)

    st.markdown(f"""
    <div class="signal-card {card_class}">
        <div class="signal-title">{icon} {article['title']}</div>
        <div class="signal-detail">{article['source']} · {tags}</div>
    </div>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 6. 메인 앱
# ──────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Talent Radar",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # ── 사이드바 (설정만) ──
    with st.sidebar:
        st.markdown("### ⚙️ 설정")

        api_key = st.text_input(
            "Anthropic API Key",
            value=os.environ.get("ANTHROPIC_API_KEY", ""),
            type="password",
        )

        st.divider()
        st.markdown("**🏢 타겟 회사 관리**")
        targets = load_targets()

        with st.expander("➕ 새 타겟 회사 추가", expanded=False):
            with st.form("add_target", clear_on_submit=True):
                new_name = st.text_input("회사명")
                new_industry = st.text_input("산업군")
                new_note = st.text_input("비고")
                if st.form_submit_button("추가", use_container_width=True):
                    if new_name:
                        if any(exc in new_name.lower() for exc in EXCLUDED_COMPANIES):
                            st.error("⛔ 클룩/크리에이트립은 제외됩니다.")
                        else:
                            targets.append({"name": new_name, "industry": new_industry, "note": new_note})
                            save_targets(targets)
                            st.rerun()

        for i, t in enumerate(targets):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{t['name']}** · {t.get('industry', '')}")
            with col2:
                if st.button("✕", key=f"del_{i}"):
                    targets.pop(i)
                    save_targets(targets)
                    st.rerun()

        st.divider()
        st.caption("⛔ 소싱 제외: 클룩, 크리에이트립")

    # ── 데이터 로드 ──
    targets = load_targets()
    target_names = [t["name"] for t in targets]
    cache = load_news_cache()
    articles = cache.get("articles", [])
    linkedin_data = load_linkedin_intel()

    fetch_time = cache.get("fetched_at", "")
    fetch_display = fetch_time[:16].replace("T", " ") if fetch_time else "미수집"

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 헤더 + 수집 버튼
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    hdr_left, hdr_right = st.columns([4, 1])
    with hdr_left:
        st.markdown(f"""
        <div class="dashboard-header">
            <h1>🎯 Talent Radar</h1>
            <p>타겟 회사 뉴스 · 투자 동향 · AI 트렌드 · 인재 이동 시그널</p>
            <div style="margin-top:12px;">
                <span class="fetch-badge">마지막 수집: {fetch_display}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with hdr_right:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("🔄 뉴스 수집", use_container_width=True, type="primary"):
            progress = st.progress(0, text="뉴스 수집 준비 중...")
            rss_articles = fetch_rss_articles(target_names, progress_callback=progress.progress)
            progress.progress(0.6, text="📡 Google News 보완 수집 중...")
            google_articles = fetch_google_news(target_names)
            progress.progress(0.8, text="🤖 AI 트렌드 수집 중...")
            ai_articles = fetch_ai_trend_articles()
            all_articles = rss_articles
            seen = {a["id"] for a in all_articles}
            for a in google_articles + ai_articles:
                if a["id"] not in seen:
                    all_articles.append(a)
                    seen.add(a["id"])
            cache = {"fetched_at": datetime.now().isoformat(), "articles": all_articles}
            save_news_cache(cache)
            progress.progress(1.0, text="✅ 수집 완료!")
            st.rerun()

        if api_key:
            if st.button("🤖 리포트 생성", use_container_width=True):
                with st.spinner("Claude 분석 중..."):
                    try:
                        report = generate_weekly_report(articles, targets, linkedin_data, api_key)
                        st.session_state["generated_report"] = report
                        st.rerun()
                    except Exception as e:
                        st.error(f"실패: {e}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 메트릭 카드
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    target_hits = len([a for a in articles if a.get("matched_targets")])
    macro_hits = len([a for a in articles if a.get("matched_macro")])
    ai_hits = len([a for a in articles if a.get("matched_ai_trend")])
    cross_hits = len([a for a in articles if a.get("matched_cross")])

    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    with mc1:
        render_metric_card(f"{len(articles)}", "수집 기사", "blue")
    with mc2:
        render_metric_card(f"{target_hits}", "타겟 회사", "green")
    with mc3:
        render_metric_card(f"{macro_hits}", "투자/매크로", "orange")
    with mc4:
        render_metric_card(f"{ai_hits}", "AI 트렌드", "red")
    with mc5:
        render_metric_card(f"{cross_hits}", "타 산업군", "")

    if not articles:
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("📡 오른쪽 상단 '뉴스 수집' 버튼을 눌러 시작하세요.")
        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🎯 이번 주 소싱 액션 (최상단)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">🎯 이번 주 소싱 액션</div>', unsafe_allow_html=True)

    macro_articles = [a for a in articles if a.get("matched_macro")]
    target_articles = [a for a in articles if a.get("matched_targets")]

    # 시그널 기반 액션 카드 생성
    urgency_kws = {"구조조정", "희망퇴직", "레이오프", "감원"}
    growth_kws = {"투자 유치", "시리즈 B", "시리즈 C", "시리즈B", "시리즈C", "IPO", "기업공개"}

    action_items = []

    # 구조조정/인력이동 시그널 → 긴급 소싱 기회
    for a in macro_articles:
        kws = set(a.get("matched_macro", []))
        targets_in = a.get("matched_targets", [])
        if kws & urgency_kws:
            company = targets_in[0] if targets_in else "업계"
            action_items.append({
                "level": "🔴",
                "class": "urgent",
                "title": f"{company} — 인력 이동 시그널 감지",
                "detail": f"{a['title']} → BD/영업 인재 이탈 가능성. 선제적 커피챗 제안 권장.",
                "source": a["source"],
            })
        elif kws & growth_kws and targets_in:
            company = targets_in[0]
            action_items.append({
                "level": "🟡",
                "class": "watch",
                "title": f"{company} — 투자/IPO 움직임",
                "detail": f"{a['title']} → 공격적 채용 예상. 해당 회사 인재 방어력 강화 시점, 장기 관계 구축 추천.",
                "source": a["source"],
            })

    # 타겟 회사 뉴스량 기반 액션 (기사 5건 이상 = 주목)
    company_counts = {}
    for t in targets:
        count = len([a for a in articles if t["name"] in a.get("matched_targets", [])])
        company_counts[t["name"]] = count

    for name, count in sorted(company_counts.items(), key=lambda x: x[1], reverse=True):
        if count >= 5 and not any(name in item["title"] for item in action_items):
            action_items.append({
                "level": "🟡",
                "class": "watch",
                "title": f"{name} — 뉴스 {count}건 (활발한 움직임)",
                "detail": f"이번 주 {name} 관련 기사가 {count}건으로 많습니다. 조직 변화/사업 확장 시그널을 확인하고 핵심 인재 모니터링을 강화하세요.",
                "source": "뉴스 집계",
            })

    if not action_items:
        action_items.append({
            "level": "🟢",
            "class": "info",
            "title": "특별한 시그널 없음",
            "detail": "이번 주기에는 긴급한 소싱 시그널이 감지되지 않았습니다. 장기 Talent Pool 관리에 집중하세요.",
            "source": "",
        })

    for item in action_items[:6]:
        source_html = f' · {item["source"]}' if item["source"] else ""
        st.markdown(f"""
        <div class="signal-card {item['class']}">
            <div class="signal-title">{item['level']} {item['title']}</div>
            <div class="signal-detail">{item['detail']}{source_html}</div>
        </div>
        """, unsafe_allow_html=True)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📡 Company Radar + 🚨 시그널
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    st.markdown("<br>", unsafe_allow_html=True)
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown('<div class="section-header">📡 Company Radar</div>', unsafe_allow_html=True)

        companies_with_news = {k: v for k, v in company_counts.items() if v > 0}
        if companies_with_news:
            sorted_companies = sorted(companies_with_news.items(), key=lambda x: x[1], reverse=True)
            max_count = sorted_companies[0][1]
            for name, count in sorted_companies:
                color = COMPANY_COLORS.get(name, "#667eea")
                render_company_bar(name, count, max_count, color)
            no_news = [t["name"] for t in targets if t["name"] not in companies_with_news]
            if no_news:
                st.caption(f"뉴스 없음: {', '.join(no_news)}")
        else:
            st.caption("타겟 회사 관련 기사가 없습니다.")

    with col_right:
        st.markdown('<div class="section-header">🚨 투자/매크로 시그널</div>', unsafe_allow_html=True)
        if macro_articles:
            for a in macro_articles[:8]:
                render_signal_card(a)
        else:
            st.caption("감지된 시그널이 없습니다.")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🤖 AI 트렌드
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ai_trend_articles = [a for a in articles if a.get("matched_ai_trend")]
    if ai_trend_articles:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-header">🤖 AI 트렌드</div>', unsafe_allow_html=True)

        ai_kw_counter = Counter()
        for a in ai_trend_articles:
            for kw in a.get("matched_ai_trend", []):
                ai_kw_counter[kw] += 1

        if ai_kw_counter:
            top_kws = ai_kw_counter.most_common(10)
            kw_html = " ".join([
                f'<span style="display:inline-block;background:#FFF5F5;color:#9B1C1C;padding:4px 12px;'
                f'border-radius:16px;font-size:0.78rem;font-weight:600;margin:2px 3px;">'
                f'{kw} ({cnt})</span>'
                for kw, cnt in top_kws
            ])
            st.markdown(f'<div style="margin-bottom:12px;">{kw_html}</div>', unsafe_allow_html=True)

        ai_cols = st.columns(2)
        for idx, a in enumerate(ai_trend_articles[:6]):
            with ai_cols[idx % 2]:
                tags_html = ""
                for kw in a.get("matched_ai_trend", [])[:3]:
                    tags_html += f'<span class="tag" style="background:#FFF5F5;color:#9B1C1C;">{kw}</span>'
                summary_html = ""
                if a.get("summary"):
                    summary_html = f'<div style="font-size:0.8rem;color:#6b7280;margin-top:6px;">{a["summary"][:120]}...</div>'
                st.markdown(f"""
                <div class="news-card" style="border-left-color:#E53E3E;">
                    <div class="news-source">{a['source']}</div>
                    <div class="news-title"><a href="{a['link']}" target="_blank">{a['title']}</a></div>
                    {summary_html}
                    <div class="news-tags">{tags_html}</div>
                </div>
                """, unsafe_allow_html=True)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📰 전체 뉴스 (필터)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">📰 전체 뉴스</div>', unsafe_allow_html=True)

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filter_type = st.multiselect(
            "카테고리",
            ["타겟 회사", "투자/매크로", "타 산업군", "AI 트렌드"],
            default=["타겟 회사", "투자/매크로"],
        )
    with col_f2:
        filter_company = st.multiselect("회사 필터", target_names)
    with col_f3:
        filter_source = st.multiselect("출처 필터", list(set(a["source"] for a in articles)))

    filtered = []
    for a in articles:
        match = False
        if "타겟 회사" in filter_type and a.get("matched_targets"):
            match = True
        if "투자/매크로" in filter_type and a.get("matched_macro"):
            match = True
        if "타 산업군" in filter_type and a.get("matched_cross"):
            match = True
        if "AI 트렌드" in filter_type and a.get("matched_ai_trend"):
            match = True
        if not match:
            continue
        if filter_company and not any(c in a.get("matched_targets", []) for c in filter_company):
            continue
        if filter_source and a["source"] not in filter_source:
            continue
        filtered.append(a)

    st.caption(f"총 {len(filtered)}건")

    news_cols = st.columns(2)
    for idx, a in enumerate(filtered[:30]):
        with news_cols[idx % 2]:
            render_news_card(a)

    if len(filtered) > 30:
        st.caption(f"... 외 {len(filtered) - 30}건")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🏢 회사별 상세 (접기)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">🏢 회사별 상세</div>', unsafe_allow_html=True)

    for t in targets:
        company_articles = [a for a in articles if t["name"] in a.get("matched_targets", [])]
        count = len(company_articles)
        indicator = "⚪" if count == 0 else ("🟢" if count <= 2 else ("🟡" if count <= 5 else "🔴"))

        with st.expander(f"{indicator} {t['name']} ({t.get('industry', '')}) — {count}건", expanded=False):
            if company_articles:
                for a in company_articles[:8]:
                    render_news_card(a)
            else:
                st.caption("관련 기사 없음")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📝 리포트
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">📝 주간 리포트</div>', unsafe_allow_html=True)

    # 생성된 리포트 표시
    if "generated_report" in st.session_state:
        st.markdown(st.session_state["generated_report"])
        st.download_button(
            "📥 리포트 다운로드",
            data=st.session_state["generated_report"],
            file_name=f"talent_radar_{datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown",
        )
        if st.button("리포트 닫기"):
            del st.session_state["generated_report"]
            st.rerun()
    else:
        if not api_key:
            st.caption("사이드바에서 API Key를 입력하면 AI 리포트를 생성할 수 있습니다.")

    # 과거 리포트
    report_files = sorted(REPORTS_DIR.glob("report_*.md"), reverse=True)
    if report_files:
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("과거 리포트")
        for rf in report_files:
            name = rf.stem.replace("report_", "")
            try:
                dt = datetime.strptime(name, "%Y%m%d_%H%M%S")
                display_date = dt.strftime("%Y년 %m월 %d일 %H:%M")
            except ValueError:
                try:
                    dt = datetime.strptime(name, "%Y%m%d")
                    display_date = dt.strftime("%Y년 %m월 %d일")
                except ValueError:
                    display_date = name

            with st.expander(f"📄 {display_date}"):
                content = rf.read_text(encoding="utf-8")
                st.markdown(content)
                st.download_button("📥 다운로드", data=content, file_name=rf.name, mime="text/markdown", key=f"dl_{rf.name}")


if __name__ == "__main__":
    main()
