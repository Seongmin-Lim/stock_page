"""
추가 경제 지표 수집 모듈
============================
주식/ETF 평가를 위한 다양한 경제 지표를 수집합니다.

지표 목록:
1. 금리 스프레드 (2Y-10Y Spread, High Yield Spread)
2. 옵션 시장 (Put/Call Ratio, VIX Term Structure)
3. 달러 인덱스 (DXY)
4. 경기 선행 지표 (ISM PMI, LEI)
5. 심리 지표 (AAII Sentiment, Consumer Sentiment)
6. 밸류에이션 (Shiller CAPE, Buffett Indicator)
7. 크레딧 지표 (IG/HY Spread, TED Spread)
"""

import os
import requests
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import yfinance as yf


@dataclass
class EconomicIndicator:
    """경제 지표 데이터"""
    name: str
    value: float
    unit: str = ""
    date: str = ""
    change: float = 0.0
    signal: str = "neutral"  # bullish, bearish, neutral
    description: str = ""


@dataclass
class MarketIndicators:
    """종합 시장 지표"""
    yield_curve: Dict = field(default_factory=dict)
    credit_spreads: Dict = field(default_factory=dict)
    sentiment: Dict = field(default_factory=dict)
    valuation: Dict = field(default_factory=dict)
    volatility: Dict = field(default_factory=dict)
    dollar: Dict = field(default_factory=dict)
    economic: Dict = field(default_factory=dict)


class FREDClient:
    """
    FRED (Federal Reserve Economic Data) API 클라이언트
    https://fred.stlouisfed.org/docs/api/fred/
    """
    
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
    
    # FRED 시리즈 ID 매핑
    SERIES_IDS = {
        # 금리 관련
        "T10Y2Y": "10Y-2Y Treasury Spread",
        "T10Y3M": "10Y-3M Treasury Spread", 
        "DGS10": "10-Year Treasury Rate",
        "DGS2": "2-Year Treasury Rate",
        "DGS3MO": "3-Month Treasury Rate",
        "DFEDTARU": "Fed Funds Upper Target",
        "DFEDTARL": "Fed Funds Lower Target",
        
        # 크레딧 스프레드
        "BAMLH0A0HYM2": "High Yield Option-Adjusted Spread",
        "BAMLC0A0CM": "Investment Grade Spread",
        "TEDRATE": "TED Spread",
        
        # 경기 지표
        "UMCSENT": "Consumer Sentiment (U. Michigan)",
        "USSLIND": "Leading Economic Index",
        
        # 통화량
        "M2SL": "M2 Money Supply",
        "WALCL": "Fed Balance Sheet (Total Assets)",
        
        # 인플레이션
        "T5YIE": "5-Year Breakeven Inflation",
        "T10YIE": "10-Year Breakeven Inflation",
        "CPIAUCSL": "Consumer Price Index",
        
        # 고용
        "UNRATE": "Unemployment Rate",
        "ICSA": "Initial Jobless Claims",
        "PAYEMS": "Nonfarm Payrolls",
    }
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        
    def is_available(self) -> bool:
        return self.api_key is not None
    
    def get_series(self, series_id: str, limit: int = 5) -> Optional[List[Dict]]:
        """FRED 시리즈 데이터 조회"""
        if not self.api_key:
            return None
            
        try:
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit
            }
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            observations = data.get("observations", [])
            return [
                {"date": obs["date"], "value": float(obs["value"]) if obs["value"] != "." else None}
                for obs in observations if obs.get("value") != "."
            ]
        except Exception as e:
            print(f"⚠️ FRED API 오류 ({series_id}): {e}")
            return None
    
    def get_latest(self, series_id: str) -> Optional[Tuple[float, str]]:
        """최신 값과 날짜 조회"""
        data = self.get_series(series_id, limit=1)
        if data and len(data) > 0:
            return data[0]["value"], data[0]["date"]
        return None, None
    
    def get_with_change(self, series_id: str) -> Optional[Dict]:
        """최신 값과 변화율 조회"""
        data = self.get_series(series_id, limit=5)
        if not data or len(data) < 2:
            return None
        
        current = data[0]["value"]
        previous = data[1]["value"]
        change = ((current - previous) / previous * 100) if previous else 0
        
        return {
            "value": current,
            "previous": previous,
            "change": round(change, 2),
            "date": data[0]["date"]
        }


class YahooFinanceIndicators:
    """Yahoo Finance 기반 시장 지표 수집"""
    
    # ETF/지수 티커 매핑
    TICKERS = {
        # 달러
        "DXY": "DX-Y.NYB",  # Dollar Index
        "UUP": "UUP",       # Dollar Bull ETF
        
        # 금리 ETF (프록시)
        "TLT": "TLT",       # 20+ Year Treasury
        "IEF": "IEF",       # 7-10 Year Treasury
        "SHY": "SHY",       # 1-3 Year Treasury
        
        # 크레딧
        "HYG": "HYG",       # High Yield Corporate Bond
        "LQD": "LQD",       # Investment Grade Corporate Bond
        "JNK": "JNK",       # High Yield Bond
        
        # 변동성
        "VIX": "^VIX",      # VIX Index
        "VVIX": "^VVIX",    # VIX of VIX
        "VXN": "^VXN",      # Nasdaq Volatility
        
        # 옵션 관련
        "PCALL": "^PCALL",  # Put/Call Ratio (종종 작동 안함)
        
        # 원자재
        "GLD": "GLD",       # Gold
        "USO": "USO",       # Oil
        "UNG": "UNG",       # Natural Gas
        
        # 글로벌
        "EEM": "EEM",       # Emerging Markets
        "EFA": "EFA",       # EAFE (Developed ex-US)
        "FXI": "FXI",       # China
    }
    
    @staticmethod
    def get_ticker_data(ticker: str, period: str = "1mo") -> Optional[Dict]:
        """야후 파이낸스에서 티커 데이터 조회"""
        try:
            data = yf.download(ticker, period=period, progress=False)
            if data.empty:
                return None
            
            current = float(data['Close'].iloc[-1])
            prev_close = float(data['Close'].iloc[-2]) if len(data) > 1 else current
            high_52w = float(data['High'].max())
            low_52w = float(data['Low'].min())
            
            return {
                "current": round(current, 2),
                "prev_close": round(prev_close, 2),
                "change_pct": round((current - prev_close) / prev_close * 100, 2),
                "high_52w": round(high_52w, 2),
                "low_52w": round(low_52w, 2),
                "range_position": round((current - low_52w) / (high_52w - low_52w) * 100, 2) if high_52w != low_52w else 50
            }
        except Exception as e:
            print(f"⚠️ Yahoo Finance 오류 ({ticker}): {e}")
            return None
    
    @staticmethod
    def get_vix_term_structure() -> Optional[Dict]:
        """VIX 기간 구조 (콘탱고/백워데이션)"""
        try:
            vix = yf.download("^VIX", period="5d", progress=False)
            # VIX 선물 ETF들로 기간구조 추정
            vxx = yf.download("VXX", period="5d", progress=False)  # Short-term
            vxz = yf.download("VIXM", period="5d", progress=False) # Mid-term
            
            if vix.empty:
                return None
            
            vix_current = float(vix['Close'].iloc[-1])
            
            result = {"spot_vix": round(vix_current, 2)}
            
            if not vxx.empty:
                vxx_current = float(vxx['Close'].iloc[-1])
                result["vxx"] = round(vxx_current, 2)
            
            if not vxz.empty:
                vxz_current = float(vxz['Close'].iloc[-1])
                result["vixm"] = round(vxz_current, 2)
            
            # 콘탱고/백워데이션 판단 (단순화)
            if vix_current < 15:
                result["structure"] = "Contango (정상: 낮은 단기 변동성)"
                result["signal"] = "bullish"
            elif vix_current > 25:
                result["structure"] = "Backwardation 가능 (높은 단기 공포)"
                result["signal"] = "bearish"
            else:
                result["structure"] = "Normal"
                result["signal"] = "neutral"
            
            return result
        except Exception as e:
            print(f"⚠️ VIX 기간구조 오류: {e}")
            return None


class PutCallRatio:
    """Put/Call Ratio 수집 (CBOE)"""
    
    @staticmethod
    def estimate_from_options() -> Optional[Dict]:
        """SPY 옵션으로 Put/Call 추정 (간접 방법)"""
        try:
            spy = yf.Ticker("SPY")
            
            # 가장 가까운 만기의 옵션 체인
            expirations = spy.options
            if not expirations:
                return None
            
            nearest_exp = expirations[0]
            chain = spy.option_chain(nearest_exp)
            
            calls_volume = chain.calls['volume'].sum()
            puts_volume = chain.puts['volume'].sum()
            
            calls_oi = chain.calls['openInterest'].sum()
            puts_oi = chain.puts['openInterest'].sum()
            
            pc_ratio_volume = puts_volume / calls_volume if calls_volume > 0 else 1
            pc_ratio_oi = puts_oi / calls_oi if calls_oi > 0 else 1
            
            # 해석
            if pc_ratio_volume < 0.7:
                signal = "bearish"  # 과도한 낙관
                interpretation = "콜 과잉 - 시장 과열 우려"
            elif pc_ratio_volume > 1.0:
                signal = "bullish"  # 과도한 비관 (역발상)
                interpretation = "풋 과잉 - 역발상 매수 신호"
            else:
                signal = "neutral"
                interpretation = "균형 상태"
            
            return {
                "pc_ratio_volume": round(pc_ratio_volume, 3),
                "pc_ratio_oi": round(pc_ratio_oi, 3),
                "calls_volume": int(calls_volume),
                "puts_volume": int(puts_volume),
                "expiration": nearest_exp,
                "signal": signal,
                "interpretation": interpretation
            }
        except Exception as e:
            print(f"⚠️ Put/Call Ratio 오류: {e}")
            return None


class MarketValuation:
    """시장 밸류에이션 지표"""
    
    @staticmethod
    def get_sp500_pe() -> Optional[Dict]:
        """S&P 500 P/E Ratio (yfinance에서 추정)"""
        try:
            spy = yf.Ticker("SPY")
            info = spy.info
            
            # ETF 정보에서 추정
            pe = info.get("trailingPE") or info.get("forwardPE")
            
            if pe:
                if pe > 25:
                    signal = "bearish"
                    interpretation = "고평가 영역"
                elif pe < 15:
                    signal = "bullish"
                    interpretation = "저평가 영역"
                else:
                    signal = "neutral"
                    interpretation = "적정 수준"
                
                return {
                    "pe_ratio": round(pe, 2),
                    "signal": signal,
                    "interpretation": interpretation
                }
            return None
        except Exception as e:
            print(f"⚠️ S&P 500 P/E 오류: {e}")
            return None
    
    @staticmethod
    def get_equity_risk_premium(risk_free_rate: float = 4.5) -> Optional[Dict]:
        """주식 리스크 프리미엄 추정"""
        try:
            spy = yf.Ticker("SPY")
            info = spy.info
            
            # 배당수익률 + 예상 성장률 - 무위험 이자율
            div_yield = info.get("dividendYield", 0) or 0
            div_yield_pct = div_yield * 100 if div_yield < 1 else div_yield
            
            # 간단한 Gordon 모델 기반 추정
            # 주식 기대수익률 = 배당수익률 + 예상 성장률 (약 5% 가정)
            expected_return = div_yield_pct + 5
            erp = expected_return - risk_free_rate
            
            if erp > 5:
                signal = "bullish"
                interpretation = "주식이 상대적으로 매력적"
            elif erp < 2:
                signal = "bearish"
                interpretation = "채권 대비 주식 매력도 낮음"
            else:
                signal = "neutral"
                interpretation = "적정 수준"
            
            return {
                "equity_risk_premium": round(erp, 2),
                "dividend_yield": round(div_yield_pct, 2),
                "risk_free_rate": risk_free_rate,
                "signal": signal,
                "interpretation": interpretation
            }
        except Exception as e:
            print(f"⚠️ ERP 오류: {e}")
            return None


class EconomicIndicatorsCollector:
    """
    종합 경제 지표 수집기
    ========================
    다양한 소스에서 경제/시장 지표를 수집하여 통합 제공
    """
    
    def __init__(self, fred_api_key: str = None):
        self.fred = FREDClient(fred_api_key)
        self.yahoo = YahooFinanceIndicators()
        self.pc_ratio = PutCallRatio()
        self.valuation = MarketValuation()
    
    def collect_yield_curve(self) -> Dict:
        """수익률 곡선 지표"""
        result = {}
        
        # FRED에서 금리 스프레드
        if self.fred.is_available():
            spread_10y2y = self.fred.get_with_change("T10Y2Y")
            if spread_10y2y:
                value = spread_10y2y["value"]
                result["10Y-2Y_spread"] = {
                    **spread_10y2y,
                    "signal": "bearish" if value < 0 else ("warning" if value < 0.5 else "neutral"),
                    "interpretation": "역전 (경기침체 신호)" if value < 0 else ("평탄화 (경고)" if value < 0.5 else "정상")
                }
            
            spread_10y3m = self.fred.get_with_change("T10Y3M")
            if spread_10y3m:
                value = spread_10y3m["value"]
                result["10Y-3M_spread"] = {
                    **spread_10y3m,
                    "signal": "bearish" if value < 0 else "neutral"
                }
            
            # 10년 금리
            rate_10y = self.fred.get_with_change("DGS10")
            if rate_10y:
                result["10Y_rate"] = rate_10y
            
            # 2년 금리
            rate_2y = self.fred.get_with_change("DGS2")
            if rate_2y:
                result["2Y_rate"] = rate_2y
        
        return result
    
    def collect_credit_spreads(self) -> Dict:
        """크레딧 스프레드 지표"""
        result = {}
        
        if self.fred.is_available():
            # 하이일드 스프레드
            hy_spread = self.fred.get_with_change("BAMLH0A0HYM2")
            if hy_spread:
                value = hy_spread["value"]
                result["high_yield_spread"] = {
                    **hy_spread,
                    "signal": "bearish" if value > 5 else ("warning" if value > 4 else "neutral"),
                    "interpretation": "크레딧 위험 상승" if value > 5 else "정상"
                }
            
            # 투자등급 스프레드
            ig_spread = self.fred.get_with_change("BAMLC0A0CM")
            if ig_spread:
                result["investment_grade_spread"] = ig_spread
            
            # TED 스프레드
            ted = self.fred.get_with_change("TEDRATE")
            if ted:
                result["ted_spread"] = ted
        
        # HYG-LQD 스프레드 (ETF 기반)
        hyg = self.yahoo.get_ticker_data("HYG", "1mo")
        lqd = self.yahoo.get_ticker_data("LQD", "1mo")
        if hyg and lqd:
            # 간접적인 크레딧 리스크 지표
            result["hyg_lqd_ratio"] = {
                "hyg_price": hyg["current"],
                "lqd_price": lqd["current"],
                "hyg_change": hyg["change_pct"],
                "lqd_change": lqd["change_pct"]
            }
        
        return result
    
    def collect_sentiment(self) -> Dict:
        """심리 지표"""
        result = {}
        
        # FRED 소비자 심리
        if self.fred.is_available():
            consumer = self.fred.get_with_change("UMCSENT")
            if consumer:
                value = consumer["value"]
                result["consumer_sentiment"] = {
                    **consumer,
                    "signal": "bullish" if value > 100 else ("bearish" if value < 70 else "neutral"),
                    "interpretation": "소비자 낙관" if value > 100 else ("소비자 비관" if value < 70 else "보통")
                }
        
        # Put/Call Ratio
        pc = self.pc_ratio.estimate_from_options()
        if pc:
            result["put_call_ratio"] = pc
        
        return result
    
    def collect_valuation(self) -> Dict:
        """밸류에이션 지표"""
        result = {}
        
        # S&P 500 P/E
        pe = self.valuation.get_sp500_pe()
        if pe:
            result["sp500_pe"] = pe
        
        # 주식 리스크 프리미엄
        erp = self.valuation.get_equity_risk_premium()
        if erp:
            result["equity_risk_premium"] = erp
        
        return result
    
    def collect_volatility(self) -> Dict:
        """변동성 지표"""
        result = {}
        
        # VIX
        vix = self.yahoo.get_ticker_data("^VIX", "1mo")
        if vix:
            value = vix["current"]
            result["vix"] = {
                **vix,
                "signal": "bearish" if value > 25 else ("bullish" if value < 15 else "neutral"),
                "interpretation": "공포 구간" if value > 25 else ("탐욕 구간" if value < 15 else "보통")
            }
        
        # VIX 기간구조
        term = self.yahoo.get_vix_term_structure()
        if term:
            result["vix_term_structure"] = term
        
        return result
    
    def collect_dollar(self) -> Dict:
        """달러 지표"""
        result = {}
        
        # DXY (달러 인덱스)
        dxy = self.yahoo.get_ticker_data("DX-Y.NYB", "3mo")
        if dxy:
            value = dxy["current"]
            result["dxy"] = {
                **dxy,
                "signal": "bearish" if value > 105 else ("bullish" if value < 95 else "neutral"),
                "interpretation": "강달러 (신흥국 부담)" if value > 105 else ("약달러 (위험자산 우호)" if value < 95 else "보통")
            }
        
        # UUP (달러 ETF)
        uup = self.yahoo.get_ticker_data("UUP", "1mo")
        if uup:
            result["uup"] = uup
        
        return result
    
    def collect_economic(self) -> Dict:
        """경제 지표"""
        result = {}
        
        if self.fred.is_available():
            # 실업률
            unemployment = self.fred.get_with_change("UNRATE")
            if unemployment:
                result["unemployment_rate"] = unemployment
            
            # 실업수당 청구
            claims = self.fred.get_with_change("ICSA")
            if claims:
                result["initial_claims"] = claims
            
            # M2 통화량
            m2 = self.fred.get_with_change("M2SL")
            if m2:
                result["m2_money_supply"] = m2
            
            # 연준 대차대조표
            fed_bs = self.fred.get_with_change("WALCL")
            if fed_bs:
                result["fed_balance_sheet"] = fed_bs
            
            # 기대 인플레이션
            bei_5y = self.fred.get_with_change("T5YIE")
            if bei_5y:
                result["breakeven_inflation_5y"] = bei_5y
        
        return result
    
    def collect_all(self) -> MarketIndicators:
        """모든 지표 수집"""
        print("📊 경제 지표 수집 중...")
        
        indicators = MarketIndicators()
        indicators.yield_curve = self.collect_yield_curve()
        indicators.credit_spreads = self.collect_credit_spreads()
        indicators.sentiment = self.collect_sentiment()
        indicators.valuation = self.collect_valuation()
        indicators.volatility = self.collect_volatility()
        indicators.dollar = self.collect_dollar()
        indicators.economic = self.collect_economic()
        
        print("✅ 경제 지표 수집 완료")
        return indicators
    
    def get_market_summary(self) -> Dict:
        """시장 요약 (빠른 조회용)"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "indicators": {}
        }
        
        # VIX
        vix = self.yahoo.get_ticker_data("^VIX", "5d")
        if vix:
            summary["indicators"]["vix"] = vix["current"]
        
        # Put/Call
        pc = self.pc_ratio.estimate_from_options()
        if pc:
            summary["indicators"]["put_call_ratio"] = pc["pc_ratio_volume"]
        
        # DXY
        dxy = self.yahoo.get_ticker_data("DX-Y.NYB", "5d")
        if dxy:
            summary["indicators"]["dxy"] = dxy["current"]
        
        # 금리 스프레드 (FRED 필요)
        if self.fred.is_available():
            spread, date = self.fred.get_latest("T10Y2Y")
            if spread is not None:
                summary["indicators"]["yield_spread_10y2y"] = spread
        
        return summary
    
    def get_signal_summary(self) -> Dict:
        """신호 요약 (Bullish/Bearish 카운트)"""
        all_indicators = self.collect_all()
        
        signals = {"bullish": 0, "bearish": 0, "neutral": 0, "warning": 0}
        details = []
        
        # 모든 지표에서 시그널 추출
        for category_name in ["yield_curve", "credit_spreads", "sentiment", "valuation", "volatility", "dollar"]:
            category = getattr(all_indicators, category_name, {})
            for name, data in category.items():
                if isinstance(data, dict) and "signal" in data:
                    signal = data["signal"]
                    signals[signal] = signals.get(signal, 0) + 1
                    details.append({
                        "category": category_name,
                        "indicator": name,
                        "signal": signal,
                        "value": data.get("value", data.get("current", "N/A"))
                    })
        
        total = sum(signals.values())
        
        # 종합 판단
        if signals["bullish"] > signals["bearish"] + signals["warning"]:
            overall = "BULLISH"
        elif signals["bearish"] + signals["warning"] > signals["bullish"]:
            overall = "BEARISH"
        else:
            overall = "NEUTRAL"
        
        return {
            "overall_signal": overall,
            "signal_counts": signals,
            "total_indicators": total,
            "bullish_ratio": round(signals["bullish"] / total * 100, 1) if total > 0 else 0,
            "details": details
        }


# 편의 함수
def get_economic_indicators(fred_api_key: str = None) -> MarketIndicators:
    """경제 지표 수집 (편의 함수)"""
    collector = EconomicIndicatorsCollector(fred_api_key)
    return collector.collect_all()


def get_market_signal_summary(fred_api_key: str = None) -> Dict:
    """시장 신호 요약 (편의 함수)"""
    collector = EconomicIndicatorsCollector(fred_api_key)
    return collector.get_signal_summary()


def get_quick_indicators() -> Dict:
    """빠른 핵심 지표 조회 (API 키 불필요)"""
    yahoo = YahooFinanceIndicators()
    pc = PutCallRatio()
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "vix": yahoo.get_ticker_data("^VIX", "5d"),
        "dxy": yahoo.get_ticker_data("DX-Y.NYB", "5d"),
        "put_call": pc.estimate_from_options(),
        "gold": yahoo.get_ticker_data("GLD", "5d"),
        "tlt": yahoo.get_ticker_data("TLT", "5d"),  # 장기채
        "hyg": yahoo.get_ticker_data("HYG", "5d"),  # 하이일드
    }
    
    return result


if __name__ == "__main__":
    print("="*60)
    print("📊 경제 지표 수집 모듈 테스트")
    print("="*60)
    
    # 빠른 지표 (API 키 불필요)
    print("\n🚀 빠른 핵심 지표:")
    quick = get_quick_indicators()
    for name, data in quick.items():
        if isinstance(data, dict) and data:
            print(f"  {name}: {data.get('current', data.get('pc_ratio_volume', 'N/A'))}")
    
    # FRED API가 있으면 전체 수집
    if os.getenv("FRED_API_KEY"):
        print("\n📈 전체 지표 수집 (FRED API 사용):")
        collector = EconomicIndicatorsCollector()
        summary = collector.get_signal_summary()
        print(f"  종합 신호: {summary['overall_signal']}")
        print(f"  Bullish: {summary['signal_counts']['bullish']}")
        print(f"  Bearish: {summary['signal_counts']['bearish']}")
    else:
        print("\n⚠️ FRED_API_KEY가 없어 일부 지표는 수집되지 않습니다.")
        print("   https://fred.stlouisfed.org/docs/api/api_key.html 에서 무료 API 키 발급")
