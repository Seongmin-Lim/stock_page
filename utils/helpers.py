"""
유틸리티 함수 모음
"""
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional
import json


def format_number(value: float, decimals: int = 2) -> str:
    """숫자 포맷팅"""
    if value is None:
        return "N/A"
    
    if abs(value) >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.{decimals}f}T"
    elif abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.{decimals}f}B"
    elif abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.{decimals}f}M"
    elif abs(value) >= 1_000:
        return f"{value / 1_000:.{decimals}f}K"
    else:
        return f"{value:.{decimals}f}"


def format_percent(value: float, decimals: int = 2) -> str:
    """퍼센트 포맷팅"""
    if value is None:
        return "N/A"
    return f"{value * 100:.{decimals}f}%" if abs(value) < 1 else f"{value:.{decimals}f}%"


def format_currency(value: float, currency: str = "USD") -> str:
    """통화 포맷팅"""
    if value is None:
        return "N/A"
    
    symbols = {"USD": "$", "KRW": "₩", "EUR": "€", "JPY": "¥"}
    symbol = symbols.get(currency, currency)
    
    return f"{symbol}{format_number(value)}"


def calculate_change(current: float, previous: float) -> Dict[str, float]:
    """변화량 계산"""
    if previous is None or previous == 0:
        return {"absolute": None, "percent": None}
    
    absolute = current - previous
    percent = (absolute / previous) * 100
    
    return {
        "absolute": round(absolute, 4),
        "percent": round(percent, 2)
    }


def interpret_per(per: Optional[float], industry_avg: float = 20) -> str:
    """PER 해석 (경제 사이클 조정값 반영)
    
    Args:
        per: 분석 대상 PER
        industry_avg: 적정 PER (경제 사이클에 따라 조정된 값 사용 가능)
    """
    if per is None:
        return "데이터 없음"
    
    if per < 0:
        return "적자 (주의 필요)"
    elif per < industry_avg * 0.6:
        return f"저평가 (적정 {industry_avg:.0f} 대비 매력적)"
    elif per < industry_avg * 0.9:
        return f"약간 저평가 (적정: {industry_avg:.0f})"
    elif per < industry_avg * 1.1:
        return "적정 수준"
    elif per < industry_avg * 1.4:
        return f"약간 고평가 (적정: {industry_avg:.0f})"
    else:
        return f"고평가 (적정 {industry_avg:.0f} 대비 주의)"


def interpret_pbr(pbr: Optional[float]) -> str:
    """PBR 해석"""
    if pbr is None:
        return "데이터 없음"
    
    if pbr < 0:
        return "자본잠식 (주의)"
    elif pbr < 1:
        return "저평가 (청산가치 이하)"
    elif pbr < 2:
        return "합리적 수준"
    elif pbr < 4:
        return "성장 프리미엄 포함"
    else:
        return "높은 프리미엄"


def interpret_vix(vix: float) -> Dict[str, str]:
    """VIX 해석"""
    if vix < 12:
        level = "매우 낮음"
        sentiment = "극도의 안정/자만"
        action = "조심스러운 접근 권장"
    elif vix < 17:
        level = "낮음"
        sentiment = "낙관적"
        action = "정상적 투자 지속"
    elif vix < 22:
        level = "보통"
        sentiment = "중립"
        action = "시장 관찰"
    elif vix < 30:
        level = "높음"
        sentiment = "불안"
        action = "방어적 포지션 고려"
    else:
        level = "매우 높음"
        sentiment = "공포"
        action = "역발상 매수 기회 가능"
    
    return {
        "level": level,
        "sentiment": sentiment,
        "action": action,
        "value": vix
    }


def interpret_fear_greed(value: float) -> Dict[str, str]:
    """공포탐욕 지수 해석"""
    if value < 25:
        rating = "극도의 공포"
        contrarian = "매수 기회"
    elif value < 45:
        rating = "공포"
        contrarian = "매수 고려"
    elif value < 55:
        rating = "중립"
        contrarian = "관망"
    elif value < 75:
        rating = "탐욕"
        contrarian = "매도 고려"
    else:
        rating = "극도의 탐욕"
        contrarian = "매도 기회"
    
    return {
        "value": value,
        "rating": rating,
        "contrarian_view": contrarian
    }


def create_summary_table(data: Dict[str, Any]) -> pd.DataFrame:
    """딕셔너리를 요약 테이블로 변환"""
    rows = []
    for key, value in data.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                rows.append({
                    "Category": key,
                    "Metric": sub_key,
                    "Value": sub_value
                })
        else:
            rows.append({
                "Category": "General",
                "Metric": key,
                "Value": value
            })
    
    return pd.DataFrame(rows)


def save_report(data: Dict, filename: str, format: str = "json"):
    """보고서 저장"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if format == "json":
        filepath = f"{filename}_{timestamp}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
    elif format == "csv":
        filepath = f"{filename}_{timestamp}.csv"
        df = create_summary_table(data)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
    
    elif format == "excel":
        filepath = f"{filename}_{timestamp}.xlsx"
        df = create_summary_table(data)
        df.to_excel(filepath, index=False)
    
    return filepath


def validate_ticker(ticker: str) -> bool:
    """티커 유효성 검사"""
    import yfinance as yf
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return 'symbol' in info or 'shortName' in info
    except:
        return False


def get_market_status() -> Dict[str, str]:
    """시장 개장 상태 확인"""
    import pytz
    from datetime import datetime
    
    now = datetime.now(pytz.timezone('America/New_York'))
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute
    
    # 주말 체크
    if weekday >= 5:
        status = "휴장 (주말)"
    # 시간 체크 (9:30 AM - 4:00 PM ET)
    elif (hour == 9 and minute >= 30) or (10 <= hour < 16):
        status = "정규장"
    elif 4 <= hour < 9 or (hour == 9 and minute < 30):
        status = "프리마켓"
    elif 16 <= hour < 20:
        status = "애프터마켓"
    else:
        status = "휴장"
    
    return {
        "status": status,
        "current_time_et": now.strftime("%Y-%m-%d %H:%M:%S ET"),
        "weekday": ["월", "화", "수", "목", "금", "토", "일"][weekday]
    }


if __name__ == "__main__":
    # 테스트
    print("=== 유틸리티 테스트 ===")
    print(f"숫자 포맷: {format_number(1234567890)}")
    print(f"퍼센트 포맷: {format_percent(0.1234)}")
    print(f"통화 포맷: {format_currency(1234567890)}")
    print(f"PER 해석: {interpret_per(25)}")
    print(f"VIX 해석: {interpret_vix(22)}")
    print(f"공포탐욕 해석: {interpret_fear_greed(35)}")
