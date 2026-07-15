"""
시장 데이터 수집 모듈
VIX, 10Y 금리, S&P 500 등 주요 지수 데이터 수집
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional
import requests
from bs4 import BeautifulSoup


class MarketDataCollector:
    """시장 데이터 수집 클래스"""
    
    def __init__(self):
        self.cache = {}
        
    def get_vix(self, period: str = "1y") -> pd.DataFrame:
        """VIX 변동성 지수 데이터 수집"""
        vix = yf.Ticker("^VIX")
        df = vix.history(period=period)
        df['Ticker'] = 'VIX'
        return df
    
    def get_10y_treasury(self, period: str = "1y") -> pd.DataFrame:
        """10년 국채 금리 데이터 수집"""
        tnx = yf.Ticker("^TNX")
        df = tnx.history(period=period)
        df['Ticker'] = '10Y Treasury'
        return df
    
    def get_sp500(self, period: str = "1y") -> pd.DataFrame:
        """S&P 500 데이터 수집"""
        sp500 = yf.Ticker("^GSPC")
        df = sp500.history(period=period)
        df['Ticker'] = 'S&P 500'
        return df
    
    def get_ticker_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        """개별 티커 데이터 수집"""
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        df['Ticker'] = ticker
        return df
    
    def get_ticker_info(self, ticker: str) -> Dict:
        """티커의 기본 정보 (PER, PBR 등) 수집"""
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return {
            "ticker": ticker,
            "name": info.get("shortName", "N/A"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "per": info.get("trailingPE", None),
            "forward_per": info.get("forwardPE", None),
            "pbr": info.get("priceToBook", None),
            "psr": info.get("priceToSalesTrailing12Months", None),
            "dividend_yield": info.get("dividendYield", None),
            "market_cap": info.get("marketCap", None),
            "52w_high": info.get("fiftyTwoWeekHigh", None),
            "52w_low": info.get("fiftyTwoWeekLow", None),
            "current_price": info.get("currentPrice", info.get("regularMarketPrice", None)),
            "target_price": info.get("targetMeanPrice", None),
            "recommendation": info.get("recommendationKey", "N/A"),
            "beta": info.get("beta", None),
            "eps": info.get("trailingEps", None),
            "forward_eps": info.get("forwardEps", None),
        }
    
    def get_sp500_forward_pe(self) -> Optional[float]:
        """
        S&P 500 Forward P/E 수집
        1차: WSJ에서 스크래핑 시도
        2차: SPY trailing PE 사용
        3차: 기본값 21 사용
        """
        import requests
        from bs4 import BeautifulSoup
        
        # 방법 1: WSJ에서 Forward P/E 스크래핑 시도
        try:
            url = "https://www.wsj.com/market-data/stocks/peyields"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # WSJ 페이지 구조에서 S&P 500 Forward P/E 찾기
                tables = soup.find_all('table')
                for table in tables:
                    text = table.get_text()
                    if 'S&P 500' in text and 'Forward' in text:
                        # 숫자 추출 시도
                        import re
                        numbers = re.findall(r'\d+\.\d+', text)
                        if numbers:
                            pe = float(numbers[0])
                            if 10 < pe < 40:  # 합리적인 범위
                                return pe
        except Exception:
            pass
        
        # 방법 2: SPY trailing P/E 사용 (약간 할인 적용하여 forward 추정)
        try:
            spy = yf.Ticker("SPY")
            info = spy.info
            trailing_pe = info.get("trailingPE")
            if trailing_pe:
                # Forward P/E는 보통 trailing보다 약간 낮음 (earnings 성장 기대)
                return round(trailing_pe * 0.95, 1)
        except Exception:
            pass
        
        # 방법 3: 기본값 (현재 시장 평균 수준)
        return 21.0
    
    def get_all_market_data(self, period: str = "1y") -> Dict[str, pd.DataFrame]:
        """모든 시장 데이터 한번에 수집"""
        return {
            "vix": self.get_vix(period),
            "treasury_10y": self.get_10y_treasury(period),
            "sp500": self.get_sp500(period),
        }
    
    def get_market_summary(self) -> Dict:
        """현재 시장 요약 정보"""
        vix_data = self.get_vix("5d")
        tnx_data = self.get_10y_treasury("5d")
        sp500_data = self.get_sp500("5d")
        
        return {
            "vix": {
                "current": vix_data['Close'].iloc[-1] if not vix_data.empty else None,
                "change_1d": self._calculate_change(vix_data['Close']) if not vix_data.empty else None,
            },
            "treasury_10y": {
                "current": tnx_data['Close'].iloc[-1] if not tnx_data.empty else None,
                "change_1d": self._calculate_change(tnx_data['Close']) if not tnx_data.empty else None,
            },
            "sp500": {
                "current": sp500_data['Close'].iloc[-1] if not sp500_data.empty else None,
                "change_1d": self._calculate_change(sp500_data['Close']) if not sp500_data.empty else None,
            },
            "sp500_forward_pe": self.get_sp500_forward_pe(),
            "timestamp": datetime.now().isoformat(),
        }
    
    def _calculate_change(self, series: pd.Series) -> Optional[float]:
        """전일 대비 변화율 계산"""
        if len(series) < 2:
            return None
        return ((series.iloc[-1] - series.iloc[-2]) / series.iloc[-2]) * 100


if __name__ == "__main__":
    # 테스트
    collector = MarketDataCollector()
    summary = collector.get_market_summary()
    print("=== 시장 요약 ===")
    for key, value in summary.items():
        print(f"{key}: {value}")
