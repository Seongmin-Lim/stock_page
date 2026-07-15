"""
주식 기본적 분석 데이터 수집 모듈
PER, PBR, EPS, 재무제표 등
"""
import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional


class StockFundamentalsCollector:
    """주식 기본적 분석 데이터 수집 클래스"""
    
    def __init__(self):
        self.cache = {}
    
    def get_stock_valuation(self, ticker: str) -> Dict:
        """주식 밸류에이션 지표 수집"""
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return {
            "ticker": ticker,
            "name": info.get("shortName", info.get("longName", "N/A")),
            "current_price": info.get("currentPrice", info.get("regularMarketPrice")),
            
            # 수익성 지표
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            
            # 자산 가치 지표
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "enterprise_to_ebitda": info.get("enterpriseToEbitda"),
            "enterprise_to_revenue": info.get("enterpriseToRevenue"),
            
            # 수익
            "trailing_eps": info.get("trailingEps"),
            "forward_eps": info.get("forwardEps"),
            "book_value": info.get("bookValue"),
            
            # 배당
            "dividend_yield": info.get("dividendYield"),
            "dividend_rate": info.get("dividendRate"),
            "payout_ratio": info.get("payoutRatio"),
            
            # 마진
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "gross_margin": info.get("grossMargins"),
            
            # 성장
            "earnings_growth": info.get("earningsGrowth"),
            "revenue_growth": info.get("revenueGrowth"),
            
            # 기타
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "beta": info.get("beta"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            
            "timestamp": datetime.now().isoformat()
        }
    
    def get_financial_statements(self, ticker: str) -> Dict:
        """재무제표 데이터 수집"""
        stock = yf.Ticker(ticker)
        
        return {
            "ticker": ticker,
            "income_statement": stock.income_stmt.to_dict() if stock.income_stmt is not None else None,
            "balance_sheet": stock.balance_sheet.to_dict() if stock.balance_sheet is not None else None,
            "cashflow": stock.cashflow.to_dict() if stock.cashflow is not None else None,
            "quarterly_income": stock.quarterly_income_stmt.to_dict() if stock.quarterly_income_stmt is not None else None,
            "quarterly_balance": stock.quarterly_balance_sheet.to_dict() if stock.quarterly_balance_sheet is not None else None,
        }
    
    def get_analyst_info(self, ticker: str) -> Dict:
        """애널리스트 정보 수집"""
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return {
            "ticker": ticker,
            "recommendation": info.get("recommendationKey"),
            "recommendation_mean": info.get("recommendationMean"),
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "target_mean_price": info.get("targetMeanPrice"),
            "target_median_price": info.get("targetMedianPrice"),
            "number_of_analysts": info.get("numberOfAnalystOpinions"),
        }
    
    def get_multiple_stocks_valuation(self, tickers: List[str]) -> pd.DataFrame:
        """여러 주식의 밸류에이션 비교"""
        data = []
        for ticker in tickers:
            try:
                valuation = self.get_stock_valuation(ticker)
                data.append(valuation)
            except Exception as e:
                print(f"{ticker} 데이터 수집 실패: {e}")
        
        return pd.DataFrame(data)
    
    def compare_to_sector(self, ticker: str) -> Dict:
        """섹터 평균과 비교"""
        stock = yf.Ticker(ticker)
        info = stock.info
        
        sector = info.get("sector", "Unknown")
        industry = info.get("industry", "Unknown")
        
        # 주요 지표
        metrics = {
            "ticker": ticker,
            "sector": sector,
            "industry": industry,
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "profit_margin": info.get("profitMargins"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
        }
        
        # 섹터 평균은 유료 데이터 필요, 여기서는 일반적인 기준치 제공
        benchmarks = self._get_sector_benchmarks(sector)
        
        return {
            "stock_metrics": metrics,
            "sector_benchmarks": benchmarks,
            "comparison": self._compare_metrics(metrics, benchmarks)
        }
    
    def _get_sector_benchmarks(self, sector: str) -> Dict:
        """섹터별 일반적인 기준치 (참고용)"""
        # 일반적인 섹터별 평균치 (실제 데이터는 변동됨)
        benchmarks = {
            "Technology": {"pe": 25, "pb": 5, "margin": 0.20},
            "Healthcare": {"pe": 20, "pb": 4, "margin": 0.15},
            "Financial Services": {"pe": 12, "pb": 1.2, "margin": 0.25},
            "Consumer Cyclical": {"pe": 18, "pb": 3, "margin": 0.10},
            "Consumer Defensive": {"pe": 22, "pb": 4, "margin": 0.08},
            "Energy": {"pe": 10, "pb": 1.5, "margin": 0.10},
            "Industrials": {"pe": 18, "pb": 3, "margin": 0.10},
            "Basic Materials": {"pe": 12, "pb": 2, "margin": 0.12},
            "Utilities": {"pe": 18, "pb": 1.8, "margin": 0.12},
            "Real Estate": {"pe": 35, "pb": 2, "margin": 0.30},
            "Communication Services": {"pe": 20, "pb": 3, "margin": 0.15},
        }
        
        return benchmarks.get(sector, {"pe": 20, "pb": 3, "margin": 0.12})
    
    def _compare_metrics(self, metrics: Dict, benchmarks: Dict) -> Dict:
        """지표 비교 분석"""
        comparison = {}
        
        if metrics.get("pe_ratio") and benchmarks.get("pe"):
            pe_diff = ((metrics["pe_ratio"] - benchmarks["pe"]) / benchmarks["pe"]) * 100
            comparison["pe_vs_sector"] = {
                "difference_pct": round(pe_diff, 1),
                "assessment": "고평가" if pe_diff > 20 else "저평가" if pe_diff < -20 else "적정"
            }
        
        if metrics.get("pb_ratio") and benchmarks.get("pb"):
            pb_diff = ((metrics["pb_ratio"] - benchmarks["pb"]) / benchmarks["pb"]) * 100
            comparison["pb_vs_sector"] = {
                "difference_pct": round(pb_diff, 1),
                "assessment": "고평가" if pb_diff > 20 else "저평가" if pb_diff < -20 else "적정"
            }
        
        if metrics.get("profit_margin") and benchmarks.get("margin"):
            margin_diff = (metrics["profit_margin"] - benchmarks["margin"]) * 100
            comparison["margin_vs_sector"] = {
                "difference_pct": round(margin_diff, 1),
                "assessment": "우수" if margin_diff > 5 else "미흡" if margin_diff < -5 else "평균"
            }
        
        return comparison
    
    def get_growth_metrics(self, ticker: str) -> Dict:
        """성장 지표 분석"""
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # 수익 히스토리
        try:
            earnings = stock.earnings_history
            if earnings is not None and not earnings.empty:
                recent_surprises = earnings['surprisePercent'].tail(4).tolist()
            else:
                recent_surprises = []
        except:
            recent_surprises = []
        
        return {
            "ticker": ticker,
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
            "peg_ratio": info.get("pegRatio"),  # PEG < 1 = 저평가
            "recent_earnings_surprises": recent_surprises,
            "forward_pe": info.get("forwardPE"),
            "trailing_pe": info.get("trailingPE"),
            "pe_to_growth": (info.get("trailingPE") / (info.get("earningsGrowth", 0.01) * 100)) if info.get("earningsGrowth") else None
        }


if __name__ == "__main__":
    # 테스트
    collector = StockFundamentalsCollector()
    
    print("=== AAPL 밸류에이션 ===")
    valuation = collector.get_stock_valuation("AAPL")
    for key, value in valuation.items():
        if value is not None:
            print(f"{key}: {value}")
    
    print("\n=== 섹터 비교 ===")
    comparison = collector.compare_to_sector("AAPL")
    print(f"섹터: {comparison['stock_metrics']['sector']}")
    print(f"비교 결과: {comparison['comparison']}")
