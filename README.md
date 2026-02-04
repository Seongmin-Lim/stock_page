# 📊 AI 기반 주식 분석 프로그램

VIX, 10년 금리, S&P Forward P/E, 공포탐욕 지수, PER, PBR 등을 활용한 종합 주식 분석 도구입니다.

## 🚀 주요 기능

### 시장 분석
- **VIX (변동성 지수)**: 시장 공포/안정 수준 측정
- **10년 국채 금리**: 금리 환경 및 채권 시장 동향
- **S&P 500 Forward P/E**: 시장 밸류에이션 수준
- **공포탐욕 지수**: CNN Fear & Greed Index 및 자체 계산

### 개별 주식 분석
- **밸류에이션**: PER, PBR, PEG, PSR 등
- **재무 지표**: 이익률, 성장률, ROE 등
- **기술적 분석**: RSI, MACD, 볼린저밴드, 이동평균 등
- **섹터 비교**: 동종 업계 평균과 비교

### AI 분석
- OpenAI GPT 또는 Anthropic Claude를 활용한 심층 분석
- 시장 상황 종합 판단
- 개별 종목 투자 의견
- 포트폴리오 추천

## 📁 프로젝트 구조

```
stock_test/
├── config/
│   ├── __init__.py
│   └── settings.py          # 설정 및 API 키
├── data_collectors/
│   ├── __init__.py
│   ├── market_data.py       # VIX, 금리, S&P 500 데이터
│   ├── fear_greed.py        # 공포탐욕 지수
│   └── stock_fundamentals.py # PER, PBR 등 기본적 분석
├── analyzers/
│   ├── __init__.py
│   ├── ai_analyzer.py       # AI 기반 분석
│   └── technical_analyzer.py # 기술적 분석
├── utils/
│   ├── __init__.py
│   ├── helpers.py           # 유틸리티 함수
│   └── visualizer.py        # 차트 생성
├── main.py                  # 메인 실행 파일
├── interactive.py           # 대화형 인터페이스
├── requirements.txt         # 의존성
├── .env.example            # 환경변수 예시
└── README.md
```

## 🛠️ 설치 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`.env.example`을 `.env`로 복사하고 API 키를 입력하세요:

```bash
cp .env.example .env
```

```env
# .env 파일
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

## 📖 사용 방법

### 대화형 모드 (권장)
```bash
python interactive.py
```

### 기본 실행
```bash
python main.py
```

### 코드에서 직접 사용
```python
from main import StockAnalyzer

# 분석기 초기화
analyzer = StockAnalyzer(ai_provider="openai")

# 시장 현황 확인
analyzer.print_market_summary()

# 개별 주식 분석
analyzer.print_stock_summary("AAPL")

# AI 시장 분석
analysis = analyzer.get_ai_market_analysis()
print(analysis)

# AI 주식 분석
stock_analysis = analyzer.get_ai_stock_analysis("MSFT")
print(stock_analysis)

# 포트폴리오 추천
recommendation = analyzer.get_portfolio_recommendation(
    tickers=["AAPL", "MSFT", "GOOGL"],
    risk_tolerance="moderate"
)
print(recommendation)

# 종합 보고서 생성
report = analyzer.generate_full_report(
    tickers=["AAPL", "MSFT", "GOOGL"],
    save=True,
    ai_analysis=True
)
```

## 📊 분석 지표 설명

### VIX (변동성 지수)
| 수준 | 값 | 의미 |
|------|-----|------|
| 매우 낮음 | < 12 | 극도의 안정/자만 |
| 낮음 | 12-17 | 낙관적 시장 |
| 보통 | 17-22 | 정상 범위 |
| 높음 | 22-30 | 불안정 |
| 매우 높음 | > 30 | 공포 (역발상 기회) |

### 공포탐욕 지수
| 수준 | 값 | 역발상 전략 |
|------|-----|------|
| 극도의 공포 | 0-25 | 매수 기회 |
| 공포 | 25-45 | 매수 고려 |
| 중립 | 45-55 | 관망 |
| 탐욕 | 55-75 | 매도 고려 |
| 극도의 탐욕 | 75-100 | 매도 기회 |

### PER (주가수익비율)
- **< 15**: 저평가 가능
- **15-20**: 적정 수준
- **> 25**: 고평가 (성장주 제외)

### PBR (주가순자산비율)
- **< 1**: 청산가치 이하 (저평가)
- **1-3**: 합리적 수준
- **> 4**: 높은 프리미엄

## ⚠️ 주의사항

1. **투자 조언이 아닙니다**: 이 프로그램은 정보 제공 목적이며, 투자 결정은 본인 책임입니다.
2. **데이터 정확성**: 실시간 데이터는 지연될 수 있으며, 일부 지표는 추정치입니다.
3. **API 비용**: AI 분석 기능은 OpenAI/Anthropic API 호출 비용이 발생합니다.

## 📝 라이센스

MIT License

## 🤝 기여

버그 리포트나 기능 제안은 Issue를 통해 제출해주세요.
