"""간단한 테스트 스크립트"""
from data_collectors import MarketDataCollector, FearGreedCollector
from data_collectors.stock_fundamentals import StockFundamentalsCollector

print("=" * 50)
print("📊 주식 분석 프로그램 테스트")
print("=" * 50)

# 시장 데이터 테스트
print("\n🔹 시장 데이터 수집 테스트")
market = MarketDataCollector()
summary = market.get_market_summary()

if summary['vix']['current']:
    print(f"  VIX: {summary['vix']['current']:.2f}")
else:
    print("  VIX: 데이터 없음")

if summary['treasury_10y']['current']:
    print(f"  10Y 금리: {summary['treasury_10y']['current']:.2f}%")
else:
    print("  10Y 금리: 데이터 없음")

if summary['sp500']['current']:
    print(f"  S&P 500: {summary['sp500']['current']:,.2f}")
else:
    print("  S&P 500: 데이터 없음")

if summary['sp500_forward_pe']:
    print(f"  S&P 500 Forward P/E: {summary['sp500_forward_pe']:.1f}")

# 공포탐욕 지수 테스트
print("\n🔹 공포탐욕 지수 테스트")
fg = FearGreedCollector()
fg_data = fg.get_fear_greed_index()
print(f"  지수: {fg_data['value']:.1f}")
print(f"  상태: {fg_data['rating']}")

# 개별 주식 테스트
print("\n🔹 AAPL 밸류에이션 테스트")
fundamentals = StockFundamentalsCollector()
aapl = fundamentals.get_stock_valuation("AAPL")
print(f"  종목: {aapl['name']}")
if aapl['current_price']:
    print(f"  현재가: ${aapl['current_price']:,.2f}")
if aapl['trailing_pe']:
    print(f"  PER: {aapl['trailing_pe']:.2f}")
if aapl['price_to_book']:
    print(f"  PBR: {aapl['price_to_book']:.2f}")

print("\n" + "=" * 50)
print("✅ 모든 테스트 완료!")
print("=" * 50)
print("\n💡 사용법:")
print("  - 대화형 모드: python interactive.py")
print("  - 기본 실행: python main.py")
print("\n⚠️ AI 분석을 사용하려면 .env 파일에 API 키를 설정하세요.")
