"""
뉴스 데이터 수집 모듈
시장 및 개별 종목 관련 뉴스 수집

지원 소스:
- NewsAPI (API 키 필요)
- Alpha Vantage News Sentiment (API 키 필요, 금융 특화)
- Finnhub (API 키 필요, 금융 특화)
- Yahoo Finance (무료)
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
from bs4 import BeautifulSoup
import yfinance as yf


class NewsCollector:
    """뉴스 수집 클래스 (다중 소스 지원)"""
    
    def __init__(self):
        self.news_api_key = os.getenv("NEWS_API_KEY")
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.finnhub_key = os.getenv("FINNHUB_API_KEY")  # 선택적
        self.marketaux_key = os.getenv("MARKETAUX_API_KEY")  # 선택적 (100/day 무료)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def get_market_news(self, days: int = 7, max_articles: int = 20) -> List[Dict]:
        """시장 관련 뉴스 수집 (다중 소스)"""
        news = []
        
        # 1. NewsAPI 사용 (API 키가 있는 경우)
        if self.news_api_key:
            news.extend(self._get_newsapi_news(
                query="stock market OR S&P 500 OR Federal Reserve OR economy",
                days=days,
                max_articles=max_articles // 3
            ))
        
        # 2. Alpha Vantage News (금융 특화, 감성 분석 포함)
        if self.alpha_vantage_key:
            av_news = self._get_alphavantage_news(
                topics="economy,finance,financial_markets",
                max_articles=max_articles // 3
            )
            news.extend(av_news)
        
        # 3. Finnhub (금융 특화)
        if self.finnhub_key:
            fh_news = self._get_finnhub_news(
                category="general",
                max_articles=max_articles // 4
            )
            news.extend(fh_news)
        
        # 4. Marketaux (금융 특화, 감성 분석 포함)
        if self.marketaux_key:
            mx_news = self._get_marketaux_news(
                topics="market,stock",
                max_articles=max_articles // 4
            )
            news.extend(mx_news)
        
        # 5. Yahoo Finance 뉴스 (무료)
        news.extend(self._get_yahoo_market_news(max_articles=max_articles // 4))
        
        # 중복 제거 및 정렬
        seen_titles = set()
        unique_news = []
        for article in news:
            title_key = article.get('title', '')[:50].lower()
            if title_key not in seen_titles and article.get('title'):
                seen_titles.add(title_key)
                unique_news.append(article)
        
        # 날짜순 정렬
        unique_news.sort(key=lambda x: x.get('published', ''), reverse=True)
        
        return unique_news[:max_articles]
    
    def get_stock_news(self, ticker: str, max_articles: int = 10) -> List[Dict]:
        """개별 종목 뉴스 수집 (다중 소스)"""
        news = []
        
        # Yahoo Finance에서 종목 뉴스
        try:
            stock = yf.Ticker(ticker)
            yf_news = stock.news
            
            for article in yf_news[:max_articles // 2]:
                news.append({
                    'title': article.get('title', ''),
                    'summary': article.get('summary', ''),
                    'source': article.get('publisher', 'Yahoo Finance'),
                    'url': article.get('link', ''),
                    'published': datetime.fromtimestamp(
                        article.get('providerPublishTime', 0)
                    ).isoformat() if article.get('providerPublishTime') else '',
                    'ticker': ticker,
                    'type': 'stock_news'
                })
        except Exception as e:
            print(f"Yahoo Finance 뉴스 수집 실패 ({ticker}): {e}")
        
        # Alpha Vantage (감성 분석 포함)
        if self.alpha_vantage_key:
            av_news = self._get_alphavantage_news(
                tickers=ticker,
                max_articles=max_articles // 3
            )
            for article in av_news:
                article['ticker'] = ticker
            news.extend(av_news)
        
        # Finnhub 
        if self.finnhub_key:
            fh_news = self._get_finnhub_news(
                ticker=ticker,
                max_articles=max_articles // 3
            )
            news.extend(fh_news)
        
        # NewsAPI 추가 (API 키가 있는 경우)
        if self.news_api_key:
            try:
                stock = yf.Ticker(ticker)
                company_name = stock.info.get('shortName', ticker)
                
                api_news = self._get_newsapi_news(
                    query=f"{company_name} OR {ticker}",
                    days=7,
                    max_articles=max_articles // 3
                )
                for article in api_news:
                    article['ticker'] = ticker
                    article['type'] = 'stock_news'
                news.extend(api_news)
            except:
                pass
        
        # 중복 제거
        seen_titles = set()
        unique_news = []
        for article in news:
            title_key = article.get('title', '')[:50].lower()
            if title_key not in seen_titles and article.get('title'):
                seen_titles.add(title_key)
                unique_news.append(article)
        
        return unique_news[:max_articles]
    
    def get_economic_news(self, days: int = 7, max_articles: int = 15) -> List[Dict]:
        """경제 지표 관련 뉴스 수집"""
        keywords = [
            "GDP growth", "inflation rate", "unemployment", 
            "Federal Reserve", "interest rate", "CPI",
            "economic outlook", "recession", "recovery"
        ]
        
        news = []
        
        if self.news_api_key:
            query = " OR ".join(keywords[:5])  # API 쿼리 길이 제한
            news.extend(self._get_newsapi_news(
                query=query,
                days=days,
                max_articles=max_articles
            ))
        
        # Yahoo Finance 경제 뉴스
        news.extend(self._get_yahoo_economic_news(max_articles=max_articles // 2))
        
        for article in news:
            article['type'] = 'economic_news'
        
        return news[:max_articles]
    
    def _get_newsapi_news(self, query: str, days: int = 7, max_articles: int = 20) -> List[Dict]:
        """NewsAPI에서 뉴스 가져오기"""
        if not self.news_api_key:
            return []
        
        news = []
        from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': query,
                'from': from_date,
                'sortBy': 'relevancy',
                'language': 'en',
                'pageSize': max_articles,
                'apiKey': self.news_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                for article in data.get('articles', []):
                    news.append({
                        'title': article.get('title', ''),
                        'summary': article.get('description', ''),
                        'source': article.get('source', {}).get('name', 'Unknown'),
                        'url': article.get('url', ''),
                        'published': article.get('publishedAt', ''),
                        'type': 'market_news'
                    })
        except Exception as e:
            print(f"NewsAPI 수집 실패: {e}")
        
        return news
    
    def _get_alphavantage_news(self, tickers: str = None, topics: str = None, 
                                max_articles: int = 20) -> List[Dict]:
        """
        Alpha Vantage News Sentiment API에서 뉴스 가져오기
        - 금융 뉴스 특화
        - 감성 점수 포함
        
        Args:
            tickers: 티커 (예: "AAPL" 또는 "AAPL,MSFT")
            topics: 토픽 (예: "technology", "finance", "economy")
        """
        if not self.alpha_vantage_key:
            return []
        
        news = []
        
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'apikey': self.alpha_vantage_key,
                'limit': max_articles,
                'sort': 'LATEST'
            }
            
            if tickers:
                params['tickers'] = tickers
            if topics:
                params['topics'] = topics
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # API 한도 초과 체크
                if 'Note' in data or 'Information' in data:
                    print(f"⚠️ Alpha Vantage API 한도: {data.get('Note', data.get('Information', ''))[:100]}")
                    return []
                
                for article in data.get('feed', []):
                    # 감성 점수 계산 (Alpha Vantage는 -1 ~ 1 스케일)
                    sentiment_score = article.get('overall_sentiment_score', 0)
                    sentiment_label = article.get('overall_sentiment_label', 'Neutral')
                    
                    # 티커별 감성 추출
                    ticker_sentiments = {}
                    for ts in article.get('ticker_sentiment', []):
                        ticker_sentiments[ts.get('ticker', '')] = {
                            'score': float(ts.get('ticker_sentiment_score', 0)),
                            'label': ts.get('ticker_sentiment_label', 'Neutral'),
                            'relevance': float(ts.get('relevance_score', 0))
                        }
                    
                    news.append({
                        'title': article.get('title', ''),
                        'summary': article.get('summary', ''),
                        'source': article.get('source', 'Unknown'),
                        'url': article.get('url', ''),
                        'published': article.get('time_published', ''),
                        'type': 'alphavantage_news',
                        'sentiment': {
                            'score': sentiment_score,
                            'label': sentiment_label
                        },
                        'ticker_sentiments': ticker_sentiments,
                        'topics': [t.get('topic', '') for t in article.get('topics', [])],
                        'banner_image': article.get('banner_image', '')
                    })
                    
        except Exception as e:
            print(f"Alpha Vantage News 수집 실패: {e}")
        
        return news
    
    def _get_finnhub_news(self, category: str = "general", 
                          ticker: str = None, max_articles: int = 20) -> List[Dict]:
        """
        Finnhub에서 뉴스 가져오기
        - 무료: 60 요청/분
        - 금융 뉴스 특화
        
        Args:
            category: "general", "forex", "crypto", "merger"
            ticker: 개별 종목 티커 (종목 뉴스용)
        """
        if not self.finnhub_key:
            return []
        
        news = []
        
        try:
            if ticker:
                # 종목별 뉴스
                url = "https://finnhub.io/api/v1/company-news"
                from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                to_date = datetime.now().strftime('%Y-%m-%d')
                params = {
                    'symbol': ticker,
                    'from': from_date,
                    'to': to_date,
                    'token': self.finnhub_key
                }
            else:
                # 일반 시장 뉴스
                url = "https://finnhub.io/api/v1/news"
                params = {
                    'category': category,
                    'token': self.finnhub_key
                }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                for article in data[:max_articles]:
                    news.append({
                        'title': article.get('headline', ''),
                        'summary': article.get('summary', ''),
                        'source': article.get('source', 'Unknown'),
                        'url': article.get('url', ''),
                        'published': datetime.fromtimestamp(
                            article.get('datetime', 0)
                        ).isoformat() if article.get('datetime') else '',
                        'type': 'finnhub_news',
                        'ticker': ticker or article.get('related', ''),
                        'category': article.get('category', category),
                        'image': article.get('image', '')
                    })
                    
        except Exception as e:
            print(f"Finnhub News 수집 실패: {e}")
        
        return news
    
    def _get_marketaux_news(self, symbols: str = None, topics: str = None,
                            max_articles: int = 20) -> List[Dict]:
        """
        Marketaux에서 뉴스 가져오기
        - 무료: 100 요청/일
        - 금융 뉴스 특화, 감성 분석 포함
        
        Args:
            symbols: 티커 (예: "AAPL" 또는 "AAPL,MSFT")
            topics: 토픽 필터 (예: "earnings", "ipo", "merger")
        """
        if not self.marketaux_key:
            return []
        
        news = []
        
        try:
            url = "https://api.marketaux.com/v1/news/all"
            params = {
                'api_token': self.marketaux_key,
                'language': 'en',
                'limit': max_articles,
                'sort': 'published_desc'
            }
            
            if symbols:
                params['symbols'] = symbols
            if topics:
                params['filter_entities'] = 'true'
                params['topics'] = topics
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                for article in data.get('data', []):
                    # Marketaux 감성 정보 추출
                    entities = article.get('entities', [])
                    ticker_sentiments = {}
                    for entity in entities:
                        if entity.get('type') == 'equity':
                            ticker_sentiments[entity.get('symbol', '')] = {
                                'score': entity.get('sentiment_score', 0),
                                'highlights': entity.get('highlights', [])
                            }
                    
                    news.append({
                        'title': article.get('title', ''),
                        'summary': article.get('description', ''),
                        'source': article.get('source', 'Unknown'),
                        'url': article.get('url', ''),
                        'published': article.get('published_at', ''),
                        'type': 'marketaux_news',
                        'ticker_sentiments': ticker_sentiments,
                        'image': article.get('image_url', ''),
                        'relevance_score': article.get('relevance_score', 0)
                    })
            elif response.status_code == 429:
                print("⚠️ Marketaux API 일일 한도 초과")
            else:
                print(f"⚠️ Marketaux API 오류: {response.status_code}")
                    
        except Exception as e:
            print(f"Marketaux News 수집 실패: {e}")
        
        return news
    
    def get_comprehensive_stock_news(self, ticker: str, max_articles: int = 15) -> Dict:
        """
        개별 종목에 대한 종합 뉴스 (모든 소스 통합)
        감성 분석 포함
        """
        all_news = []
        source_stats = {}
        
        # 1. Yahoo Finance (무료, 항상 사용)
        yf_news = []
        try:
            stock = yf.Ticker(ticker)
            for article in stock.news[:5]:
                yf_news.append({
                    'title': article.get('title', ''),
                    'summary': article.get('summary', ''),
                    'source': article.get('publisher', 'Yahoo Finance'),
                    'url': article.get('link', ''),
                    'published': datetime.fromtimestamp(
                        article.get('providerPublishTime', 0)
                    ).isoformat() if article.get('providerPublishTime') else '',
                    'type': 'yahoo_finance',
                    'ticker': ticker
                })
            all_news.extend(yf_news)
            source_stats['Yahoo Finance'] = len(yf_news)
        except Exception as e:
            source_stats['Yahoo Finance'] = f"실패: {e}"
        
        # 2. Alpha Vantage (감성 점수 포함)
        if self.alpha_vantage_key:
            av_news = self._get_alphavantage_news(tickers=ticker, max_articles=5)
            all_news.extend(av_news)
            source_stats['Alpha Vantage'] = len(av_news)
        
        # 3. Finnhub
        if self.finnhub_key:
            fh_news = self._get_finnhub_news(ticker=ticker, max_articles=4)
            all_news.extend(fh_news)
            source_stats['Finnhub'] = len(fh_news)
        
        # 4. Marketaux (감성 분석 포함)
        if self.marketaux_key:
            mx_news = self._get_marketaux_news(symbols=ticker, max_articles=4)
            all_news.extend(mx_news)
            source_stats['Marketaux'] = len(mx_news)
        
        # 5. NewsAPI
        if self.news_api_key:
            try:
                stock = yf.Ticker(ticker)
                company_name = stock.info.get('shortName', ticker)
                na_news = self._get_newsapi_news(
                    query=f'"{company_name}" OR {ticker}',
                    days=7,
                    max_articles=5
                )
                for article in na_news:
                    article['ticker'] = ticker
                all_news.extend(na_news)
                source_stats['NewsAPI'] = len(na_news)
            except:
                source_stats['NewsAPI'] = 0
        
        # 중복 제거
        seen_titles = set()
        unique_news = []
        for article in all_news:
            title_key = article['title'][:50].lower()
            if title_key not in seen_titles and article['title']:
                seen_titles.add(title_key)
                unique_news.append(article)
        
        # 날짜순 정렬
        unique_news.sort(key=lambda x: x.get('published', ''), reverse=True)
        
        # Alpha Vantage 뉴스에서 감성 점수 추출
        av_sentiments = [n.get('sentiment', {}).get('score', 0) 
                        for n in unique_news if n.get('type') == 'alphavantage_news']
        avg_av_sentiment = sum(av_sentiments) / len(av_sentiments) if av_sentiments else None
        
        # 키워드 기반 감성 분석
        keyword_sentiment = self.summarize_news_sentiment(unique_news)
        
        return {
            'ticker': ticker,
            'timestamp': datetime.now().isoformat(),
            'total_articles': len(unique_news),
            'articles': unique_news[:max_articles],
            'source_stats': source_stats,
            'sentiment_analysis': {
                'keyword_based': keyword_sentiment,
                'alphavantage_avg': avg_av_sentiment,
                'combined_score': (
                    (keyword_sentiment['score'] + avg_av_sentiment) / 2 
                    if avg_av_sentiment is not None 
                    else keyword_sentiment['score']
                )
            }
        }
    
    def _get_yahoo_market_news(self, max_articles: int = 10) -> List[Dict]:
        """Yahoo Finance 시장 뉴스 수집"""
        news = []
        
        try:
            # SPY ETF 뉴스를 시장 뉴스로 사용
            spy = yf.Ticker("SPY")
            yf_news = spy.news
            
            for article in yf_news[:max_articles]:
                news.append({
                    'title': article.get('title', ''),
                    'summary': article.get('summary', ''),
                    'source': article.get('publisher', 'Yahoo Finance'),
                    'url': article.get('link', ''),
                    'published': datetime.fromtimestamp(
                        article.get('providerPublishTime', 0)
                    ).isoformat() if article.get('providerPublishTime') else '',
                    'type': 'market_news'
                })
        except Exception as e:
            print(f"Yahoo Finance 시장 뉴스 수집 실패: {e}")
        
        return news
    
    def _get_yahoo_economic_news(self, max_articles: int = 10) -> List[Dict]:
        """Yahoo Finance 경제 뉴스 (국채 ETF 뉴스 활용)"""
        news = []
        
        try:
            # TLT (20년 국채 ETF) 뉴스를 경제 뉴스로 활용
            tlt = yf.Ticker("TLT")
            yf_news = tlt.news
            
            for article in yf_news[:max_articles]:
                news.append({
                    'title': article.get('title', ''),
                    'summary': article.get('summary', ''),
                    'source': article.get('publisher', 'Yahoo Finance'),
                    'url': article.get('link', ''),
                    'published': datetime.fromtimestamp(
                        article.get('providerPublishTime', 0)
                    ).isoformat() if article.get('providerPublishTime') else '',
                    'type': 'economic_news'
                })
        except Exception as e:
            print(f"Yahoo Finance 경제 뉴스 수집 실패: {e}")
        
        return news
    
    def summarize_news_sentiment(self, news_list: List[Dict]) -> Dict:
        """뉴스 감성 요약 (간단한 키워드 기반)"""
        if not news_list:
            return {"sentiment": "neutral", "score": 0, "article_count": 0}
        
        positive_keywords = [
            'surge', 'jump', 'rally', 'gain', 'rise', 'growth', 'bullish',
            'record high', 'beat', 'exceed', 'optimism', 'recovery', 'boom'
        ]
        negative_keywords = [
            'fall', 'drop', 'plunge', 'crash', 'decline', 'bearish', 'fear',
            'recession', 'crisis', 'miss', 'disappoint', 'concern', 'risk',
            'selloff', 'tumble', 'slump'
        ]
        
        positive_count = 0
        negative_count = 0
        
        for article in news_list:
            title = article.get('title', '') or ''
            summary = article.get('summary', '') or ''
            text = (title + ' ' + summary).lower()
            
            for keyword in positive_keywords:
                if keyword in text:
                    positive_count += 1
            
            for keyword in negative_keywords:
                if keyword in text:
                    negative_count += 1
        
        total = positive_count + negative_count
        if total == 0:
            score = 0
            sentiment = "neutral"
        else:
            score = (positive_count - negative_count) / total
            if score > 0.2:
                sentiment = "positive"
            elif score < -0.2:
                sentiment = "negative"
            else:
                sentiment = "neutral"
        
        return {
            "sentiment": sentiment,
            "score": round(score, 2),
            "positive_signals": positive_count,
            "negative_signals": negative_count,
            "article_count": len(news_list)
        }
    
    def get_news_summary(self) -> Dict:
        """전체 뉴스 요약"""
        market_news = self.get_market_news(days=3, max_articles=15)
        economic_news = self.get_economic_news(days=3, max_articles=10)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "market_news": {
                "articles": market_news,
                "sentiment": self.summarize_news_sentiment(market_news)
            },
            "economic_news": {
                "articles": economic_news,
                "sentiment": self.summarize_news_sentiment(economic_news)
            }
        }


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    collector = NewsCollector()
    
    # API 키 상태 확인
    print("=" * 50)
    print("📰 뉴스 API 상태 확인")
    print("=" * 50)
    print(f"✅ NewsAPI: {'설정됨' if collector.news_api_key else '❌ 미설정'}")
    print(f"✅ Alpha Vantage: {'설정됨' if collector.alpha_vantage_key else '❌ 미설정'}")
    print(f"✅ Finnhub: {'설정됨' if collector.finnhub_key else '❌ 미설정 (선택적)'}")
    print(f"✅ Marketaux: {'설정됨' if collector.marketaux_key else '❌ 미설정 (선택적)'}")
    print()
    
    print("=== 시장 뉴스 (다중 소스) ===")
    market_news = collector.get_market_news(max_articles=12)
    print(f"총 {len(market_news)}개 기사 수집")
    
    # 소스별 통계
    source_counts = {}
    for news in market_news:
        src = news.get('type', 'unknown')
        source_counts[src] = source_counts.get(src, 0) + 1
    print(f"소스별 수집: {source_counts}")
    
    for news in market_news[:5]:
        source_type = news.get('type', 'unknown')
        sentiment = news.get('sentiment', {}).get('label', '')
        sentiment_str = f" [{sentiment}]" if sentiment else ""
        print(f"  [{source_type}]{sentiment_str} {news['title'][:50]}...")
    
    print("\n=== AAPL 종합 뉴스 ===")
    aapl_comprehensive = collector.get_comprehensive_stock_news("AAPL", max_articles=12)
    print(f"총 {aapl_comprehensive['total_articles']}개 기사")
    print(f"소스별 수집: {aapl_comprehensive['source_stats']}")
    print(f"감성 분석: {aapl_comprehensive['sentiment_analysis']}")
    print("\n주요 기사:")
    for news in aapl_comprehensive['articles'][:3]:
        print(f"  - {news['title'][:60]}...")
    
    print("\n=== 뉴스 감성 요약 ===")
    sentiment = collector.summarize_news_sentiment(market_news)
    print(f"키워드 기반 감성: {sentiment['sentiment']}")
    print(f"점수: {sentiment['score']}")
    print(f"긍정 신호: {sentiment['positive_signals']}, 부정 신호: {sentiment['negative_signals']}")
