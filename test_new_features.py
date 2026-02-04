"""
새로운 기능 테스트 스크립트
"""
from main import StockAnalyzer

def test_economic_cycle():
    """경제 사이클 분석 테스트"""
    print("=" * 50)
    print("🔄 경제 사이클 분석 테스트")
    print("=" * 50)
    
    analyzer = StockAnalyzer(ai_provider="grok")
    
    # 경제 사이클 분석
    cycle = analyzer.get_economic_cycle()
    
    print(f"\n현재 경제 단계: {cycle['current_phase']}")
    print(f"신뢰도: {cycle['confidence']}%")
    print(f"설명: {cycle['description'][:100]}...")
    
    # 동적 조정값
    adj = cycle.get('dynamic_adjustments', {})
    print(f"\n📊 동적 조정값:")
    print(f"  적정 PER: {adj.get('adjusted_per_fair', 20)}")
    print(f"  VIX 경계: {adj.get('adjusted_vix_threshold', 25)}")
    print(f"  PER 배수: {adj.get('per_multiplier', 1.0)}")
    
    # 추천 자산 배분
    allocation = cycle.get('recommendations', {}).get('asset_allocation', {})
    print(f"\n📈 추천 자산 배분:")
    for asset, weight in allocation.items():
        print(f"  {asset}: {weight}%")
    
    return True


def test_portfolio_comparison():
    """포트폴리오 비교 테스트"""
    print("\n" + "=" * 50)
    print("📊 포트폴리오 비교 테스트")
    print("=" * 50)
    
    analyzer = StockAnalyzer(ai_provider="grok")
    
    # 예시 포트폴리오
    user_holdings = {
        "SPY": 40.0,
        "QQQ": 30.0,
        "TLT": 20.0,
        "GLD": 10.0
    }
    
    print(f"\n테스트 포트폴리오: {user_holdings}")
    
    # 포트폴리오 비교
    comparison = analyzer.compare_portfolio(user_holdings)
    
    print(f"\n비교 결과:")
    famous = comparison['comparison'].get('famous_portfolios', {})
    
    for name, data in list(famous.items())[:3]:
        info = data.get('info', {})
        print(f"\n  📌 {info.get('name', name)}")
        print(f"     설명: {info.get('description', 'N/A')}")
        print(f"     창시자: {info.get('creator', 'N/A')}")
    
    print(f"\n경제 사이클 기반 추천 배분:")
    rec_allocation = comparison.get('economic_cycle', {}).get('recommended_allocation', {})
    for asset, weight in rec_allocation.items():
        print(f"  {asset}: {weight}%")
    
    return True


def test_news_collection():
    """뉴스 수집 테스트"""
    print("\n" + "=" * 50)
    print("📰 뉴스 수집 테스트")
    print("=" * 50)
    
    analyzer = StockAnalyzer(ai_provider="grok")
    
    news = analyzer.get_news_summary()
    
    print(f"\n뉴스 수집 결과:")
    print(f"  총 뉴스 수: {len(news.get('articles', []))}")
    
    sentiment = news.get('sentiment', {})
    print(f"\n감성 분석:")
    print(f"  전반적 감성: {sentiment.get('overall', 'N/A')}")
    print(f"  긍정: {sentiment.get('positive', 0)}개")
    print(f"  부정: {sentiment.get('negative', 0)}개")
    print(f"  중립: {sentiment.get('neutral', 0)}개")
    
    print(f"\n최근 뉴스 헤드라인:")
    for i, article in enumerate(news.get('articles', [])[:3], 1):
        print(f"  {i}. {article.get('title', 'N/A')[:60]}...")
    
    return True


def test_report_generator():
    """보고서 생성 테스트"""
    print("\n" + "=" * 50)
    print("📄 보고서 생성 테스트")
    print("=" * 50)
    
    from utils import ReportGenerator
    
    generator = ReportGenerator()
    
    # 테스트 데이터
    test_data = {
        "test": True,
        "timestamp": "2024-01-01T00:00:00",
        "market_data": {"vix": 15.0}
    }
    
    # 보고서 저장 테스트
    path = generator.save_market_analysis(test_data)
    print(f"\n✅ 시장 분석 보고서 저장됨: {path}")
    
    # 보고서 목록
    reports = generator.list_reports(days=1)
    print(f"\n📁 저장된 보고서 수: {len(reports)}")
    
    return True


def main():
    """모든 테스트 실행"""
    print("\n🚀 새로운 기능 테스트 시작\n")
    
    tests = [
        ("경제 사이클 분석", test_economic_cycle),
        ("포트폴리오 비교", test_portfolio_comparison),
        ("뉴스 수집", test_news_collection),
        ("보고서 생성", test_report_generator),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "✅ 성공"))
        except Exception as e:
            results.append((name, f"❌ 실패: {e}"))
            import traceback
            traceback.print_exc()
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📋 테스트 결과 요약")
    print("=" * 50)
    
    for name, result in results:
        print(f"  {name}: {result}")
    
    print("\n✅ 테스트 완료!")


if __name__ == "__main__":
    main()
