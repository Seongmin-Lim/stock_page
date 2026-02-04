"""
주식 분석 메인 모듈
VIX, 10Y 금리, S&P F-P/E, 공포탐욕 지수, PER, PBR 등을 종합 분석
경제 사이클 분석, 뉴스 분석, 포트폴리오 비교 기능 포함
"""
import json
from datetime import datetime
from typing import List, Optional, Dict

from data_collectors import (
    MarketDataCollector, FearGreedCollector, StockFundamentalsCollector,
    NewsCollector, EconomicCycleAnalyzer
)
from analyzers import AIAnalyzer, TechnicalAnalyzer, PortfolioAnalyzer
from utils import StockVisualizer, ReportGenerator
from utils.helpers import (
    interpret_vix, interpret_fear_greed, interpret_per, interpret_pbr,
    format_number, format_percent
)
from config.settings import SAVE_REPORTS


class StockAnalyzer:
    """종합 주식 분석 클래스"""
    
    def __init__(self, ai_provider: str = "grok"):
        self.market_collector = MarketDataCollector()
        self.fear_greed_collector = FearGreedCollector()
        self.fundamentals_collector = StockFundamentalsCollector()
        self.news_collector = NewsCollector()
        self.economic_analyzer = EconomicCycleAnalyzer()
        self.ai_analyzer = AIAnalyzer(provider=ai_provider)
        self.technical_analyzer = TechnicalAnalyzer()
        self.portfolio_analyzer = PortfolioAnalyzer()
        self.visualizer = StockVisualizer()
        self.report_generator = ReportGenerator()
        
        # 경제 사이클 캐시
        self._economic_cycle_cache = None
    
    def get_economic_cycle(self, refresh: bool = False) -> Dict:
        """경제 사이클 분석 (캐시 사용)"""
        if self._economic_cycle_cache is None or refresh:
            print("🔄 경제 사이클 분석 중...")
            self._economic_cycle_cache = self.economic_analyzer.analyze_economic_cycle()
        return self._economic_cycle_cache
    
    def get_market_overview(self) -> dict:
        """시장 전체 개요 수집"""
        print("📊 시장 데이터 수집 중...")
        
        # 시장 요약 데이터
        market_summary = self.market_collector.get_market_summary()
        
        # 공포탐욕 지수
        fear_greed = self.fear_greed_collector.get_fear_greed_index()
        
        # 경제 사이클
        economic_cycle = self.get_economic_cycle()
        
        # VIX 해석
        vix_interpretation = interpret_vix(market_summary['vix']['current']) if market_summary['vix']['current'] else {}
        
        # 공포탐욕 해석
        fg_interpretation = interpret_fear_greed(fear_greed['value']) if fear_greed['value'] else {}
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "market_data": {
                "vix": {
                    **market_summary['vix'],
                    "interpretation": vix_interpretation
                },
                "treasury_10y": market_summary['treasury_10y'],
                "sp500": market_summary['sp500'],
                "sp500_forward_pe": market_summary['sp500_forward_pe'],
            },
            "fear_greed_index": {
                **fear_greed,
                "interpretation": fg_interpretation
            },
            "economic_cycle": {
                "phase": economic_cycle['current_phase'],
                "confidence": economic_cycle['confidence'],
                "description": economic_cycle['description'],
            }
        }
        
        # 보고서 저장
        if SAVE_REPORTS:
            self.report_generator.save_market_analysis(result)
        
        return result
    
    def get_news_summary(self) -> Dict:
        """뉴스 수집 및 요약"""
        print("📰 뉴스 수집 중...")
        news_summary = self.news_collector.get_news_summary()
        
        if SAVE_REPORTS:
            self.report_generator.save_news_analysis(news_summary)
        
        return news_summary
    
    def analyze_stock(self, ticker: str, include_technical: bool = True) -> dict:
        """개별 주식 종합 분석"""
        print(f"📈 {ticker} 분석 중...")
        
        # 기본적 분석
        valuation = self.fundamentals_collector.get_stock_valuation(ticker)
        
        # 섹터 비교
        sector_comparison = self.fundamentals_collector.compare_to_sector(ticker)
        
        # 성장 지표
        growth = self.fundamentals_collector.get_growth_metrics(ticker)
        
        # 기술적 분석
        technical = None
        if include_technical:
            technical = self.technical_analyzer.analyze_ticker(ticker)
        
        # 경제 사이클 반영 PER/PBR 해석
        economic_cycle = self.get_economic_cycle()
        adjusted_per = economic_cycle.get('dynamic_adjustments', {}).get('adjusted_per_fair', 20)
        
        per_interp = interpret_per(valuation.get('trailing_pe'), adjusted_per)
        pbr_interp = interpret_pbr(valuation.get('price_to_book'))
        
        result = {
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "valuation": {
                **valuation,
                "per_interpretation": per_interp,
                "pbr_interpretation": pbr_interp,
                "adjusted_fair_per": adjusted_per,
            },
            "sector_comparison": sector_comparison,
            "growth_metrics": growth,
            "technical_analysis": technical,
            "economic_context": {
                "phase": economic_cycle['current_phase'],
                "per_adjustment": economic_cycle.get('dynamic_adjustments', {}).get('per_multiplier', 1.0)
            }
        }
        
        if SAVE_REPORTS:
            self.report_generator.save_stock_analysis(ticker, result)
        
        return result
    
    def analyze_multiple_stocks(self, tickers: List[str]) -> List[dict]:
        """여러 주식 분석"""
        results = []
        for ticker in tickers:
            try:
                result = self.analyze_stock(ticker)
                results.append(result)
            except Exception as e:
                print(f"❌ {ticker} 분석 실패: {e}")
                results.append({"ticker": ticker, "error": str(e)})
        return results
    
    def compare_portfolio(self, user_holdings: Dict[str, float], period: str = "1y") -> Dict:
        """포트폴리오 비교 분석"""
        print("📊 포트폴리오 비교 분석 중...")
        
        comparison = self.portfolio_analyzer.compare_with_famous_portfolios(user_holdings, period)
        economic_cycle = self.get_economic_cycle()
        
        # 경제 사이클 기반 추천
        recommendations = self.portfolio_analyzer.get_portfolio_recommendations(
            user_holdings,
            economic_phase=economic_cycle['current_phase']
        )
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "comparison": comparison,
            "recommendations": recommendations,
            "economic_cycle": {
                "phase": economic_cycle['current_phase'],
                "recommended_allocation": economic_cycle.get('recommendations', {}).get('asset_allocation', {})
            }
        }
        
        if SAVE_REPORTS:
            self.report_generator.save_portfolio_analysis(result)
        
        return result
    
    def get_ai_market_analysis(self, include_news: bool = True) -> str:
        """AI 기반 시장 분석"""
        print("🤖 AI 시장 분석 중...")
        
        market_overview = self.get_market_overview()
        economic_cycle = self.get_economic_cycle()
        
        if include_news:
            news_summary = self.get_news_summary()
            analysis = self.ai_analyzer.analyze_with_news(
                market_overview, news_summary, economic_cycle
            )
        else:
            analysis = self.ai_analyzer.analyze_market_conditions(
                market_overview, economic_cycle
            )
        
        if SAVE_REPORTS:
            self.report_generator.save_ai_analysis(
                "market", analysis, 
                {"include_news": include_news}
            )
        
        return analysis
    
    def get_ai_stock_analysis(self, ticker: str) -> str:
        """AI 기반 개별 주식 분석"""
        print(f"🤖 AI {ticker} 분석 중...")
        
        stock_data = self.analyze_stock(ticker)
        market_context = self.get_market_overview()
        economic_cycle = self.get_economic_cycle()
        
        analysis = self.ai_analyzer.analyze_stock(
            stock_data, market_context, economic_cycle
        )
        
        if SAVE_REPORTS:
            self.report_generator.save_ai_analysis(
                f"stock_{ticker}", analysis,
                {"ticker": ticker}
            )
        
        return analysis
    
    def get_ai_comparison(self, tickers: List[str]) -> str:
        """AI 기반 주식 비교 분석"""
        print(f"🤖 AI 비교 분석 중: {', '.join(tickers)}")
        
        stocks_data = self.analyze_multiple_stocks(tickers)
        economic_cycle = self.get_economic_cycle()
        
        return self.ai_analyzer.compare_stocks(stocks_data, economic_cycle)
    
    def get_ai_portfolio_analysis(self, user_holdings: Dict[str, float]) -> str:
        """AI 기반 포트폴리오 분석"""
        print("🤖 AI 포트폴리오 분석 중...")
        
        portfolio_comparison = self.compare_portfolio(user_holdings)
        economic_cycle = self.get_economic_cycle()
        
        analysis = self.ai_analyzer.analyze_portfolio_comparison(
            portfolio_comparison, economic_cycle
        )
        
        if SAVE_REPORTS:
            self.report_generator.save_ai_analysis(
                "portfolio", analysis,
                {"holdings": user_holdings}
            )
        
        return analysis
    
    def get_portfolio_recommendation(self, 
                                     tickers: List[str],
                                     risk_tolerance: str = "moderate") -> str:
        """AI 기반 포트폴리오 추천"""
        print(f"🤖 포트폴리오 추천 생성 중...")
        
        market_data = self.get_market_overview()
        fear_greed = self.fear_greed_collector.get_fear_greed_index()
        stocks_data = self.analyze_multiple_stocks(tickers)
        economic_cycle = self.get_economic_cycle()
        
        return self.ai_analyzer.generate_portfolio_recommendation(
            market_data, fear_greed, stocks_data, economic_cycle, risk_tolerance
        )
    
    def explain_economic_cycle(self) -> str:
        """경제 사이클 AI 설명"""
        economic_cycle = self.get_economic_cycle()
        return self.ai_analyzer.explain_economic_cycle(economic_cycle)
    
    def show_market_dashboard(self):
        """시장 대시보드 시각화"""
        market_overview = self.get_market_overview()
        
        dashboard_data = {
            'vix': market_overview['market_data']['vix'],
            'treasury_10y': market_overview['market_data']['treasury_10y'],
            'sp500_forward_pe': market_overview['market_data']['sp500_forward_pe'],
            'fear_greed': market_overview['fear_greed_index']
        }
        
        self.visualizer.plot_market_dashboard(dashboard_data)
    
    def generate_full_report(self, 
                            tickers: List[str], 
                            user_holdings: Dict[str, float] = None,
                            ai_analysis: bool = True) -> dict:
        """종합 보고서 생성"""
        print("=" * 50)
        print("📊 종합 주식 분석 보고서 생성")
        print("=" * 50)
        
        # 경제 사이클
        economic_cycle = self.get_economic_cycle()
        
        # 시장 개요
        market_overview = self.get_market_overview()
        
        # 뉴스 요약
        news_summary = self.get_news_summary()
        
        # 주식 분석
        stocks_analysis = self.analyze_multiple_stocks(tickers)
        
        report = {
            "report_date": datetime.now().isoformat(),
            "economic_cycle": economic_cycle,
            "market_overview": market_overview,
            "news_summary": news_summary,
            "stocks_analysis": stocks_analysis,
        }
        
        # 포트폴리오 비교
        if user_holdings:
            portfolio_analysis = self.compare_portfolio(user_holdings)
            report["portfolio_analysis"] = portfolio_analysis
        
        # AI 분석
        ai_analysis_text = None
        if ai_analysis:
            try:
                ai_analysis_text = self.get_ai_market_analysis(include_news=True)
                report["ai_market_analysis"] = ai_analysis_text
            except Exception as e:
                print(f"⚠️ AI 분석 실패: {e}")
                report["ai_analysis_error"] = str(e)
        
        # 마크다운 보고서 생성
        md_path = self.report_generator.generate_markdown_report(
            market_overview,
            economic_cycle,
            news_summary,
            report.get("portfolio_analysis"),
            ai_analysis_text
        )
        print(f"✅ 마크다운 보고서: {md_path}")
        
        # JSON 보고서 저장
        json_path = self.report_generator.save_daily_report(report)
        print(f"✅ JSON 보고서: {json_path}")
        
        # 엑셀 보고서 생성
        try:
            excel_path = self.report_generator.generate_excel_report(
                market_overview, stocks_analysis, 
                report.get("portfolio_analysis")
            )
            print(f"✅ 엑셀 보고서: {excel_path}")
        except Exception as e:
            print(f"⚠️ 엑셀 보고서 생성 실패: {e}")
        
        return report
    
    def print_economic_cycle_summary(self):
        """경제 사이클 요약 출력"""
        cycle = self.get_economic_cycle()
        
        print("\n" + "=" * 50)
        print("🔄 경제 사이클 분석")
        print("=" * 50)
        
        print(f"\n현재 단계: {cycle['current_phase']}")
        print(f"신뢰도: {cycle['confidence']}%")
        print(f"\n{cycle['description']}")
        
        print(f"\n📊 주요 지표:")
        indicators = cycle.get('indicators', {})
        if 'vix' in indicators:
            print(f"  VIX: {indicators['vix'].get('current', 'N/A'):.2f}")
        if 'yield_curve' in indicators:
            print(f"  금리 곡선: {indicators['yield_curve'].get('status', 'N/A')}")
        if 'market_trend' in indicators:
            print(f"  시장 트렌드: {indicators['market_trend'].get('trend', 'N/A')}")
        
        print(f"\n💡 추천 섹터: {', '.join(cycle.get('recommendations', {}).get('sectors', []))}")
        
        print(f"\n📈 추천 자산 배분:")
        allocation = cycle.get('recommendations', {}).get('asset_allocation', {})
        for asset, weight in allocation.items():
            print(f"  {asset}: {weight}%")
        
        print(f"\n🎯 조정된 기준값:")
        adj = cycle.get('dynamic_adjustments', {})
        print(f"  적정 PER: {adj.get('adjusted_per_fair', 20)}")
        print(f"  VIX 경계: {adj.get('adjusted_vix_threshold', 25)}")
        
        outlook = cycle.get('market_outlook', {})
        print(f"\n🔮 시장 전망:")
        for key, value in outlook.items():
            print(f"  {key}: {value}")
        
        print("\n" + "=" * 50)
    
    def print_market_summary(self):
        """시장 요약 출력"""
        overview = self.get_market_overview()
        
        print("\n" + "=" * 50)
        print("📊 시장 요약")
        print("=" * 50)
        
        # 경제 사이클
        print(f"\n🔄 경제 사이클: {overview['economic_cycle']['phase']} (신뢰도: {overview['economic_cycle']['confidence']}%)")
        
        # VIX
        vix_data = overview['market_data']['vix']
        print(f"\n🔸 VIX (변동성 지수)")
        print(f"   현재: {vix_data['current']:.2f}")
        print(f"   상태: {vix_data['interpretation'].get('level', 'N/A')}")
        print(f"   투자 심리: {vix_data['interpretation'].get('sentiment', 'N/A')}")
        
        # 10년 금리
        tnx_data = overview['market_data']['treasury_10y']
        print(f"\n🔸 10년 국채 금리")
        print(f"   현재: {tnx_data['current']:.2f}%")
        
        # S&P 500
        sp500_data = overview['market_data']['sp500']
        print(f"\n🔸 S&P 500")
        print(f"   현재: {sp500_data['current']:,.2f}")
        fpe = overview['market_data']['sp500_forward_pe']
        print(f"   Forward P/E: {fpe:.1f}" if fpe else "   Forward P/E: N/A")
        
        # 공포탐욕 지수
        fg_data = overview['fear_greed_index']
        print(f"\n🔸 공포탐욕 지수")
        print(f"   현재: {fg_data['value']:.0f}")
        print(f"   상태: {fg_data['rating']}")
        print(f"   역발상 관점: {fg_data['interpretation'].get('contrarian_view', 'N/A')}")
        
        print("\n" + "=" * 50)
    
    def print_stock_summary(self, ticker: str):
        """주식 요약 출력"""
        analysis = self.analyze_stock(ticker)
        
        print("\n" + "=" * 50)
        print(f"📈 {ticker} 분석 요약")
        print("=" * 50)
        
        val = analysis['valuation']
        
        print(f"\n🏢 {val.get('name', ticker)}")
        print(f"   현재가: ${val['current_price']:,.2f}" if val['current_price'] else "   현재가: N/A")
        
        print(f"\n📊 밸류에이션 (경제 단계: {analysis['economic_context']['phase']})")
        print(f"   PER: {val['trailing_pe']:.2f} ({val['per_interpretation']})" if val['trailing_pe'] else "   PER: N/A")
        print(f"   조정 적정 PER: {val['adjusted_fair_per']:.1f}")
        print(f"   Forward PER: {val['forward_pe']:.2f}" if val['forward_pe'] else "   Forward PER: N/A")
        print(f"   PBR: {val['price_to_book']:.2f} ({val['pbr_interpretation']})" if val['price_to_book'] else "   PBR: N/A")
        print(f"   PEG: {val['peg_ratio']:.2f}" if val['peg_ratio'] else "   PEG: N/A")
        
        print(f"\n💰 수익성")
        print(f"   이익률: {format_percent(val['profit_margin'])}" if val['profit_margin'] else "   이익률: N/A")
        print(f"   영업이익률: {format_percent(val['operating_margin'])}" if val['operating_margin'] else "   영업이익률: N/A")
        
        print(f"\n📈 성장성")
        growth = analysis['growth_metrics']
        print(f"   매출 성장률: {format_percent(growth['revenue_growth'])}" if growth['revenue_growth'] else "   매출 성장률: N/A")
        print(f"   이익 성장률: {format_percent(growth['earnings_growth'])}" if growth['earnings_growth'] else "   이익 성장률: N/A")
        
        # 기술적 분석
        if analysis['technical_analysis']:
            tech = analysis['technical_analysis']
            print(f"\n📉 기술적 분석")
            print(f"   RSI: {tech['momentum']['rsi_14']} ({tech['momentum']['rsi_signal']})")
            print(f"   트렌드: {tech['trend']['short_term']} (단기), {tech['trend']['medium_term']} (중기)")
            print(f"   신호: {tech['signals']['overall']}")
        
        print("\n" + "=" * 50)
    
    def print_portfolio_comparison(self, user_holdings: Dict[str, float]):
        """포트폴리오 비교 출력"""
        comparison = self.compare_portfolio(user_holdings)
        
        print("\n" + "=" * 50)
        print("📊 포트폴리오 비교 분석")
        print("=" * 50)
        
        # 내 포트폴리오 성과
        user_metrics = comparison['comparison'].get('user_portfolio', {}).get('metrics', {})
        print(f"\n🔸 내 포트폴리오 성과")
        print(f"   연간 수익률: {user_metrics.get('annual_return', 'N/A')}%")
        print(f"   변동성: {user_metrics.get('volatility', 'N/A')}%")
        print(f"   샤프비율: {user_metrics.get('sharpe_ratio', 'N/A')}")
        print(f"   최대 낙폭: {user_metrics.get('max_drawdown', 'N/A')}%")
        
        # 유명 포트폴리오 비교
        print(f"\n🔸 유명 포트폴리오 대비")
        famous = comparison['comparison'].get('famous_portfolios', {})
        for name, data in list(famous.items())[:4]:
            metrics = data.get('metrics', {})
            print(f"\n   {data.get('info', {}).get('name', name)}:")
            print(f"     수익률: {metrics.get('annual_return', 'N/A')}% | 샤프: {metrics.get('sharpe_ratio', 'N/A')}")
        
        # 종합 평가
        summary = comparison['comparison'].get('comparison', {}).get('summary', {})
        print(f"\n🏆 종합 평가:")
        for key, value in summary.items():
            print(f"   {value}")
        
        # 추천
        recommendations = comparison.get('recommendations', {})
        adjustments = recommendations.get('adjustments_needed', [])
        if adjustments:
            print(f"\n💡 추천 조정:")
            for adj in adjustments[:3]:
                print(f"   {adj['asset']}: {adj['current']:.1f}% → {adj['recommended']:.1f}% ({adj['action']} {adj['amount']:.1f}%)")
        
        print("\n" + "=" * 50)
    
    def list_saved_reports(self, days: int = 7):
        """저장된 보고서 목록"""
        reports = self.report_generator.list_reports(days=days)
        
        print(f"\n📁 최근 {days}일 저장된 보고서: {len(reports)}개")
        print("-" * 50)
        
        for report in reports[:10]:
            print(f"  [{report['category']}] {report['filename']}")
            print(f"           생성: {report['created'][:16]}")
        
        if len(reports) > 10:
            print(f"  ... 외 {len(reports) - 10}개")


def main():
    """메인 실행 함수"""
    print("\n🚀 주식 분석 프로그램 시작")
    print("=" * 50)
    
    # 분석기 초기화
    analyzer = StockAnalyzer(ai_provider="grok")  # grok 또는 gemini
    
    # 1. 경제 사이클 출력
    analyzer.print_economic_cycle_summary()
    
    # 2. 시장 요약 출력
    analyzer.print_market_summary()
    
    # 3. 개별 주식 분석 예시
    sample_tickers = ["AAPL", "MSFT", "GOOGL"]
    
    for ticker in sample_tickers[:1]:  # 첫 번째만 출력
        analyzer.print_stock_summary(ticker)
    
    # 4. AI 분석 (API 키가 설정된 경우)
    try:
        print("\n🤖 AI 시장 분석:")
        print("-" * 40)
        ai_analysis = analyzer.get_ai_market_analysis(include_news=True)
        print(ai_analysis)
    except Exception as e:
        print(f"⚠️ AI 분석을 위해 .env 파일에 API 키를 설정하세요: {e}")
    
    print("\n✅ 분석 완료!")


if __name__ == "__main__":
    main()
