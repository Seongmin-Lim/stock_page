"""
공포탐욕 지수 (Fear & Greed Index) 수집 모듈
CNN Fear & Greed Index 및 대안 지표 계산
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional
import yfinance as yf


class FearGreedCollector:
    """공포탐욕 지수 수집 및 계산 클래스"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def get_cnn_fear_greed(self) -> Optional[Dict]:
        """
        CNN Fear & Greed Index 수집 시도
        주의: 웹 스크래핑은 사이트 구조 변경에 취약함
        """
        try:
            # CNN API endpoint (변경될 수 있음)
            url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "value": data.get("fear_and_greed", {}).get("score"),
                    "rating": data.get("fear_and_greed", {}).get("rating"),
                    "timestamp": datetime.now().isoformat(),
                    "source": "CNN Fear & Greed Index"
                }
        except Exception as e:
            print(f"CNN Fear & Greed 수집 실패: {e}")
        
        return None
    
    def calculate_custom_fear_greed(self) -> Dict:
        """
        자체 공포탐욕 지수 계산
        여러 지표를 종합하여 0-100 사이 점수 산출
        """
        scores = {}
        weights = {}
        
        # 1. VIX 기반 점수 (높을수록 공포)
        try:
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period="1mo")
            current_vix = vix_data['Close'].iloc[-1]
            vix_avg = vix_data['Close'].mean()
            
            # VIX 20 이하: 탐욕, 30 이상: 공포
            if current_vix <= 12:
                vix_score = 95  # Extreme Greed
            elif current_vix <= 17:
                vix_score = 75  # Greed
            elif current_vix <= 22:
                vix_score = 50  # Neutral
            elif current_vix <= 30:
                vix_score = 25  # Fear
            else:
                vix_score = 5   # Extreme Fear
            
            scores['vix'] = vix_score
            weights['vix'] = 0.25
        except Exception as e:
            print(f"VIX 계산 실패: {e}")
        
        # 2. S&P 500 모멘텀 (125일 이동평균 대비)
        try:
            sp500 = yf.Ticker("^GSPC")
            sp500_data = sp500.history(period="6mo")
            current_price = sp500_data['Close'].iloc[-1]
            ma_125 = sp500_data['Close'].rolling(window=125).mean().iloc[-1]
            
            momentum = ((current_price - ma_125) / ma_125) * 100
            
            # 모멘텀 점수 변환
            if momentum > 10:
                momentum_score = 90
            elif momentum > 5:
                momentum_score = 70
            elif momentum > 0:
                momentum_score = 55
            elif momentum > -5:
                momentum_score = 40
            elif momentum > -10:
                momentum_score = 25
            else:
                momentum_score = 10
            
            scores['momentum'] = momentum_score
            weights['momentum'] = 0.20
        except Exception as e:
            print(f"모멘텀 계산 실패: {e}")
        
        # 3. 52주 신고가/신저가 비율
        try:
            # 간소화된 버전: S&P 500 ETF 기준
            spy = yf.Ticker("SPY")
            spy_data = spy.history(period="1y")
            current_price = spy_data['Close'].iloc[-1]
            high_52w = spy_data['High'].max()
            low_52w = spy_data['Low'].min()
            
            # 현재 위치 (0: 52주 저점, 100: 52주 고점)
            position = ((current_price - low_52w) / (high_52w - low_52w)) * 100
            scores['52w_position'] = position
            weights['52w_position'] = 0.15
        except Exception as e:
            print(f"52주 위치 계산 실패: {e}")
        
        # 4. 채권 vs 주식 (10년 국채 금리)
        try:
            tnx = yf.Ticker("^TNX")
            tnx_data = tnx.history(period="3mo")
            current_yield = tnx_data['Close'].iloc[-1]
            avg_yield = tnx_data['Close'].mean()
            
            # 금리 상승 = 주식 약세 가능성
            yield_change = current_yield - avg_yield
            if yield_change < -0.5:
                yield_score = 70  # 금리 하락 = 주식에 긍정적
            elif yield_change < 0:
                yield_score = 60
            elif yield_change < 0.5:
                yield_score = 40
            else:
                yield_score = 30  # 금리 급등 = 주식에 부정적
            
            scores['yield'] = yield_score
            weights['yield'] = 0.15
        except Exception as e:
            print(f"금리 계산 실패: {e}")
        
        # 5. Put/Call Ratio (간접 추정 - VIX 변화율 사용)
        try:
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period="5d")
            vix_change = ((vix_data['Close'].iloc[-1] - vix_data['Close'].iloc[0]) / vix_data['Close'].iloc[0]) * 100
            
            if vix_change < -10:
                pcr_score = 80  # VIX 급락 = 탐욕
            elif vix_change < 0:
                pcr_score = 60
            elif vix_change < 10:
                pcr_score = 40
            else:
                pcr_score = 20  # VIX 급등 = 공포
            
            scores['pcr_proxy'] = pcr_score
            weights['pcr_proxy'] = 0.25
        except Exception as e:
            print(f"PCR 대리 계산 실패: {e}")
        
        # 가중 평균 계산
        if scores:
            total_weight = sum(weights.values())
            weighted_score = sum(scores[k] * weights[k] for k in scores.keys()) / total_weight
        else:
            weighted_score = 50  # 기본값
        
        # 등급 결정
        if weighted_score >= 75:
            rating = "Extreme Greed"
        elif weighted_score >= 55:
            rating = "Greed"
        elif weighted_score >= 45:
            rating = "Neutral"
        elif weighted_score >= 25:
            rating = "Fear"
        else:
            rating = "Extreme Fear"
        
        return {
            "value": round(weighted_score, 1),
            "rating": rating,
            "components": scores,
            "weights": weights,
            "timestamp": datetime.now().isoformat(),
            "source": "Custom Calculation"
        }
    
    def get_fear_greed_index(self) -> Dict:
        """
        공포탐욕 지수 반환
        CNN 데이터 실패 시 자체 계산 사용
        """
        # CNN 데이터 시도
        cnn_data = self.get_cnn_fear_greed()
        if cnn_data and cnn_data.get("value"):
            return cnn_data
        
        # 실패 시 자체 계산
        return self.calculate_custom_fear_greed()
    
    def get_fear_greed_history(self, days: int = 30) -> pd.DataFrame:
        """
        공포탐욕 지수 히스토리 (자체 계산 기반)
        주의: 실시간 히스토리 데이터는 별도 저장 필요
        """
        # 간소화된 버전: VIX 기반 역사적 추정
        vix = yf.Ticker("^VIX")
        vix_data = vix.history(period=f"{days}d")
        
        def vix_to_fear_greed(vix_value):
            if vix_value <= 12:
                return 95
            elif vix_value <= 17:
                return 75
            elif vix_value <= 22:
                return 50
            elif vix_value <= 30:
                return 25
            else:
                return 5
        
        vix_data['FearGreed'] = vix_data['Close'].apply(vix_to_fear_greed)
        return vix_data[['Close', 'FearGreed']].rename(columns={'Close': 'VIX'})


if __name__ == "__main__":
    # 테스트
    collector = FearGreedCollector()
    
    print("=== 공포탐욕 지수 ===")
    fg_index = collector.get_fear_greed_index()
    for key, value in fg_index.items():
        print(f"{key}: {value}")
    
    print("\n=== 최근 10일 히스토리 ===")
    history = collector.get_fear_greed_history(10)
    print(history.tail())
