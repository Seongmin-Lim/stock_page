"""
대화형 주식 분석 인터페이스
경제 사이클, 뉴스 분석, 포트폴리오 비교 기능 포함
"""
from main import StockAnalyzer
from config.settings import AI_PROVIDER


def print_menu():
    """메뉴 출력"""
    print("\n" + "=" * 50)
    print("📊 주식 분석 프로그램")
    print("=" * 50)
    print("1.  시장 현황 보기")
    print("2.  경제 사이클 분석")
    print("3.  개별 주식 분석")
    print("4.  여러 주식 비교")
    print("5.  뉴스 요약 보기")
    print("6.  포트폴리오 비교 (대가들)")
    print("-" * 30)
    print("7.  AI 시장 분석")
    print("8.  AI 주식 분석")
    print("9.  AI 포트폴리오 추천")
    print("10. AI 경제 사이클 설명")
    print("-" * 30)
    print("11. 시장 대시보드 (차트)")
    print("12. 종합 보고서 생성")
    print("13. 저장된 보고서 목록")
    print("0.  종료")
    print("=" * 50)


def select_ai_provider() -> str:
    """AI 제공자 선택"""
    print("\nAI 제공자를 선택하세요:")
    print("1. Grok (xAI) - 추천")
    print("2. Gemini (Google)")
    print("3. OpenAI (GPT)")
    print("4. Anthropic (Claude)")
    
    choice = input("선택 (1/2/3/4, 기본: 1): ").strip() or "1"
    
    providers = {
        "1": "grok",
        "2": "gemini", 
        "3": "openai",
        "4": "anthropic"
    }
    
    return providers.get(choice, "grok")


def input_portfolio() -> dict:
    """사용자 포트폴리오 입력"""
    print("\n포트폴리오를 입력하세요 (예: AAPL:30,MSFT:25,BND:45)")
    print("형식: 티커:비중%, 쉼표로 구분")
    print("또는 'default'를 입력하면 예시 포트폴리오 사용")
    
    user_input = input("\n입력: ").strip()
    
    if user_input.lower() == 'default':
        return {
            "SPY": 40.0,
            "QQQ": 20.0,
            "TLT": 25.0,
            "GLD": 10.0,
            "VNQ": 5.0
        }
    
    holdings = {}
    try:
        for item in user_input.split(","):
            ticker, weight = item.strip().split(":")
            holdings[ticker.upper()] = float(weight)
    except:
        print("❌ 입력 형식이 올바르지 않습니다. 예시 포트폴리오를 사용합니다.")
        return {
            "SPY": 40.0,
            "QQQ": 20.0,
            "TLT": 25.0,
            "GLD": 10.0,
            "VNQ": 5.0
        }
    
    return holdings


def main():
    """대화형 메인 함수"""
    print("\n🚀 주식 분석 프로그램 시작")
    print("=" * 50)
    print("경제 사이클 분석 | 뉴스 분석 | 대가 포트폴리오 비교")
    print("=" * 50)
    
    # AI 제공자 선택
    ai_provider = select_ai_provider()
    print(f"\n✅ {ai_provider.upper()} 선택됨")
    
    # 분석기 초기화
    print("\n🔄 분석기 초기화 중...")
    analyzer = StockAnalyzer(ai_provider=ai_provider)
    
    while True:
        print_menu()
        choice = input("\n선택: ").strip()
        
        try:
            if choice == "1":
                # 시장 현황
                analyzer.print_market_summary()
            
            elif choice == "2":
                # 경제 사이클 분석
                analyzer.print_economic_cycle_summary()
            
            elif choice == "3":
                # 개별 주식 분석
                ticker = input("티커 입력 (예: AAPL): ").strip().upper()
                if ticker:
                    analyzer.print_stock_summary(ticker)
            
            elif choice == "4":
                # 여러 주식 비교
                tickers_input = input("티커 입력 (쉼표로 구분, 예: AAPL,MSFT,GOOGL): ").strip().upper()
                tickers = [t.strip() for t in tickers_input.split(",") if t.strip()]
                
                if tickers:
                    results = analyzer.analyze_multiple_stocks(tickers)
                    
                    print("\n📊 비교 결과")
                    print("-" * 90)
                    print(f"{'티커':<10} {'현재가':<12} {'PER':<10} {'PBR':<10} {'이익률':<12} {'경제 사이클':<15}")
                    print("-" * 90)
                    
                    for r in results:
                        if 'error' not in r:
                            val = r['valuation']
                            price = f"${val['current_price']:,.2f}" if val['current_price'] else "N/A"
                            per = f"{val['trailing_pe']:.1f}" if val['trailing_pe'] else "N/A"
                            pbr = f"{val['price_to_book']:.2f}" if val['price_to_book'] else "N/A"
                            margin = f"{val['profit_margin']*100:.1f}%" if val['profit_margin'] else "N/A"
                            phase = r.get('economic_context', {}).get('phase', 'N/A')
                            print(f"{r['ticker']:<10} {price:<12} {per:<10} {pbr:<10} {margin:<12} {phase:<15}")
            
            elif choice == "5":
                # 뉴스 요약
                print("\n📰 뉴스 수집 중...")
                news = analyzer.get_news_summary()
                
                print("\n" + "=" * 50)
                print("📰 최근 시장 뉴스")
                print("=" * 50)
                
                print(f"\n🎯 시장 감성: {news.get('sentiment', {}).get('overall', 'N/A')}")
                print(f"   긍정: {news.get('sentiment', {}).get('positive', 0)}개")
                print(f"   부정: {news.get('sentiment', {}).get('negative', 0)}개")
                print(f"   중립: {news.get('sentiment', {}).get('neutral', 0)}개")
                
                print("\n📌 주요 뉴스:")
                for i, article in enumerate(news.get('articles', [])[:5], 1):
                    print(f"\n{i}. {article.get('title', 'N/A')}")
                    print(f"   출처: {article.get('source', 'N/A')}")
                    if article.get('published'):
                        print(f"   발행: {article['published']}")
            
            elif choice == "6":
                # 포트폴리오 비교
                user_holdings = input_portfolio()
                print(f"\n입력된 포트폴리오: {user_holdings}")
                
                analyzer.print_portfolio_comparison(user_holdings)
            
            elif choice == "7":
                # AI 시장 분석
                include_news = input("뉴스 분석 포함? (y/n, 기본: y): ").strip().lower() != 'n'
                
                print("\n🤖 AI 시장 분석 중...")
                analysis = analyzer.get_ai_market_analysis(include_news=include_news)
                print("\n" + "=" * 50)
                print(analysis)
                print("=" * 50)
            
            elif choice == "8":
                # AI 주식 분석
                ticker = input("티커 입력 (예: AAPL): ").strip().upper()
                if ticker:
                    print(f"\n🤖 AI {ticker} 분석 중...")
                    analysis = analyzer.get_ai_stock_analysis(ticker)
                    print("\n" + "=" * 50)
                    print(analysis)
                    print("=" * 50)
            
            elif choice == "9":
                # AI 포트폴리오 추천
                user_holdings = input_portfolio()
                
                print(f"\n입력된 포트폴리오: {user_holdings}")
                print("\n🤖 AI 포트폴리오 분석 중...")
                
                analysis = analyzer.get_ai_portfolio_analysis(user_holdings)
                print("\n" + "=" * 50)
                print(analysis)
                print("=" * 50)
            
            elif choice == "10":
                # AI 경제 사이클 설명
                print("\n🤖 AI 경제 사이클 설명 중...")
                explanation = analyzer.explain_economic_cycle()
                print("\n" + "=" * 50)
                print(explanation)
                print("=" * 50)
            
            elif choice == "11":
                # 시장 대시보드
                print("\n📊 시장 대시보드 생성 중...")
                analyzer.show_market_dashboard()
            
            elif choice == "12":
                # 종합 보고서
                tickers_input = input("분석할 티커 입력 (쉼표로 구분): ").strip().upper()
                tickers = [t.strip() for t in tickers_input.split(",") if t.strip()]
                
                if not tickers:
                    tickers = ["AAPL", "MSFT", "GOOGL"]
                    print(f"기본 티커 사용: {tickers}")
                
                portfolio_input = input("\n포트폴리오 비교 포함? (y/n, 기본: n): ").strip().lower()
                user_holdings = None
                if portfolio_input == 'y':
                    user_holdings = input_portfolio()
                
                ai_choice = input("AI 분석 포함? (y/n, 기본: y): ").strip().lower()
                include_ai = ai_choice != 'n'
                
                print("\n📊 종합 보고서 생성 중...")
                report = analyzer.generate_full_report(
                    tickers, 
                    user_holdings=user_holdings,
                    ai_analysis=include_ai
                )
                print("\n✅ 보고서가 생성되었습니다!")
                print("📁 reports 폴더에서 확인하세요.")
            
            elif choice == "13":
                # 저장된 보고서 목록
                days = input("며칠간의 보고서를 볼까요? (기본: 7): ").strip()
                days = int(days) if days.isdigit() else 7
                analyzer.list_saved_reports(days=days)
            
            elif choice == "0":
                print("\n👋 프로그램을 종료합니다.")
                break
            
            else:
                print("\n❌ 잘못된 선택입니다.")
        
        except KeyboardInterrupt:
            print("\n\n👋 프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            print("\n계속하려면 Enter를 누르세요...")
            input()


if __name__ == "__main__":
    main()
