"""
설정 파일 - API 키 및 기본 설정
"""
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# 분석 대상 티커
DEFAULT_TICKERS = {
    "indices": {
        "^VIX": "VIX 변동성 지수",
        "^GSPC": "S&P 500",
        "^DJI": "다우존스",
        "^IXIC": "나스닥",
        "^TNX": "10년 국채 금리",
    },
    "etfs": {
        "SPY": "S&P 500 ETF",
        "QQQ": "나스닥 100 ETF",
        "IWM": "러셀 2000 ETF",
    }
}

# 분석 기간 설정
DEFAULT_PERIOD = "1y"  # 1년
DEFAULT_INTERVAL = "1d"  # 일봉

# AI 모델 설정
AI_MODEL = "grok-beta"  # 기본 모델
AI_PROVIDER = "grok"    # 기본 제공자: grok, gemini, openai, anthropic

# 공포탐욕 지수 기준값 (기본값 - 경제 사이클에 따라 조정됨)
FEAR_GREED_THRESHOLDS = {
    "extreme_fear": 25,
    "fear": 45,
    "neutral": 55,
    "greed": 75,
    "extreme_greed": 100
}

# PER/PBR 기준값 (기본값 - 경제 사이클에 따라 조정됨)
VALUATION_BENCHMARKS = {
    "per_low": 15,
    "per_avg": 20,
    "per_high": 25,
    "pbr_low": 2.5,
    "pbr_avg": 3.5,
    "pbr_high": 4.5,
}

# ============================================================
# 섹터/시가총액별 PER/PBR 기준값 (종목별 맥락 적용)
# ============================================================
SECTOR_VALUATION_BENCHMARKS = {
    # 메가캡 기술주 (AAPL, MSFT, GOOGL, NVDA, META 등)
    "mega_cap_tech": {
        "name": "메가캡 기술주",
        "market_cap_min": 500_000_000_000,  # 5000억$ 이상
        "per": {"low": 20, "avg": 30, "high": 45},  # 높은 PER 허용
        "pbr": {"low": 5, "avg": 10, "high": 20},
        "examples": ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "AMZN"],
    },
    # 고성장 기술주 (소형~중형 성장주)
    "growth_tech": {
        "name": "고성장 기술주",
        "growth_rate_min": 0.20,  # 매출 성장률 20% 이상
        "per": {"low": 25, "avg": 40, "high": 80},  # 매우 높은 PER 허용
        "pbr": {"low": 3, "avg": 8, "high": 15},
        "examples": ["PLTR", "SNOW", "NET", "DDOG", "CRWD"],
    },
    # 전통 기술주 (성숙한 IT)
    "mature_tech": {
        "name": "성숙 기술주",
        "per": {"low": 12, "avg": 18, "high": 25},
        "pbr": {"low": 2, "avg": 4, "high": 7},
        "examples": ["INTC", "CSCO", "IBM", "HPQ", "ORCL"],
    },
    # 금융 섹터
    "financials": {
        "name": "금융",
        "per": {"low": 8, "avg": 12, "high": 18},
        "pbr": {"low": 0.8, "avg": 1.2, "high": 2.0},  # 금융은 PBR 중요
        "examples": ["JPM", "BAC", "WFC", "C", "GS", "MS"],
    },
    # 헬스케어/바이오
    "healthcare": {
        "name": "헬스케어",
        "per": {"low": 15, "avg": 22, "high": 35},
        "pbr": {"low": 2, "avg": 4, "high": 8},
        "examples": ["JNJ", "UNH", "PFE", "ABBV", "LLY", "MRK"],
    },
    # 에너지
    "energy": {
        "name": "에너지",
        "per": {"low": 6, "avg": 10, "high": 15},  # 낮은 PER
        "pbr": {"low": 1, "avg": 1.5, "high": 2.5},
        "examples": ["XOM", "CVX", "COP", "SLB", "EOG"],
    },
    # 유틸리티/리츠 (배당주)
    "defensive": {
        "name": "방어주/배당주",
        "per": {"low": 12, "avg": 18, "high": 25},
        "pbr": {"low": 1.5, "avg": 2.5, "high": 4},
        "examples": ["NEE", "DUK", "SO", "O", "AMT", "PLD"],
    },
    # 소비재/리테일
    "consumer": {
        "name": "소비재",
        "per": {"low": 15, "avg": 22, "high": 30},
        "pbr": {"low": 3, "avg": 6, "high": 12},
        "examples": ["WMT", "COST", "TGT", "HD", "NKE", "MCD"],
    },
    # 산업재
    "industrials": {
        "name": "산업재",
        "per": {"low": 12, "avg": 18, "high": 25},
        "pbr": {"low": 2, "avg": 4, "high": 7},
        "examples": ["CAT", "DE", "HON", "UNP", "BA", "GE"],
    },
    # 기본값 (분류 불가 시)
    "default": {
        "name": "일반",
        "per": {"low": 15, "avg": 20, "high": 25},
        "pbr": {"low": 2.5, "avg": 3.5, "high": 4.5},
        "examples": [],
    },
}

def get_valuation_benchmark(ticker: str, market_cap: float = None, growth_rate: float = None) -> dict:
    """
    종목의 섹터/시가총액에 따른 적절한 PER/PBR 기준값 반환
    
    Args:
        ticker: 종목 티커
        market_cap: 시가총액 (optional)
        growth_rate: 매출 성장률 (optional)
    
    Returns:
        dict: {"per": {"low", "avg", "high"}, "pbr": {"low", "avg", "high"}, "category": str}
    """
    ticker = ticker.upper()
    
    # 1. 메가캡 기술주 체크
    if ticker in SECTOR_VALUATION_BENCHMARKS["mega_cap_tech"]["examples"]:
        bench = SECTOR_VALUATION_BENCHMARKS["mega_cap_tech"]
        return {"per": bench["per"], "pbr": bench["pbr"], "category": bench["name"]}
    
    # 2. 시가총액으로 메가캡 판별
    if market_cap and market_cap >= 500_000_000_000:  # 5000억$ 이상
        bench = SECTOR_VALUATION_BENCHMARKS["mega_cap_tech"]
        return {"per": bench["per"], "pbr": bench["pbr"], "category": bench["name"]}
    
    # 3. 고성장주 체크
    if ticker in SECTOR_VALUATION_BENCHMARKS["growth_tech"]["examples"]:
        bench = SECTOR_VALUATION_BENCHMARKS["growth_tech"]
        return {"per": bench["per"], "pbr": bench["pbr"], "category": bench["name"]}
    
    if growth_rate and growth_rate >= 0.20:
        bench = SECTOR_VALUATION_BENCHMARKS["growth_tech"]
        return {"per": bench["per"], "pbr": bench["pbr"], "category": bench["name"]}
    
    # 4. 섹터별 매칭
    for sector_key, sector_data in SECTOR_VALUATION_BENCHMARKS.items():
        if sector_key in ["mega_cap_tech", "growth_tech", "default"]:
            continue
        if ticker in sector_data.get("examples", []):
            return {"per": sector_data["per"], "pbr": sector_data["pbr"], "category": sector_data["name"]}
    
    # 5. 기본값
    bench = SECTOR_VALUATION_BENCHMARKS["default"]
    return {"per": bench["per"], "pbr": bench["pbr"], "category": bench["name"]}

# 경제 사이클별 기준값 조정 계수
ECONOMIC_CYCLE_ADJUSTMENTS = {
    "회복기": {"per": 0.9, "vix": 1.2, "fear_greed": 1.0},
    "확장기": {"per": 1.0, "vix": 1.0, "fear_greed": 1.0},
    "과열기": {"per": 1.1, "vix": 0.8, "fear_greed": 0.9},
    "수축기": {"per": 0.85, "vix": 1.3, "fear_greed": 1.1},
    "침체기": {"per": 0.8, "vix": 1.5, "fear_greed": 1.2},
}

# 보고서 저장 설정
REPORT_OUTPUT_DIR = "reports"
SAVE_REPORTS = True  # 모든 분석 결과 자동 저장
