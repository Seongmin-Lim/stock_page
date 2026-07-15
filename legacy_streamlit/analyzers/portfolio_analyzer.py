"""
포트폴리오 분석 및 비교 모듈
올웨더, 대가들의 포트폴리오와 비교
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


class PortfolioAnalyzer:
    """포트폴리오 분석 및 비교 클래스"""
    
    # 유명 포트폴리오 전략
    FAMOUS_PORTFOLIOS = {
        "all_weather": {
            "name": "레이 달리오 올웨더 포트폴리오",
            "creator": "Ray Dalio (Bridgewater)",
            "description": "모든 경제 환경에서 안정적 수익을 추구하는 포트폴리오",
            "allocation": {
                "VTI": 30,    # 미국 전체 주식
                "TLT": 40,    # 장기 국채
                "IEF": 15,    # 중기 국채
                "GLD": 7.5,   # 금
                "DBC": 7.5,   # 원자재
            },
            "category_allocation": {
                "주식": 30,
                "장기채권": 40,
                "중기채권": 15,
                "금": 7.5,
                "원자재": 7.5,
            }
        },
        "60_40": {
            "name": "전통적 60/40 포트폴리오",
            "creator": "Classic Strategy",
            "description": "주식 60%, 채권 40%의 전통적 배분",
            "allocation": {
                "SPY": 60,    # S&P 500
                "AGG": 40,    # 미국 종합 채권
            },
            "category_allocation": {
                "주식": 60,
                "채권": 40,
            }
        },
        "warren_buffett": {
            "name": "워렌 버핏 추천 포트폴리오",
            "creator": "Warren Buffett",
            "description": "버핏이 일반 투자자에게 추천한 단순한 포트폴리오",
            "allocation": {
                "VOO": 90,    # S&P 500
                "SHY": 10,    # 단기 국채
            },
            "category_allocation": {
                "주식": 90,
                "단기채권": 10,
            }
        },
        "david_swensen": {
            "name": "데이비드 스웬슨 포트폴리오",
            "creator": "David Swensen (Yale)",
            "description": "예일대 기금 운용 전략을 개인용으로 변형",
            "allocation": {
                "VTI": 30,    # 미국 주식
                "VEA": 15,    # 선진국 주식
                "VWO": 5,     # 신흥국 주식
                "VNQ": 20,    # 리츠
                "TIP": 15,    # 물가연동채
                "TLT": 15,    # 장기 국채
            },
            "category_allocation": {
                "미국주식": 30,
                "선진국주식": 15,
                "신흥국주식": 5,
                "리츠": 20,
                "물가연동채": 15,
                "장기채권": 15,
            }
        },
        "harry_browne": {
            "name": "해리 브라운 영구 포트폴리오",
            "creator": "Harry Browne",
            "description": "4가지 자산에 균등 배분하는 단순한 전략",
            "allocation": {
                "VTI": 25,    # 주식
                "TLT": 25,    # 장기 국채
                "SHY": 25,    # 단기 국채/현금
                "GLD": 25,    # 금
            },
            "category_allocation": {
                "주식": 25,
                "장기채권": 25,
                "현금성": 25,
                "금": 25,
            }
        },
        "three_fund": {
            "name": "보글헤드 3펀드 포트폴리오",
            "creator": "Bogleheads",
            "description": "존 보글의 철학에 기반한 단순한 인덱스 투자",
            "allocation": {
                "VTI": 40,    # 미국 전체 주식
                "VXUS": 20,   # 미국 외 주식
                "BND": 40,    # 미국 종합 채권
            },
            "category_allocation": {
                "미국주식": 40,
                "해외주식": 20,
                "채권": 40,
            }
        },
        "golden_butterfly": {
            "name": "골든 버터플라이 포트폴리오",
            "creator": "Tyler (Portfolio Charts)",
            "description": "영구 포트폴리오의 변형, 소형 가치주 추가",
            "allocation": {
                "VTI": 20,    # 미국 전체 주식
                "IWN": 20,    # 소형 가치주
                "TLT": 20,    # 장기 국채
                "SHY": 20,    # 단기 국채
                "GLD": 20,    # 금
            },
            "category_allocation": {
                "대형주": 20,
                "소형가치주": 20,
                "장기채권": 20,
                "단기채권": 20,
                "금": 20,
            }
        },
        "pension_kr": {
            "name": "🇰🇷 연금저축계좌 포트폴리오",
            "creator": "한국 연금저축 최적화",
            "description": "연금저축계좌(IRP/연금저축펀드)에 적합한 장기 투자 포트폴리오. 세액공제 혜택 극대화 및 안정적 노후 준비",
            "allocation": {
                "TIGER 미국S&P500": 30,     # 미국 대형주 (국내 ETF)
                "KODEX 미국나스닥100": 20,   # 미국 기술주 (국내 ETF)
                "ACE 미국배당다우존스": 15,   # 미국 배당주 (국내 ETF)
                "TIGER 미국채10년선물": 15,  # 미국 중기채 (국내 ETF)
                "KODEX 골드선물(H)": 10,     # 금 (국내 ETF)
                "TIGER 단기채권액티브": 10,  # 단기채/현금성 (국내 ETF)
            },
            "category_allocation": {
                "미국주식": 50,
                "미국배당주": 15,
                "채권": 25,
                "금": 10,
            },
            "notes": {
                "세액공제": "연 900만원 한도 (IRP 포함 시 1,800만원)",
                "과세이연": "인출 시까지 과세 이연, 연금 수령 시 3.3~5.5% 저율과세",
                "추천대상": "장기 노후 준비, 세액공제 혜택 필요한 직장인/자영업자",
                "리밸런싱": "연 1회 리밸런싱 권장",
            }
        },
    }
    
    def __init__(self):
        self.cache = {}
    
    def calculate_portfolio_metrics(self, 
                                    holdings: Dict[str, float],
                                    period: str = "1y") -> Dict:
        """포트폴리오 성과 지표 계산"""
        if not holdings:
            return {"error": "보유 종목이 없습니다"}
        
        # 비중 정규화
        total_weight = sum(holdings.values())
        weights = {k: v / total_weight * 100 for k, v in holdings.items()}
        
        # 개별 종목 데이터 수집
        returns_data = {}
        prices_data = {}
        
        for ticker in holdings.keys():
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period=period)
                if not hist.empty:
                    prices_data[ticker] = hist['Close']
                    returns_data[ticker] = hist['Close'].pct_change()
            except Exception as e:
                print(f"{ticker} 데이터 수집 실패: {e}")
        
        if not returns_data:
            return {"error": "데이터를 가져올 수 없습니다"}
        
        # 포트폴리오 수익률 계산
        portfolio_returns = pd.Series(0, index=list(returns_data.values())[0].index)
        
        for ticker, weight in weights.items():
            if ticker in returns_data:
                portfolio_returns += returns_data[ticker].fillna(0) * (weight / 100)
        
        # 성과 지표 계산
        total_return = (1 + portfolio_returns).prod() - 1
        annual_return = (1 + total_return) ** (252 / len(portfolio_returns)) - 1
        volatility = portfolio_returns.std() * np.sqrt(252)
        sharpe_ratio = annual_return / volatility if volatility > 0 else 0
        
        # 최대 낙폭 계산
        cumulative = (1 + portfolio_returns).cumprod()
        rolling_max = cumulative.cummax()
        drawdown = (cumulative - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # 개별 종목 기여도
        contributions = {}
        for ticker, weight in weights.items():
            if ticker in returns_data:
                ticker_return = (1 + returns_data[ticker].fillna(0)).prod() - 1
                contributions[ticker] = {
                    "weight": round(weight, 2),
                    "return": round(ticker_return * 100, 2),
                    "contribution": round(ticker_return * weight, 2)
                }
        
        return {
            "holdings": weights,
            "metrics": {
                "total_return": round(total_return * 100, 2),
                "annual_return": round(annual_return * 100, 2),
                "volatility": round(volatility * 100, 2),
                "sharpe_ratio": round(sharpe_ratio, 2),
                "max_drawdown": round(max_drawdown * 100, 2),
            },
            "contributions": contributions,
            "period": period,
        }
    
    def compare_with_famous_portfolios(self, 
                                       user_holdings: Dict[str, float],
                                       period: str = "1y") -> Dict:
        """유명 포트폴리오와 비교"""
        results = {
            "user_portfolio": self.calculate_portfolio_metrics(user_holdings, period),
            "famous_portfolios": {},
            "comparison": {},
        }
        
        # 유명 포트폴리오 성과 계산
        for name, portfolio in self.FAMOUS_PORTFOLIOS.items():
            try:
                metrics = self.calculate_portfolio_metrics(portfolio["allocation"], period)
                results["famous_portfolios"][name] = {
                    "info": {
                        "name": portfolio["name"],
                        "creator": portfolio["creator"],
                        "description": portfolio["description"],
                    },
                    "allocation": portfolio["category_allocation"],
                    "metrics": metrics.get("metrics", {})
                }
            except Exception as e:
                print(f"{name} 포트폴리오 계산 실패: {e}")
        
        # 비교 분석
        user_metrics = results["user_portfolio"].get("metrics", {})
        
        if user_metrics:
            comparison = []
            for name, data in results["famous_portfolios"].items():
                famous_metrics = data.get("metrics", {})
                if famous_metrics:
                    comparison.append({
                        "portfolio": data["info"]["name"],
                        "return_diff": round(
                            user_metrics.get("annual_return", 0) - famous_metrics.get("annual_return", 0), 2
                        ),
                        "volatility_diff": round(
                            user_metrics.get("volatility", 0) - famous_metrics.get("volatility", 0), 2
                        ),
                        "sharpe_diff": round(
                            user_metrics.get("sharpe_ratio", 0) - famous_metrics.get("sharpe_ratio", 0), 2
                        ),
                        "mdd_diff": round(
                            user_metrics.get("max_drawdown", 0) - famous_metrics.get("max_drawdown", 0), 2
                        ),
                    })
            
            results["comparison"] = {
                "details": comparison,
                "summary": self._generate_comparison_summary(user_metrics, results["famous_portfolios"])
            }
        
        return results
    
    def _generate_comparison_summary(self, user_metrics: Dict, famous_portfolios: Dict) -> Dict:
        """비교 요약 생성"""
        user_return = user_metrics.get("annual_return", 0)
        user_sharpe = user_metrics.get("sharpe_ratio", 0)
        user_volatility = user_metrics.get("volatility", 0)
        
        better_return_count = 0
        better_sharpe_count = 0
        lower_vol_count = 0
        
        for name, data in famous_portfolios.items():
            metrics = data.get("metrics", {})
            if user_return > metrics.get("annual_return", 0):
                better_return_count += 1
            if user_sharpe > metrics.get("sharpe_ratio", 0):
                better_sharpe_count += 1
            if user_volatility < metrics.get("volatility", 0):
                lower_vol_count += 1
        
        total = len(famous_portfolios)
        
        return {
            "return_ranking": f"수익률: {total - better_return_count + 1}위 / {total + 1}개",
            "sharpe_ranking": f"샤프비율: {total - better_sharpe_count + 1}위 / {total + 1}개",
            "volatility_ranking": f"변동성: {total - lower_vol_count + 1}위 / {total + 1}개 (낮을수록 좋음)",
            "overall_assessment": self._assess_portfolio(user_metrics, famous_portfolios)
        }
    
    def _assess_portfolio(self, user_metrics: Dict, famous_portfolios: Dict) -> str:
        """포트폴리오 종합 평가"""
        user_sharpe = user_metrics.get("sharpe_ratio", 0)
        user_mdd = abs(user_metrics.get("max_drawdown", 0))
        
        avg_sharpe = np.mean([
            fp.get("metrics", {}).get("sharpe_ratio", 0) 
            for fp in famous_portfolios.values()
        ])
        
        avg_mdd = np.mean([
            abs(fp.get("metrics", {}).get("max_drawdown", 0))
            for fp in famous_portfolios.values()
        ])
        
        assessments = []
        
        if user_sharpe > avg_sharpe * 1.2:
            assessments.append("위험 대비 수익률이 우수합니다")
        elif user_sharpe < avg_sharpe * 0.8:
            assessments.append("위험 대비 수익률 개선이 필요합니다")
        
        if user_mdd > avg_mdd * 1.3:
            assessments.append("최대 낙폭이 높아 분산 투자를 고려하세요")
        elif user_mdd < avg_mdd * 0.7:
            assessments.append("방어력이 우수한 포트폴리오입니다")
        
        if not assessments:
            assessments.append("유명 포트폴리오와 비슷한 수준의 성과를 보이고 있습니다")
        
        return " / ".join(assessments)
    
    def get_portfolio_recommendations(self, 
                                      user_holdings: Dict[str, float],
                                      risk_tolerance: str = "moderate",
                                      economic_phase: str = "확장기") -> Dict:
        """포트폴리오 개선 추천"""
        # 현재 포트폴리오 분석
        current_analysis = self.analyze_portfolio_composition(user_holdings)
        
        # 경제 단계별 추천 배분
        phase_recommendations = {
            "회복기": {"주식": 60, "채권": 25, "현금": 10, "대안자산": 5},
            "확장기": {"주식": 70, "채권": 20, "현금": 5, "대안자산": 5},
            "과열기": {"주식": 45, "채권": 30, "현금": 15, "대안자산": 10},
            "수축기": {"주식": 30, "채권": 35, "현금": 30, "대안자산": 5},
            "침체기": {"주식": 45, "채권": 30, "현금": 20, "대안자산": 5},
        }
        
        # 위험 성향별 조정
        risk_adjustments = {
            "conservative": {"주식": -15, "채권": +10, "현금": +5},
            "moderate": {"주식": 0, "채권": 0, "현금": 0},
            "aggressive": {"주식": +15, "채권": -10, "현금": -5},
        }
        
        recommended = phase_recommendations.get(economic_phase, phase_recommendations["확장기"]).copy()
        adjustments = risk_adjustments.get(risk_tolerance, risk_adjustments["moderate"])
        
        for asset, adj in adjustments.items():
            if asset in recommended:
                recommended[asset] = max(0, min(100, recommended[asset] + adj))
        
        # 정규화
        total = sum(recommended.values())
        recommended = {k: round(v / total * 100, 1) for k, v in recommended.items()}
        
        return {
            "current_composition": current_analysis,
            "recommended_allocation": recommended,
            "economic_phase": economic_phase,
            "risk_tolerance": risk_tolerance,
            "adjustments_needed": self._calculate_adjustments(current_analysis, recommended),
            "suggested_etfs": self._suggest_etfs(recommended, current_analysis)
        }
    
    def analyze_portfolio_composition(self, holdings: Dict[str, float]) -> Dict:
        """포트폴리오 구성 분석"""
        composition = {
            "주식": 0,
            "채권": 0,
            "현금": 0,
            "대안자산": 0,
            "기타": 0,
        }
        
        # ETF/주식 분류
        asset_categories = {
            # 주식 ETF
            "SPY": "주식", "VOO": "주식", "VTI": "주식", "QQQ": "주식",
            "IWM": "주식", "VEA": "주식", "VWO": "주식", "VXUS": "주식",
            "IWN": "주식", "VNQ": "대안자산",
            # 채권 ETF
            "TLT": "채권", "IEF": "채권", "SHY": "채권", "AGG": "채권",
            "BND": "채권", "TIP": "채권", "LQD": "채권",
            # 대안자산
            "GLD": "대안자산", "IAU": "대안자산", "SLV": "대안자산",
            "DBC": "대안자산", "GSG": "대안자산",
            # 현금성
            "SHV": "현금", "BIL": "현금", "SGOV": "현금",
        }
        
        total_weight = sum(holdings.values())
        
        for ticker, weight in holdings.items():
            normalized_weight = (weight / total_weight) * 100
            
            if ticker.upper() in asset_categories:
                category = asset_categories[ticker.upper()]
            else:
                # 개별 주식은 주식으로 분류
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    if info.get('quoteType') == 'ETF':
                        # ETF 이름으로 추정
                        name = info.get('shortName', '').lower()
                        if 'bond' in name or 'treasury' in name:
                            category = "채권"
                        elif 'gold' in name or 'commodity' in name:
                            category = "대안자산"
                        else:
                            category = "주식"
                    else:
                        category = "주식"
                except:
                    category = "기타"
            
            composition[category] += normalized_weight
        
        # 반올림
        composition = {k: round(v, 1) for k, v in composition.items()}
        
        return composition
    
    def _calculate_adjustments(self, current: Dict, recommended: Dict) -> List[Dict]:
        """필요한 조정 계산"""
        adjustments = []
        
        for asset in recommended:
            current_val = current.get(asset, 0)
            recommended_val = recommended.get(asset, 0)
            diff = recommended_val - current_val
            
            if abs(diff) > 3:  # 3% 이상 차이나면 조정 필요
                adjustments.append({
                    "asset": asset,
                    "current": current_val,
                    "recommended": recommended_val,
                    "action": "증가" if diff > 0 else "감소",
                    "amount": abs(round(diff, 1))
                })
        
        return adjustments
    
    def _suggest_etfs(self, recommended: Dict, current: Dict) -> Dict:
        """추천 ETF 제안"""
        suggestions = {}
        
        if recommended.get("주식", 0) > current.get("주식", 0):
            suggestions["주식 추가"] = ["VOO (S&P 500)", "VTI (전체 시장)", "QQQ (나스닥 100)"]
        
        if recommended.get("채권", 0) > current.get("채권", 0):
            suggestions["채권 추가"] = ["AGG (종합 채권)", "TLT (장기 국채)", "BND (채권 종합)"]
        
        if recommended.get("대안자산", 0) > current.get("대안자산", 0):
            suggestions["대안자산 추가"] = ["GLD (금)", "VNQ (리츠)", "DBC (원자재)"]
        
        if recommended.get("현금", 0) > current.get("현금", 0):
            suggestions["현금성 자산"] = ["SHY (단기 국채)", "BIL (초단기 국채)", "SGOV (단기 국채)"]
        
        return suggestions
    
    def get_famous_portfolio_info(self, portfolio_name: str) -> Optional[Dict]:
        """유명 포트폴리오 정보 조회"""
        portfolio = self.FAMOUS_PORTFOLIOS.get(portfolio_name)
        if portfolio:
            metrics = self.calculate_portfolio_metrics(portfolio["allocation"])
            return {
                "info": portfolio,
                "metrics": metrics
            }
        return None
    
    def get_etf_holdings(self, ticker: str) -> Dict:
        """
        ETF의 구성 종목 정보 가져오기
        
        Args:
            ticker: ETF 티커 (예: SPY, QQQ, VTI)
        
        Returns:
            dict: 구성 종목 정보 {holdings: [{ticker, weight, name}], top_10_weight, sector_breakdown}
        """
        try:
            import requests
            
            etf = yf.Ticker(ticker)
            info = etf.info
            
            # yfinance에서 직접 가져오기 시도
            holdings_data = []
            
            # ETF의 상위 보유 종목 가져오기
            try:
                # yfinance 최신 버전에서 지원
                if hasattr(etf, 'get_holdings'):
                    raw_holdings = etf.get_holdings()
                    if raw_holdings is not None and not raw_holdings.empty:
                        for _, row in raw_holdings.head(20).iterrows():
                            holdings_data.append({
                                "ticker": row.get('Symbol', ''),
                                "name": row.get('Name', ''),
                                "weight": row.get('% of Portfolio', 0)
                            })
            except:
                pass
            
            # 대안: 잘 알려진 ETF의 주요 구성 종목 하드코딩
            if not holdings_data:
                holdings_data = self._get_known_etf_holdings(ticker.upper())
            
            # 섹터 정보
            sector_breakdown = {}
            try:
                sector_weights = info.get('sectorWeightings', {})
                if sector_weights:
                    sector_breakdown = {k: round(v * 100, 2) for k, v in sector_weights.items()}
            except:
                pass
            
            top_10_weight = sum(h.get('weight', 0) for h in holdings_data[:10])
            
            return {
                "ticker": ticker.upper(),
                "name": info.get('shortName', ticker),
                "holdings": holdings_data,
                "top_10_weight": round(top_10_weight, 2),
                "sector_breakdown": sector_breakdown,
                "total_assets": info.get('totalAssets', 0),
                "expense_ratio": info.get('annualReportExpenseRatio', 0),
            }
            
        except Exception as e:
            print(f"ETF 구성 종목 조회 실패 ({ticker}): {e}")
            return {"ticker": ticker, "holdings": [], "error": str(e)}
    
    def _get_known_etf_holdings(self, ticker: str) -> List[Dict]:
        """잘 알려진 ETF의 주요 구성 종목 (하드코딩)"""
        
        KNOWN_HOLDINGS = {
            "SPY": [
                {"ticker": "AAPL", "name": "Apple Inc.", "weight": 7.2},
                {"ticker": "MSFT", "name": "Microsoft Corporation", "weight": 6.8},
                {"ticker": "NVDA", "name": "NVIDIA Corporation", "weight": 4.5},
                {"ticker": "AMZN", "name": "Amazon.com Inc.", "weight": 3.8},
                {"ticker": "META", "name": "Meta Platforms Inc.", "weight": 2.5},
                {"ticker": "GOOGL", "name": "Alphabet Inc. Class A", "weight": 2.1},
                {"ticker": "GOOG", "name": "Alphabet Inc. Class C", "weight": 1.8},
                {"ticker": "BRK.B", "name": "Berkshire Hathaway Inc.", "weight": 1.7},
                {"ticker": "TSLA", "name": "Tesla Inc.", "weight": 1.5},
                {"ticker": "JPM", "name": "JPMorgan Chase & Co.", "weight": 1.3},
            ],
            "QQQ": [
                {"ticker": "AAPL", "name": "Apple Inc.", "weight": 9.5},
                {"ticker": "MSFT", "name": "Microsoft Corporation", "weight": 8.8},
                {"ticker": "NVDA", "name": "NVIDIA Corporation", "weight": 7.5},
                {"ticker": "AMZN", "name": "Amazon.com Inc.", "weight": 5.2},
                {"ticker": "META", "name": "Meta Platforms Inc.", "weight": 4.8},
                {"ticker": "GOOGL", "name": "Alphabet Inc. Class A", "weight": 2.8},
                {"ticker": "GOOG", "name": "Alphabet Inc. Class C", "weight": 2.6},
                {"ticker": "AVGO", "name": "Broadcom Inc.", "weight": 2.5},
                {"ticker": "TSLA", "name": "Tesla Inc.", "weight": 2.3},
                {"ticker": "COST", "name": "Costco Wholesale Corporation", "weight": 2.1},
            ],
            "VTI": [
                {"ticker": "AAPL", "name": "Apple Inc.", "weight": 6.5},
                {"ticker": "MSFT", "name": "Microsoft Corporation", "weight": 6.0},
                {"ticker": "NVDA", "name": "NVIDIA Corporation", "weight": 4.0},
                {"ticker": "AMZN", "name": "Amazon.com Inc.", "weight": 3.5},
                {"ticker": "META", "name": "Meta Platforms Inc.", "weight": 2.3},
                {"ticker": "GOOGL", "name": "Alphabet Inc. Class A", "weight": 1.9},
                {"ticker": "BRK.B", "name": "Berkshire Hathaway Inc.", "weight": 1.6},
                {"ticker": "GOOG", "name": "Alphabet Inc. Class C", "weight": 1.6},
                {"ticker": "TSLA", "name": "Tesla Inc.", "weight": 1.4},
                {"ticker": "JPM", "name": "JPMorgan Chase & Co.", "weight": 1.2},
            ],
            "VOO": [
                {"ticker": "AAPL", "name": "Apple Inc.", "weight": 7.2},
                {"ticker": "MSFT", "name": "Microsoft Corporation", "weight": 6.8},
                {"ticker": "NVDA", "name": "NVIDIA Corporation", "weight": 4.5},
                {"ticker": "AMZN", "name": "Amazon.com Inc.", "weight": 3.8},
                {"ticker": "META", "name": "Meta Platforms Inc.", "weight": 2.5},
                {"ticker": "GOOGL", "name": "Alphabet Inc. Class A", "weight": 2.1},
                {"ticker": "GOOG", "name": "Alphabet Inc. Class C", "weight": 1.8},
                {"ticker": "BRK.B", "name": "Berkshire Hathaway Inc.", "weight": 1.7},
                {"ticker": "TSLA", "name": "Tesla Inc.", "weight": 1.5},
                {"ticker": "JPM", "name": "JPMorgan Chase & Co.", "weight": 1.3},
            ],
            "TLT": [
                {"ticker": "US Treasury 20+ Year", "name": "미국 장기 국채 (20년 이상)", "weight": 100},
            ],
            "BND": [
                {"ticker": "US Treasury", "name": "미국 국채", "weight": 46},
                {"ticker": "Corporate", "name": "회사채", "weight": 27},
                {"ticker": "MBS", "name": "모기지 증권", "weight": 22},
                {"ticker": "Other", "name": "기타", "weight": 5},
            ],
            "GLD": [
                {"ticker": "Gold", "name": "금 현물", "weight": 100},
            ],
            "IWM": [
                {"ticker": "Russell 2000", "name": "러셀 2000 소형주", "weight": 100},
            ],
        }
        
        return KNOWN_HOLDINGS.get(ticker, [])
    
    def analyze_portfolio_with_etf_breakdown(self, holdings: Dict[str, float]) -> Dict:
        """
        ETF를 포함한 포트폴리오의 실제 구성 종목까지 분석
        
        Args:
            holdings: {티커: 비중%} 형식의 포트폴리오
        
        Returns:
            dict: 실제 구성 종목별 비중, 섹터 분포, 중복 노출 분석
        """
        # 결과 저장
        actual_holdings = {}  # 실제 종목별 비중
        etf_breakdown = {}    # ETF별 구성 상세
        individual_stocks = {}  # 개별 주식
        
        total_weight = sum(holdings.values())
        
        for ticker, weight in holdings.items():
            ticker = ticker.upper()
            normalized_weight = (weight / total_weight) * 100
            
            # ETF인지 확인 (간단한 휴리스틱)
            etf_data = self.get_etf_holdings(ticker)
            
            if etf_data.get('holdings') and len(etf_data['holdings']) > 1:
                # ETF인 경우 - 구성 종목으로 분해
                etf_breakdown[ticker] = {
                    "portfolio_weight": normalized_weight,
                    "holdings": etf_data['holdings'],
                    "name": etf_data.get('name', ticker)
                }
                
                for holding in etf_data['holdings']:
                    stock_ticker = holding.get('ticker', '')
                    stock_weight_in_etf = holding.get('weight', 0)
                    
                    # 포트폴리오 내 실제 비중 = ETF 비중 × ETF 내 종목 비중
                    actual_weight = normalized_weight * (stock_weight_in_etf / 100)
                    
                    if stock_ticker in actual_holdings:
                        actual_holdings[stock_ticker]['weight'] += actual_weight
                        actual_holdings[stock_ticker]['sources'].append(f"{ticker}({stock_weight_in_etf:.1f}%)")
                    else:
                        actual_holdings[stock_ticker] = {
                            'weight': actual_weight,
                            'name': holding.get('name', stock_ticker),
                            'sources': [f"{ticker}({stock_weight_in_etf:.1f}%)"]
                        }
            else:
                # 개별 주식인 경우
                individual_stocks[ticker] = normalized_weight
                
                if ticker in actual_holdings:
                    actual_holdings[ticker]['weight'] += normalized_weight
                    actual_holdings[ticker]['sources'].append("직접 보유")
                else:
                    # 주식 정보 가져오기
                    try:
                        stock = yf.Ticker(ticker)
                        name = stock.info.get('shortName', ticker)
                    except:
                        name = ticker
                    
                    actual_holdings[ticker] = {
                        'weight': normalized_weight,
                        'name': name,
                        'sources': ["직접 보유"]
                    }
        
        # 중복 노출 분석
        overlapping_stocks = {
            ticker: data for ticker, data in actual_holdings.items()
            if len(data['sources']) > 1
        }
        
        # 상위 10 종목
        sorted_holdings = sorted(
            actual_holdings.items(), 
            key=lambda x: x[1]['weight'], 
            reverse=True
        )[:10]
        
        # 총 분석된 비중
        analyzed_weight = sum(h['weight'] for h in actual_holdings.values())
        
        return {
            "input_portfolio": holdings,
            "actual_holdings": actual_holdings,
            "top_10_actual": [
                {
                    "ticker": ticker,
                    "name": data['name'],
                    "weight": round(data['weight'], 2),
                    "sources": data['sources']
                }
                for ticker, data in sorted_holdings
            ],
            "etf_breakdown": etf_breakdown,
            "individual_stocks": individual_stocks,
            "overlapping_stocks": {
                ticker: {
                    "weight": round(data['weight'], 2),
                    "sources": data['sources']
                }
                for ticker, data in overlapping_stocks.items()
            },
            "total_actual_holdings": len(actual_holdings),
            "analyzed_weight": round(analyzed_weight, 2),
            "summary": {
                "etf_count": len(etf_breakdown),
                "individual_count": len(individual_stocks),
                "overlapping_count": len(overlapping_stocks),
            }
        }
    
    def list_famous_portfolios(self) -> List[Dict]:
        """유명 포트폴리오 목록"""
        return [
            {
                "key": key,
                "name": value["name"],
                "creator": value["creator"],
                "description": value["description"]
            }
            for key, value in self.FAMOUS_PORTFOLIOS.items()
        ]


if __name__ == "__main__":
    analyzer = PortfolioAnalyzer()
    
    # 테스트 포트폴리오
    my_portfolio = {
        "AAPL": 25,
        "MSFT": 20,
        "GOOGL": 15,
        "VOO": 20,
        "TLT": 10,
        "GLD": 10,
    }
    
    print("=== 내 포트폴리오 분석 ===")
    metrics = analyzer.calculate_portfolio_metrics(my_portfolio)
    print(f"연간 수익률: {metrics['metrics']['annual_return']}%")
    print(f"변동성: {metrics['metrics']['volatility']}%")
    print(f"샤프비율: {metrics['metrics']['sharpe_ratio']}")
    print(f"최대 낙폭: {metrics['metrics']['max_drawdown']}%")
    
    print("\n=== 유명 포트폴리오 목록 ===")
    for pf in analyzer.list_famous_portfolios():
        print(f"- {pf['name']} ({pf['creator']})")
    
    print("\n=== 올웨더 포트폴리오 비교 ===")
    comparison = analyzer.compare_with_famous_portfolios(my_portfolio)
    print(f"내 포트폴리오 vs 올웨더:")
    if "all_weather" in comparison["famous_portfolios"]:
        aw = comparison["famous_portfolios"]["all_weather"]["metrics"]
        print(f"  올웨더 수익률: {aw['annual_return']}%")
