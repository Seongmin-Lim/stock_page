"""
분석 보고서 생성 및 저장 모듈
모든 분석 결과를 파일로 저장
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import pandas as pd


class ReportGenerator:
    """보고서 생성 및 저장 클래스"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        self._ensure_directory()
    
    def _ensure_directory(self):
        """출력 디렉토리 생성"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # 하위 디렉토리 생성
        subdirs = ["daily", "market", "stocks", "portfolio", "news"]
        for subdir in subdirs:
            path = os.path.join(self.output_dir, subdir)
            if not os.path.exists(path):
                os.makedirs(path)
    
    def _get_timestamp(self) -> str:
        """타임스탬프 생성"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _get_date(self) -> str:
        """날짜 문자열"""
        return datetime.now().strftime("%Y%m%d")
    
    def save_market_analysis(self, analysis: Dict) -> str:
        """시장 분석 저장"""
        filename = f"market_analysis_{self._get_timestamp()}.json"
        filepath = os.path.join(self.output_dir, "market", filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)
        
        return filepath
    
    def save_stock_analysis(self, ticker: str, analysis: Dict) -> str:
        """개별 주식 분석 저장"""
        filename = f"{ticker}_{self._get_timestamp()}.json"
        filepath = os.path.join(self.output_dir, "stocks", filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)
        
        return filepath
    
    def save_portfolio_analysis(self, analysis: Dict) -> str:
        """포트폴리오 분석 저장"""
        filename = f"portfolio_{self._get_timestamp()}.json"
        filepath = os.path.join(self.output_dir, "portfolio", filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)
        
        return filepath
    
    def save_news_analysis(self, analysis: Dict) -> str:
        """뉴스 분석 저장"""
        filename = f"news_{self._get_timestamp()}.json"
        filepath = os.path.join(self.output_dir, "news", filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)
        
        return filepath
    
    def save_daily_report(self, report: Dict) -> str:
        """일일 종합 보고서 저장"""
        filename = f"daily_report_{self._get_date()}.json"
        filepath = os.path.join(self.output_dir, "daily", filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        
        return filepath
    
    def save_ai_analysis(self, analysis_type: str, content: str, metadata: Dict = None) -> str:
        """AI 분석 결과 저장"""
        data = {
            "type": analysis_type,
            "timestamp": datetime.now().isoformat(),
            "content": content,
            "metadata": metadata or {}
        }
        
        filename = f"ai_{analysis_type}_{self._get_timestamp()}.json"
        filepath = os.path.join(self.output_dir, "daily", filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def generate_markdown_report(self, 
                                 market_data: Dict,
                                 economic_cycle: Dict,
                                 news_summary: Dict,
                                 portfolio_analysis: Dict = None,
                                 ai_analysis: str = None) -> str:
        """마크다운 형식 종합 보고서 생성"""
        report_date = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
        
        md_content = f"""# 📊 주식 시장 분석 보고서

**생성일시:** {report_date}

---

## 1. 경제 사이클 현황

**현재 단계:** {economic_cycle.get('current_phase', 'N/A')}
**신뢰도:** {economic_cycle.get('confidence', 'N/A')}%

{economic_cycle.get('description', '')}

### 시장 전망
"""
        
        outlook = economic_cycle.get('market_outlook', {})
        for key, value in outlook.items():
            md_content += f"- **{key}:** {value}\n"
        
        md_content += f"""
### 추천 자산 배분
"""
        allocation = economic_cycle.get('recommendations', {}).get('asset_allocation', {})
        for asset, weight in allocation.items():
            md_content += f"- {asset}: {weight}%\n"
        
        md_content += f"""
---

## 2. 시장 지표

| 지표 | 현재값 | 상태 |
|------|--------|------|
"""
        
        # VIX
        vix_data = market_data.get('market_data', {}).get('vix', {})
        vix_current = vix_data.get('current', 'N/A')
        vix_interp = vix_data.get('interpretation', {}).get('level', 'N/A')
        md_content += f"| VIX | {vix_current:.2f if isinstance(vix_current, (int, float)) else vix_current} | {vix_interp} |\n"
        
        # 10Y 금리
        tnx_data = market_data.get('market_data', {}).get('treasury_10y', {})
        tnx_current = tnx_data.get('current', 'N/A')
        md_content += f"| 10Y 국채금리 | {tnx_current:.2f if isinstance(tnx_current, (int, float)) else tnx_current}% | - |\n"
        
        # S&P 500
        sp_data = market_data.get('market_data', {}).get('sp500', {})
        sp_current = sp_data.get('current', 'N/A')
        md_content += f"| S&P 500 | {sp_current:,.2f if isinstance(sp_current, (int, float)) else sp_current} | - |\n"
        
        # Forward PE
        fpe = market_data.get('market_data', {}).get('sp500_forward_pe', 'N/A')
        md_content += f"| S&P 500 Forward P/E | {fpe:.1f if isinstance(fpe, (int, float)) else fpe} | - |\n"
        
        # 공포탐욕
        fg_data = market_data.get('fear_greed_index', {})
        fg_value = fg_data.get('value', 'N/A')
        fg_rating = fg_data.get('rating', 'N/A')
        md_content += f"| 공포탐욕 지수 | {fg_value:.0f if isinstance(fg_value, (int, float)) else fg_value} | {fg_rating} |\n"
        
        md_content += f"""
---

## 3. 뉴스 감성 분석

### 시장 뉴스
"""
        
        market_sentiment = news_summary.get('market_news', {}).get('sentiment', {})
        md_content += f"- **감성:** {market_sentiment.get('sentiment', 'N/A')}\n"
        md_content += f"- **점수:** {market_sentiment.get('score', 'N/A')}\n"
        md_content += f"- **긍정 신호:** {market_sentiment.get('positive_signals', 0)}개\n"
        md_content += f"- **부정 신호:** {market_sentiment.get('negative_signals', 0)}개\n"
        
        md_content += f"""
### 주요 헤드라인
"""
        
        articles = news_summary.get('market_news', {}).get('articles', [])[:5]
        for article in articles:
            md_content += f"- {article.get('title', 'N/A')}\n"
        
        if portfolio_analysis:
            md_content += f"""
---

## 4. 포트폴리오 분석

### 현재 포트폴리오 성과
"""
            metrics = portfolio_analysis.get('user_portfolio', {}).get('metrics', {})
            md_content += f"- **연간 수익률:** {metrics.get('annual_return', 'N/A')}%\n"
            md_content += f"- **변동성:** {metrics.get('volatility', 'N/A')}%\n"
            md_content += f"- **샤프비율:** {metrics.get('sharpe_ratio', 'N/A')}\n"
            md_content += f"- **최대 낙폭:** {metrics.get('max_drawdown', 'N/A')}%\n"
            
            md_content += f"""
### 유명 포트폴리오 대비 비교
"""
            summary = portfolio_analysis.get('comparison', {}).get('summary', {})
            for key, value in summary.items():
                md_content += f"- {value}\n"
        
        if ai_analysis:
            md_content += f"""
---

## 5. AI 종합 분석

{ai_analysis}
"""
        
        md_content += f"""
---

## 6. 조정된 기준값 (경제 단계 반영)

현재 **{economic_cycle.get('current_phase', 'N/A')}** 단계 기준:
"""
        
        adj = economic_cycle.get('dynamic_adjustments', {})
        md_content += f"- 적정 PER: {adj.get('adjusted_per_fair', 20)}\n"
        md_content += f"- VIX 경계선: {adj.get('adjusted_vix_threshold', 25)}\n"
        
        md_content += f"""
---

*이 보고서는 참고용이며, 투자 결정은 본인의 판단과 책임 하에 이루어져야 합니다.*
"""
        
        # 저장
        filename = f"report_{self._get_date()}.md"
        filepath = os.path.join(self.output_dir, "daily", filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        return filepath
    
    def generate_excel_report(self, 
                              market_data: Dict,
                              stocks_data: List[Dict],
                              portfolio_data: Dict = None) -> str:
        """엑셀 형식 보고서 생성"""
        filename = f"analysis_{self._get_date()}.xlsx"
        filepath = os.path.join(self.output_dir, "daily", filename)
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # 시장 지표 시트
            market_df = self._market_data_to_df(market_data)
            market_df.to_excel(writer, sheet_name='시장지표', index=False)
            
            # 개별 주식 시트
            if stocks_data:
                stocks_df = self._stocks_data_to_df(stocks_data)
                stocks_df.to_excel(writer, sheet_name='주식분석', index=False)
            
            # 포트폴리오 시트
            if portfolio_data:
                portfolio_df = self._portfolio_data_to_df(portfolio_data)
                portfolio_df.to_excel(writer, sheet_name='포트폴리오', index=False)
        
        return filepath
    
    def _market_data_to_df(self, market_data: Dict) -> pd.DataFrame:
        """시장 데이터를 DataFrame으로 변환"""
        rows = []
        
        md = market_data.get('market_data', {})
        
        if 'vix' in md:
            rows.append({'지표': 'VIX', '현재값': md['vix'].get('current'), '변화': md['vix'].get('change_1d')})
        if 'treasury_10y' in md:
            rows.append({'지표': '10Y 금리', '현재값': md['treasury_10y'].get('current'), '변화': md['treasury_10y'].get('change_1d')})
        if 'sp500' in md:
            rows.append({'지표': 'S&P 500', '현재값': md['sp500'].get('current'), '변화': md['sp500'].get('change_1d')})
        if 'sp500_forward_pe' in md:
            rows.append({'지표': 'Forward P/E', '현재값': md['sp500_forward_pe'], '변화': None})
        
        fg = market_data.get('fear_greed_index', {})
        if fg:
            rows.append({'지표': '공포탐욕지수', '현재값': fg.get('value'), '변화': fg.get('rating')})
        
        return pd.DataFrame(rows)
    
    def _stocks_data_to_df(self, stocks_data: List[Dict]) -> pd.DataFrame:
        """주식 데이터를 DataFrame으로 변환"""
        rows = []
        
        for stock in stocks_data:
            if 'error' in stock:
                continue
            
            val = stock.get('valuation', {})
            rows.append({
                '티커': stock.get('ticker'),
                '종목명': val.get('name'),
                '현재가': val.get('current_price'),
                'PER': val.get('trailing_pe'),
                'Forward PER': val.get('forward_pe'),
                'PBR': val.get('price_to_book'),
                'PEG': val.get('peg_ratio'),
                '이익률': val.get('profit_margin'),
                '배당률': val.get('dividend_yield'),
            })
        
        return pd.DataFrame(rows)
    
    def _portfolio_data_to_df(self, portfolio_data: Dict) -> pd.DataFrame:
        """포트폴리오 데이터를 DataFrame으로 변환"""
        rows = []
        
        # 보유 종목
        holdings = portfolio_data.get('user_portfolio', {}).get('holdings', {})
        contributions = portfolio_data.get('user_portfolio', {}).get('contributions', {})
        
        for ticker, weight in holdings.items():
            contrib = contributions.get(ticker, {})
            rows.append({
                '티커': ticker,
                '비중(%)': weight,
                '수익률(%)': contrib.get('return'),
                '기여도': contrib.get('contribution'),
            })
        
        return pd.DataFrame(rows)
    
    def list_reports(self, category: str = None, days: int = 7) -> List[Dict]:
        """저장된 보고서 목록 조회"""
        reports = []
        
        if category:
            search_dirs = [os.path.join(self.output_dir, category)]
        else:
            search_dirs = [
                os.path.join(self.output_dir, d) 
                for d in ["daily", "market", "stocks", "portfolio", "news"]
            ]
        
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        for dir_path in search_dirs:
            if os.path.exists(dir_path):
                for filename in os.listdir(dir_path):
                    filepath = os.path.join(dir_path, filename)
                    if os.path.isfile(filepath):
                        stat = os.stat(filepath)
                        if stat.st_mtime >= cutoff:
                            reports.append({
                                "filename": filename,
                                "path": filepath,
                                "category": os.path.basename(dir_path),
                                "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                "size": stat.st_size,
                            })
        
        reports.sort(key=lambda x: x['created'], reverse=True)
        return reports
    
    def load_report(self, filepath: str) -> Optional[Dict]:
        """저장된 보고서 로드"""
        if not os.path.exists(filepath):
            return None
        
        if filepath.endswith('.json'):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        elif filepath.endswith('.md'):
            with open(filepath, 'r', encoding='utf-8') as f:
                return {"content": f.read(), "format": "markdown"}
        
        return None


if __name__ == "__main__":
    generator = ReportGenerator()
    
    # 테스트 데이터
    test_market = {
        "market_data": {
            "vix": {"current": 18.5, "change_1d": -0.5},
            "treasury_10y": {"current": 4.25},
            "sp500": {"current": 5200},
            "sp500_forward_pe": 21.5,
        },
        "fear_greed_index": {"value": 62, "rating": "Greed"}
    }
    
    # 시장 분석 저장
    path = generator.save_market_analysis(test_market)
    print(f"시장 분석 저장: {path}")
    
    # 보고서 목록
    reports = generator.list_reports()
    print(f"\n저장된 보고서: {len(reports)}개")
