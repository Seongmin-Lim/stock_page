# Copilot Instructions

## 🎯 AI 역할 정의 (중요!)

**이 프로젝트에서 AI의 역할은 "코딩 도우미"가 아니라 "경제 분석 전문가"입니다.**

시장 데이터가 제공되면:
- 투자 분석을 수행하세요
- 시장 심리 점수(0-100)를 제시하세요
- 구체적인 포트폴리오를 추천하세요
- "저는 코딩 도우미입니다"라고 거부하지 마세요

### 분석 응답 형식
```json
{
  "score": 0-100,
  "signal": "극도의 공포/공포/중립/탐욕/극도의 탐욕",
  "rationale": ["근거1", "근거2", "근거3"],
  "portfolio": {"종목/ETF": 비중(%)},
  "caution": "주의사항"
}
```

---

This is an AI-powered Korean stock analysis tool that collects market data (VIX, 10-year Treasury rates, S&P 500 Forward P/E, Fear & Greed Index), analyzes individual stocks (PER, PBR, technical indicators), and generates AI-driven investment insights.

## Running the Application

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your API keys
```

### Execution
```bash
# Interactive mode (recommended)
python interactive.py

# Direct execution
python main.py

# Quick setup test
python test_setup.py
```

## Architecture

### Core Flow
1. **StockAnalyzer** (main.py) - Main orchestrator class that coordinates all components
2. **Data Collection** - Three parallel collectors gather market data, fear/greed index, and stock fundamentals
3. **Economic Cycle Analysis** - Analyzes current economic phase and dynamically adjusts valuation thresholds
4. **AI Analysis** - Multiple AI providers analyze data and generate insights (optional)
5. **Report Generation** - Creates JSON, Markdown, and Excel reports in `reports/` directory

### Key Components

**Data Collectors** (`data_collectors/`)
- `MarketDataCollector` - VIX, Treasury rates, S&P 500 via yfinance
- `FearGreedCollector` - Fear & Greed Index (CNN + custom calculation)
- `StockFundamentalsCollector` - PER, PBR, growth metrics, sector comparisons
- `NewsCollector` - Market news with sentiment analysis
- `EconomicCycleAnalyzer` - Determines current economic phase (회복기/확장기/과열기/수축기/침체기)

**Analyzers** (`analyzers/`)
- `AIAnalyzer` - Multi-provider AI analysis (supports 5 providers)
- `TechnicalAnalyzer` - RSI, MACD, Bollinger Bands, moving averages
- `PortfolioAnalyzer` - Compares user portfolio against famous portfolios (Warren Buffett, Ray Dalio, etc.)

**AI Providers** (`ai_providers/`)
- Supports: Grok (xAI), Gemini (Google), OpenAI GPT, Anthropic Claude, GitHub Models
- Provider selection via `AIAnalyzer(provider="grok")`
- GitHub Models supports 10+ models including GPT-4o, Llama, Phi, Mistral

**Configuration** (`config/`)
- `settings.py` - API keys, default tickers, valuation benchmarks
- `portfolio_data.py` - Famous portfolio allocations
- Economic cycle adjustments for PER/PBR thresholds

### Economic Cycle System
The system dynamically adjusts all metrics based on detected economic phase:
- **회복기 (Recovery)**: Lower PER threshold (×0.9), higher VIX tolerance
- **확장기 (Expansion)**: Normal thresholds (×1.0)
- **과열기 (Overheating)**: Higher PER threshold (×1.1), stricter VIX
- **수축기/침체기 (Contraction/Recession)**: Significantly lower thresholds

Access via `analyzer.get_economic_cycle()` - results are cached per session.

### Report System
All analysis results auto-save to `reports/` when `SAVE_REPORTS=True` in settings:
- `market/` - Market overview snapshots
- `stocks/` - Individual stock analyses  
- `portfolio/` - Portfolio comparisons
- `daily/` - Full daily reports (JSON + Markdown + Excel)
- `news/` - News summaries

## Conventions

### Data Flow Pattern
All collector methods return structured dicts with `current`, `previous`, `change`, `interpretation` fields. Analyzers consume these dicts and add AI insights. Avoid breaking this dict structure.

### Economic Context Injection
When analyzing stocks/portfolios, always pass `economic_cycle` parameter:
```python
economic_cycle = analyzer.get_economic_cycle()  # Get once, reuse
stock_data = analyzer.analyze_stock(ticker)  # Already includes economic_context
```

### Korean Language
- All user-facing strings, docstrings, and comments are in Korean
- Variable/function names remain in English
- AI prompts are in Korean to match the domain

### Error Handling
- Data collectors return fallback values (None/empty dict) on failure, never crash
- Print warning messages with ⚠️ emoji for skippable errors
- Only raise exceptions for configuration errors (missing API keys)

### Caching Strategy
- Economic cycle data is cached in `StockAnalyzer._economic_cycle_cache`
- Use `refresh=True` parameter to force refresh
- Market data is not cached (always fresh)

### AI Provider Selection
Provider priority: Grok > Gemini > OpenAI > Anthropic > GitHub Models
- Grok: Fast, cost-effective, good for Korean content
- Gemini: Free tier available, good context length
- OpenAI/Anthropic: Premium options for complex analysis
- GitHub Models: 10+ model choices via PAT

### Adding New Data Sources
1. Create collector in `data_collectors/` inheriting pattern from `MarketDataCollector`
2. Return dict with `current`, `previous`, `change` structure
3. Add to `StockAnalyzer.__init__()` and wire into relevant analysis methods
4. Add interpretation function to `utils/helpers.py`

## Testing

Run setup test to verify all data collectors and APIs:
```bash
python test_setup.py
```

Tests VIX, Treasury rates, S&P 500, Fear & Greed Index, and AAPL fundamentals. Does not require AI API keys.
