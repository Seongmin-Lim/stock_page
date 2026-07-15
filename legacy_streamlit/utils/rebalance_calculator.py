"""
💰 리밸런싱 계산기
목표 배분과 현재 보유 종목을 비교하여 리밸런싱 권고 생성
"""
import yfinance as yf
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import pandas as pd


@dataclass
class RebalanceAction:
    """리밸런싱 액션"""
    ticker: str
    action: str  # "buy", "sell", "hold"
    current_value: float
    current_percent: float
    target_percent: float
    diff_percent: float
    diff_value: float
    shares_to_trade: int
    current_price: float
    priority: int  # 1=높음, 3=낮음


class RebalanceCalculator:
    """리밸런싱 계산기"""
    
    def __init__(self):
        self.price_cache = {}
        self.cache_time = None
        self.cache_duration = 300  # 5분 캐시
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """현재 가격 조회 (캐시 적용)"""
        now = datetime.now()
        
        # 캐시 만료 확인
        if self.cache_time and (now - self.cache_time).seconds < self.cache_duration:
            if ticker in self.price_cache:
                return self.price_cache[ticker]
        else:
            self.price_cache = {}
            self.cache_time = now
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                self.price_cache[ticker] = price
                return price
        except Exception as e:
            print(f"⚠️ {ticker} 가격 조회 실패: {e}")
        
        return None
    
    def get_multiple_prices(self, tickers: List[str]) -> Dict[str, float]:
        """여러 종목 가격 한번에 조회"""
        prices = {}
        
        # 캐시된 가격 먼저 사용
        uncached = []
        for ticker in tickers:
            if ticker in self.price_cache:
                prices[ticker] = self.price_cache[ticker]
            else:
                uncached.append(ticker)
        
        # 캐시되지 않은 종목 조회
        if uncached:
            try:
                tickers_str = " ".join(uncached)
                data = yf.download(tickers_str, period="1d", progress=False)
                
                if not data.empty:
                    if len(uncached) == 1:
                        # 단일 종목
                        if 'Close' in data.columns:
                            prices[uncached[0]] = data['Close'].iloc[-1]
                            self.price_cache[uncached[0]] = prices[uncached[0]]
                    else:
                        # 다중 종목
                        for ticker in uncached:
                            if ('Close', ticker) in data.columns:
                                price = data[('Close', ticker)].iloc[-1]
                                if pd.notna(price):
                                    prices[ticker] = price
                                    self.price_cache[ticker] = price
            except Exception as e:
                print(f"⚠️ 다중 종목 가격 조회 실패: {e}")
                # 개별 조회 fallback
                for ticker in uncached:
                    price = self.get_current_price(ticker)
                    if price:
                        prices[ticker] = price
        
        self.cache_time = datetime.now()
        return prices
    
    def calculate_portfolio_value(self, holdings: List[Dict], 
                                   prices: Dict[str, float] = None) -> Tuple[float, Dict]:
        """
        포트폴리오 총 가치 및 종목별 현황 계산
        
        Args:
            holdings: [{"ticker": "AAPL", "quantity": 10, "avg_price": 150.0}, ...]
            prices: 현재 가격 딕셔너리 (없으면 자동 조회)
        
        Returns:
            (총 가치, {ticker: {value, percent, quantity, avg_price, current_price, profit_loss}})
        """
        if not holdings:
            return 0.0, {}
        
        # 가격 조회
        tickers = [h['ticker'] for h in holdings]
        if prices is None:
            prices = self.get_multiple_prices(tickers)
        
        # 종목별 현황 계산
        portfolio_details = {}
        total_value = 0.0
        
        for holding in holdings:
            ticker = holding['ticker']
            quantity = holding['quantity']
            avg_price = holding.get('avg_price', 0)
            current_price = prices.get(ticker, avg_price)  # 가격 없으면 평균가 사용
            
            value = quantity * current_price
            cost = quantity * avg_price
            profit_loss = value - cost
            profit_loss_pct = (profit_loss / cost * 100) if cost > 0 else 0
            
            portfolio_details[ticker] = {
                'quantity': quantity,
                'avg_price': avg_price,
                'current_price': current_price,
                'value': value,
                'cost': cost,
                'profit_loss': profit_loss,
                'profit_loss_percent': profit_loss_pct
            }
            
            total_value += value
        
        # 비중 계산
        for ticker in portfolio_details:
            portfolio_details[ticker]['percent'] = (
                portfolio_details[ticker]['value'] / total_value * 100 
                if total_value > 0 else 0
            )
        
        return total_value, portfolio_details
    
    def calculate_rebalance(self, 
                           holdings: List[Dict],
                           target_allocations: List[Dict],
                           additional_cash: float = 0,
                           threshold_percent: float = 2.0,
                           prices: Dict[str, float] = None) -> Dict:
        """
        리밸런싱 계산
        
        Args:
            holdings: 현재 보유 종목 [{"ticker": "AAPL", "quantity": 10, "avg_price": 150}, ...]
            target_allocations: 목표 배분 [{"ticker": "AAPL", "target_percent": 30}, ...]
            additional_cash: 추가 투자금 (선택)
            threshold_percent: 리밸런싱 임계값 (이 비율 이상 차이나면 조정 권고)
            prices: 현재 가격 딕셔너리
        
        Returns:
            {
                "total_value": 현재 포트폴리오 가치,
                "target_value": 목표 포트폴리오 가치 (추가 투자금 포함),
                "current_allocations": 현재 배분 현황,
                "actions": [RebalanceAction, ...],
                "summary": 요약 정보
            }
        """
        # 현재 포트폴리오 가치 계산
        total_value, current_details = self.calculate_portfolio_value(holdings, prices)
        
        # 목표 포트폴리오 가치 (추가 투자금 포함)
        target_total = total_value + additional_cash
        
        # 모든 관련 종목 수집
        all_tickers = set()
        for h in holdings:
            all_tickers.add(h['ticker'])
        for t in target_allocations:
            all_tickers.add(t['ticker'])
        
        # 가격 조회
        if prices is None:
            prices = self.get_multiple_prices(list(all_tickers))
        
        # 목표 배분 딕셔너리 변환
        target_dict = {t['ticker']: t['target_percent'] for t in target_allocations}
        
        # 리밸런싱 액션 계산
        actions = []
        
        for ticker in all_tickers:
            current_value = current_details.get(ticker, {}).get('value', 0)
            current_percent = current_details.get(ticker, {}).get('percent', 0)
            target_percent = target_dict.get(ticker, 0)
            current_price = prices.get(ticker, 0)
            
            # 목표 가치
            target_value = target_total * (target_percent / 100)
            
            # 차이 계산
            diff_percent = target_percent - current_percent
            diff_value = target_value - current_value
            
            # 거래할 주식 수 (정수)
            if current_price > 0:
                shares_to_trade = int(diff_value / current_price)
            else:
                shares_to_trade = 0
            
            # 액션 결정
            if abs(diff_percent) < threshold_percent:
                action = "hold"
                priority = 3
            elif diff_percent > 0:
                action = "buy"
                priority = 1 if diff_percent > threshold_percent * 2 else 2
            else:
                action = "sell"
                priority = 1 if abs(diff_percent) > threshold_percent * 2 else 2
            
            actions.append(RebalanceAction(
                ticker=ticker,
                action=action,
                current_value=current_value,
                current_percent=current_percent,
                target_percent=target_percent,
                diff_percent=diff_percent,
                diff_value=diff_value,
                shares_to_trade=abs(shares_to_trade),
                current_price=current_price,
                priority=priority
            ))
        
        # 우선순위로 정렬
        actions.sort(key=lambda x: (x.priority, -abs(x.diff_percent)))
        
        # 요약 생성
        buy_actions = [a for a in actions if a.action == "buy"]
        sell_actions = [a for a in actions if a.action == "sell"]
        hold_actions = [a for a in actions if a.action == "hold"]
        
        total_buy = sum(a.diff_value for a in buy_actions)
        total_sell = sum(abs(a.diff_value) for a in sell_actions)
        
        summary = {
            "buy_count": len(buy_actions),
            "sell_count": len(sell_actions),
            "hold_count": len(hold_actions),
            "total_buy_amount": total_buy,
            "total_sell_amount": total_sell,
            "net_cash_needed": total_buy - total_sell,
            "is_balanced": len(buy_actions) == 0 and len(sell_actions) == 0,
            "additional_cash_used": min(additional_cash, max(0, total_buy - total_sell))
        }
        
        return {
            "total_value": total_value,
            "target_value": target_total,
            "additional_cash": additional_cash,
            "threshold_percent": threshold_percent,
            "current_allocations": current_details,
            "actions": actions,
            "summary": summary,
            "calculated_at": datetime.now().isoformat()
        }
    
    def suggest_allocation_adjustments(self, 
                                       current_allocations: Dict,
                                       market_conditions: Dict = None) -> List[Dict]:
        """
        시장 상황에 따른 배분 조정 제안
        
        Args:
            current_allocations: 현재 목표 배분
            market_conditions: 시장 상황 데이터 (VIX, Fear & Greed 등)
        
        Returns:
            조정 제안 리스트
        """
        suggestions = []
        
        if not market_conditions:
            return suggestions
        
        vix = market_conditions.get('vix', 20)
        fear_greed = market_conditions.get('fear_greed', 50)
        economic_cycle = market_conditions.get('economic_cycle', '확장기')
        
        # VIX 기반 제안
        if vix > 30:
            suggestions.append({
                "type": "defensive",
                "reason": f"VIX가 {vix:.1f}로 높음 - 변동성 확대",
                "suggestion": "방어적 자산(채권, 금) 비중 확대 고려",
                "priority": "high"
            })
        elif vix < 15:
            suggestions.append({
                "type": "aggressive",
                "reason": f"VIX가 {vix:.1f}로 낮음 - 시장 안정",
                "suggestion": "성장주/리스크 자산 비중 유지 가능",
                "priority": "low"
            })
        
        # Fear & Greed 기반 제안
        if fear_greed < 25:
            suggestions.append({
                "type": "contrarian_buy",
                "reason": f"Fear & Greed {fear_greed}점 - 극도의 공포",
                "suggestion": "역발상 매수 기회, 주식 비중 확대 고려",
                "priority": "high"
            })
        elif fear_greed > 75:
            suggestions.append({
                "type": "contrarian_sell",
                "reason": f"Fear & Greed {fear_greed}점 - 극도의 탐욕",
                "suggestion": "차익 실현 고려, 현금 비중 확대",
                "priority": "high"
            })
        
        # 경제 사이클 기반 제안
        cycle_suggestions = {
            "회복기": "경기 민감주, 소형주 비중 확대 고려",
            "확장기": "성장주 유지, 점진적 방어주 확대",
            "과열기": "가치주, 배당주로 이동 고려",
            "수축기": "채권, 현금 비중 확대",
            "침체기": "채권, 금, 필수소비재 집중"
        }
        
        if economic_cycle in cycle_suggestions:
            suggestions.append({
                "type": "cycle_based",
                "reason": f"현재 경제 사이클: {economic_cycle}",
                "suggestion": cycle_suggestions[economic_cycle],
                "priority": "medium"
            })
        
        return suggestions
    
    def generate_rebalance_orders(self, actions: List[RebalanceAction],
                                   execute_sells_first: bool = True) -> List[Dict]:
        """
        리밸런싱 주문 생성 (실행 순서 포함)
        
        Args:
            actions: RebalanceAction 리스트
            execute_sells_first: 매도 먼저 실행 여부
        
        Returns:
            주문 리스트 (순서대로)
        """
        orders = []
        
        # 매도/매수 분리
        sells = [a for a in actions if a.action == "sell" and a.shares_to_trade > 0]
        buys = [a for a in actions if a.action == "buy" and a.shares_to_trade > 0]
        
        # 실행 순서 결정
        if execute_sells_first:
            ordered_actions = sells + buys
        else:
            ordered_actions = buys + sells
        
        for idx, action in enumerate(ordered_actions, 1):
            orders.append({
                "order": idx,
                "action": action.action.upper(),
                "ticker": action.ticker,
                "shares": action.shares_to_trade,
                "estimated_price": action.current_price,
                "estimated_amount": action.shares_to_trade * action.current_price,
                "reason": f"현재 {action.current_percent:.1f}% → 목표 {action.target_percent:.1f}%"
            })
        
        return orders


# 전역 인스턴스
rebalance_calculator = RebalanceCalculator()
