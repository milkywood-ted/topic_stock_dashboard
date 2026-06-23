"""
종목 마스터 초기 데이터
conversation에서 정리된 AI 수혜 기업 리스트
"""

INITIAL_STOCKS = [
    # ── 1차 수혜 ─────────────────────────────────────────
    {"ticker": "NVDA",   "name": "NVIDIA",               "tier": "1차", "sector": "GPU·AI칩",        "market": "US"},
    {"ticker": "AVGO",   "name": "Broadcom",              "tier": "1차", "sector": "AI ASIC·네트워크", "market": "US"},
    {"ticker": "AMD",    "name": "Advanced Micro Devices","tier": "1차", "sector": "GPU·CPU",          "market": "US"},
    {"ticker": "MU",     "name": "Micron Technology",     "tier": "1차", "sector": "HBM·메모리",       "market": "US"},
    {"ticker": "TSM",    "name": "TSMC (ADR)",            "tier": "1차", "sector": "파운드리",          "market": "US"},
    {"ticker": "ANET",   "name": "Arista Networks",       "tier": "1차", "sector": "DC 네트워크",       "market": "US"},
    {"ticker": "MRVL",   "name": "Marvell Technology",    "tier": "1차", "sector": "광통신·AI ASIC",   "market": "US"},
    {"ticker": "VRT",    "name": "Vertiv Holdings",       "tier": "1차", "sector": "전력·냉각 인프라",  "market": "US"},
    {"ticker": "SMCI",   "name": "Super Micro Computer",  "tier": "1차", "sector": "AI 서버",           "market": "US"},
    {"ticker": "DELL",   "name": "Dell Technologies",     "tier": "1차", "sector": "AI 서버·인프라",    "market": "US"},
    {"ticker": "CEG",    "name": "Constellation Energy",  "tier": "1차", "sector": "원전·전력",         "market": "US"},
    {"ticker": "NEE",    "name": "NextEra Energy",        "tier": "1차", "sector": "재생에너지",         "market": "US"},
    {"ticker": "EQIX",   "name": "Equinix",               "tier": "1차", "sector": "데이터센터 리츠",   "market": "US"},
    # 한국 1차 (yfinance 티커 형식)
    {"ticker": "000660.KS", "name": "SK하이닉스",         "tier": "1차", "sector": "HBM 메모리",        "market": "KR"},
    {"ticker": "005930.KS", "name": "삼성전자",            "tier": "1차", "sector": "반도체·HBM",        "market": "KR"},
    {"ticker": "042700.KS", "name": "한미반도체",          "tier": "1차", "sector": "반도체 장비",        "market": "KR"},
    {"ticker": "095340.KS", "name": "ISC",                "tier": "1차", "sector": "반도체 테스트",      "market": "KR"},
    {"ticker": "006400.KS", "name": "삼성SDI",             "tier": "1차", "sector": "전력·배터리",        "market": "KR"},

    # ── 2차 수혜 ─────────────────────────────────────────
    {"ticker": "MSFT",   "name": "Microsoft",             "tier": "2차", "sector": "클라우드·Copilot",  "market": "US"},
    {"ticker": "GOOGL",  "name": "Alphabet",              "tier": "2차", "sector": "검색·클라우드 AI",  "market": "US"},
    {"ticker": "AMZN",   "name": "Amazon",                "tier": "2차", "sector": "AWS·커머스 AI",     "market": "US"},
    {"ticker": "META",   "name": "Meta Platforms",        "tier": "2차", "sector": "소셜 AI·광고",      "market": "US"},
    {"ticker": "PLTR",   "name": "Palantir Technologies", "tier": "2차", "sector": "AI 플랫폼·데이터",  "market": "US"},
    {"ticker": "CRWD",   "name": "CrowdStrike",           "tier": "2차", "sector": "AI 사이버보안",      "market": "US"},
    {"ticker": "NOW",    "name": "ServiceNow",            "tier": "2차", "sector": "AI 워크플로우",      "market": "US"},
    {"ticker": "SNOW",   "name": "Snowflake",             "tier": "2차", "sector": "AI 데이터 클라우드", "market": "US"},
    {"ticker": "NET",    "name": "Cloudflare",            "tier": "2차", "sector": "엣지 AI·보안",       "market": "US"},
    {"ticker": "PANW",   "name": "Palo Alto Networks",    "tier": "2차", "sector": "제로트러스트 보안",  "market": "US"},
    {"ticker": "CRM",    "name": "Salesforce",            "tier": "2차", "sector": "CRM AI",             "market": "US"},
    {"ticker": "DDOG",   "name": "Datadog",               "tier": "2차", "sector": "AI 모니터링",        "market": "US"},
    {"ticker": "ISRG",   "name": "Intuitive Surgical",    "tier": "2차", "sector": "AI 수술로봇",        "market": "US"},
    {"ticker": "V",      "name": "Visa",                  "tier": "2차", "sector": "AI 결제·금융",       "market": "US"},
    # 한국 2차
    {"ticker": "035720.KS", "name": "카카오",              "tier": "2차", "sector": "AI 플랫폼",          "market": "KR"},
    {"ticker": "035420.KS", "name": "NAVER",               "tier": "2차", "sector": "검색·클라우드 AI",  "market": "KR"},
    {"ticker": "066570.KS", "name": "LG전자",              "tier": "2차", "sector": "AI 가전·로봇",       "market": "KR"},

    # ── 3차 수혜 ─────────────────────────────────────────
    {"ticker": "TSLA",   "name": "Tesla",                 "tier": "3차", "sector": "AI 로봇·자율주행",   "market": "US"},
    {"ticker": "MBLY",   "name": "Mobileye",              "tier": "3차", "sector": "자율주행 AI칩",       "market": "US"},
    {"ticker": "PATH",   "name": "UiPath",                "tier": "3차", "sector": "RPA·AI 자동화",       "market": "US"},
    # 한국 3차
    {"ticker": "277810.KS", "name": "레인보우로보틱스",    "tier": "3차", "sector": "협동로봇",            "market": "KR"},
    {"ticker": "454910.KS", "name": "두산로보틱스",        "tier": "3차", "sector": "산업용 로봇",         "market": "KR"},
    {"ticker": "003490.KS", "name": "대한항공",            "tier": "3차", "sector": "SAF·물류 AI",         "market": "KR"},
]
