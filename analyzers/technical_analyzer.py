"""
기술적 분석 모듈
이동평균, RSI, MACD 등 기술적 지표 계산
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import yfinance as yf


class TechnicalAnalyzer:
    """기술적 분석 클래스"""
    
    def __init__(self):
        pass
    
    def calculate_sma(self, data: pd.Series, period: int) -> pd.Series:
        """단순 이동평균 (SMA)"""
        return data.rolling(window=period).mean()
    
    def calculate_ema(self, data: pd.Series, period: int) -> pd.Series:
        """지수 이동평균 (EMA)"""
        return data.ewm(span=period, adjust=False).mean()
    
    def calculate_rsi(self, data: pd.Series, period: int = 14) -> pd.Series:
        """상대강도지수 (RSI)"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, data: pd.Series, 
                       fast: int = 12, 
                       slow: int = 26, 
                       signal: int = 9) -> Dict[str, pd.Series]:
        """MACD"""
        ema_fast = self.calculate_ema(data, fast)
        ema_slow = self.calculate_ema(data, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = self.calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }
    
    def calculate_bollinger_bands(self, data: pd.Series, 
                                   period: int = 20, 
                                   std_dev: float = 2) -> Dict[str, pd.Series]:
        """볼린저 밴드"""
        sma = self.calculate_sma(data, period)
        std = data.rolling(window=period).std()
        
        return {
            "middle": sma,
            "upper": sma + (std * std_dev),
            "lower": sma - (std * std_dev)
        }
    
    def calculate_stochastic(self, high: pd.Series, 
                              low: pd.Series, 
                              close: pd.Series,
                              k_period: int = 14,
                              d_period: int = 3) -> Dict[str, pd.Series]:
        """스토캐스틱"""
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        k = ((close - lowest_low) / (highest_high - lowest_low)) * 100
        d = k.rolling(window=d_period).mean()
        
        return {"k": k, "d": d}
    
    def calculate_atr(self, high: pd.Series, 
                      low: pd.Series, 
                      close: pd.Series,
                      period: int = 14) -> pd.Series:
        """평균 진정 범위 (ATR)"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def get_support_resistance(self, data: pd.DataFrame, 
                                lookback: int = 20) -> Dict[str, float]:
        """지지/저항선 계산"""
        recent_data = data.tail(lookback)
        
        return {
            "resistance": recent_data['High'].max(),
            "support": recent_data['Low'].min(),
            "pivot": (recent_data['High'].max() + recent_data['Low'].min() + recent_data['Close'].iloc[-1]) / 3
        }
    
    def analyze_ticker(self, ticker: str, period: str = "1y") -> Dict:
        """티커 종합 기술적 분석"""
        stock = yf.Ticker(ticker)
        data = stock.history(period=period)
        
        if data.empty:
            return {"error": f"{ticker} 데이터를 가져올 수 없습니다."}
        
        close = data['Close']
        high = data['High']
        low = data['Low']
        
        # 현재가
        current_price = close.iloc[-1]
        
        # 이동평균
        sma_20 = self.calculate_sma(close, 20).iloc[-1]
        sma_50 = self.calculate_sma(close, 50).iloc[-1]
        sma_200 = self.calculate_sma(close, 200).iloc[-1] if len(close) >= 200 else None
        
        # RSI
        rsi = self.calculate_rsi(close).iloc[-1]
        
        # MACD
        macd_data = self.calculate_macd(close)
        
        # 볼린저 밴드
        bb = self.calculate_bollinger_bands(close)
        
        # 스토캐스틱
        stoch = self.calculate_stochastic(high, low, close)
        
        # ATR
        atr = self.calculate_atr(high, low, close).iloc[-1]
        
        # 지지/저항
        sr = self.get_support_resistance(data)
        
        # 트렌드 판단
        trend = self._determine_trend(current_price, sma_20, sma_50, sma_200)
        
        # 신호 생성
        signals = self._generate_signals(
            current_price, sma_20, sma_50, sma_200,
            rsi, macd_data, stoch, bb
        )
        
        return {
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "moving_averages": {
                "sma_20": round(sma_20, 2),
                "sma_50": round(sma_50, 2),
                "sma_200": round(sma_200, 2) if sma_200 else None,
                "price_vs_sma20": round(((current_price - sma_20) / sma_20) * 100, 2),
                "price_vs_sma50": round(((current_price - sma_50) / sma_50) * 100, 2),
            },
            "momentum": {
                "rsi_14": round(rsi, 2),
                "rsi_signal": "과매수" if rsi > 70 else "과매도" if rsi < 30 else "중립",
                "stochastic_k": round(stoch['k'].iloc[-1], 2),
                "stochastic_d": round(stoch['d'].iloc[-1], 2),
            },
            "macd": {
                "macd_line": round(macd_data['macd'].iloc[-1], 4),
                "signal_line": round(macd_data['signal'].iloc[-1], 4),
                "histogram": round(macd_data['histogram'].iloc[-1], 4),
                "signal": "매수" if macd_data['histogram'].iloc[-1] > 0 else "매도",
            },
            "bollinger_bands": {
                "upper": round(bb['upper'].iloc[-1], 2),
                "middle": round(bb['middle'].iloc[-1], 2),
                "lower": round(bb['lower'].iloc[-1], 2),
                "position": self._bb_position(current_price, bb),
            },
            "volatility": {
                "atr_14": round(atr, 2),
                "atr_percent": round((atr / current_price) * 100, 2),
            },
            "support_resistance": {
                "resistance": round(sr['resistance'], 2),
                "support": round(sr['support'], 2),
                "pivot": round(sr['pivot'], 2),
            },
            "trend": trend,
            "signals": signals,
        }
    
    def _determine_trend(self, price: float, sma20: float, sma50: float, sma200: Optional[float]) -> Dict:
        """트렌드 판단"""
        short_term = "상승" if price > sma20 else "하락"
        medium_term = "상승" if price > sma50 else "하락"
        long_term = "상승" if sma200 and price > sma200 else "하락" if sma200 else "N/A"
        
        # 골든크로스/데드크로스 체크
        if sma200:
            if sma50 > sma200:
                cross = "골든크로스 (강세)"
            else:
                cross = "데드크로스 (약세)"
        else:
            cross = "N/A"
        
        return {
            "short_term": short_term,
            "medium_term": medium_term,
            "long_term": long_term,
            "ma_cross": cross
        }
    
    def _generate_signals(self, price, sma20, sma50, sma200, rsi, macd, stoch, bb) -> Dict:
        """매매 신호 생성"""
        signals = {
            "buy_signals": [],
            "sell_signals": [],
            "overall": "중립"
        }
        
        buy_count = 0
        sell_count = 0
        
        # 이동평균 기반
        if price > sma20 and price > sma50:
            signals["buy_signals"].append("가격이 20일/50일 이동평균 위")
            buy_count += 1
        elif price < sma20 and price < sma50:
            signals["sell_signals"].append("가격이 20일/50일 이동평균 아래")
            sell_count += 1
        
        # RSI 기반
        if rsi < 30:
            signals["buy_signals"].append("RSI 과매도 구간")
            buy_count += 1
        elif rsi > 70:
            signals["sell_signals"].append("RSI 과매수 구간")
            sell_count += 1
        
        # MACD 기반
        if macd['histogram'].iloc[-1] > 0 and macd['histogram'].iloc[-2] < 0:
            signals["buy_signals"].append("MACD 골든크로스")
            buy_count += 1
        elif macd['histogram'].iloc[-1] < 0 and macd['histogram'].iloc[-2] > 0:
            signals["sell_signals"].append("MACD 데드크로스")
            sell_count += 1
        
        # 볼린저 밴드 기반
        if price < bb['lower'].iloc[-1]:
            signals["buy_signals"].append("볼린저 밴드 하단 이탈")
            buy_count += 1
        elif price > bb['upper'].iloc[-1]:
            signals["sell_signals"].append("볼린저 밴드 상단 이탈")
            sell_count += 1
        
        # 스토캐스틱 기반
        if stoch['k'].iloc[-1] < 20:
            signals["buy_signals"].append("스토캐스틱 과매도")
            buy_count += 1
        elif stoch['k'].iloc[-1] > 80:
            signals["sell_signals"].append("스토캐스틱 과매수")
            sell_count += 1
        
        # 종합 판단
        if buy_count >= 3:
            signals["overall"] = "강력 매수"
        elif buy_count >= 2:
            signals["overall"] = "매수"
        elif sell_count >= 3:
            signals["overall"] = "강력 매도"
        elif sell_count >= 2:
            signals["overall"] = "매도"
        else:
            signals["overall"] = "중립"
        
        return signals
    
    def _bb_position(self, price: float, bb: Dict) -> str:
        """볼린저 밴드 내 위치"""
        upper = bb['upper'].iloc[-1]
        lower = bb['lower'].iloc[-1]
        middle = bb['middle'].iloc[-1]
        
        if price > upper:
            return "상단 돌파 (과매수)"
        elif price < lower:
            return "하단 돌파 (과매도)"
        elif price > middle:
            return "중간선 위"
        else:
            return "중간선 아래"


if __name__ == "__main__":
    # 테스트
    analyzer = TechnicalAnalyzer()
    
    print("=== AAPL 기술적 분석 ===")
    result = analyzer.analyze_ticker("AAPL")
    
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
