"""
시각화 모듈
차트 및 그래프 생성
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


class StockVisualizer:
    """주식 시각화 클래스"""
    
    def __init__(self, style: str = 'seaborn-v0_8-whitegrid'):
        try:
            plt.style.use(style)
        except:
            plt.style.use('classic')
        
        self.colors = {
            'up': '#26A69A',      # 상승 - 녹색
            'down': '#EF5350',    # 하락 - 빨간색
            'neutral': '#42A5F5', # 중립 - 파란색
            'ma20': '#FF9800',    # 20일 이동평균 - 주황색
            'ma50': '#9C27B0',    # 50일 이동평균 - 보라색
            'ma200': '#795548',   # 200일 이동평균 - 갈색
        }
    
    def plot_price_with_ma(self, data: pd.DataFrame, 
                           ticker: str,
                           mas: List[int] = [20, 50, 200],
                           save_path: Optional[str] = None) -> None:
        """가격 차트 + 이동평균선"""
        fig, ax = plt.subplots(figsize=(14, 7))
        
        # 종가 그래프
        ax.plot(data.index, data['Close'], label='종가', color=self.colors['neutral'], linewidth=1.5)
        
        # 이동평균선
        ma_colors = [self.colors['ma20'], self.colors['ma50'], self.colors['ma200']]
        for i, ma in enumerate(mas):
            if len(data) >= ma:
                ma_data = data['Close'].rolling(window=ma).mean()
                ax.plot(data.index, ma_data, label=f'MA{ma}', 
                       color=ma_colors[i % len(ma_colors)], linewidth=1, alpha=0.8)
        
        ax.set_title(f'{ticker} 가격 차트', fontsize=14, fontweight='bold')
        ax.set_xlabel('날짜')
        ax.set_ylabel('가격')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        
        # x축 날짜 포맷
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        
        plt.show()
    
    def plot_rsi(self, data: pd.DataFrame, 
                 period: int = 14,
                 save_path: Optional[str] = None) -> None:
        """RSI 차트"""
        # RSI 계산
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        fig, ax = plt.subplots(figsize=(14, 4))
        
        ax.plot(data.index, rsi, color=self.colors['neutral'], linewidth=1.5)
        ax.axhline(y=70, color=self.colors['down'], linestyle='--', alpha=0.7, label='과매수 (70)')
        ax.axhline(y=30, color=self.colors['up'], linestyle='--', alpha=0.7, label='과매도 (30)')
        ax.fill_between(data.index, 70, 100, alpha=0.1, color=self.colors['down'])
        ax.fill_between(data.index, 0, 30, alpha=0.1, color=self.colors['up'])
        
        ax.set_title(f'RSI ({period}일)', fontsize=12, fontweight='bold')
        ax.set_ylabel('RSI')
        ax.set_ylim(0, 100)
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        
        plt.show()
    
    def plot_fear_greed_gauge(self, value: float, 
                              save_path: Optional[str] = None) -> None:
        """공포탐욕 지수 게이지 차트"""
        fig, ax = plt.subplots(figsize=(8, 6), subplot_kw={'projection': 'polar'})
        
        # 반원 게이지 설정
        theta = np.linspace(np.pi, 0, 100)
        
        # 배경 구간 (극도의 공포 -> 극도의 탐욕)
        colors = ['#8B0000', '#FF4500', '#FFD700', '#90EE90', '#006400']
        bounds = [0, 25, 45, 55, 75, 100]
        
        for i in range(len(colors)):
            start = bounds[i] / 100 * np.pi
            end = bounds[i + 1] / 100 * np.pi
            ax.barh(1, end - start, left=np.pi - end, height=0.5, color=colors[i], alpha=0.7)
        
        # 현재 값 표시 (바늘)
        needle_angle = np.pi - (value / 100 * np.pi)
        ax.annotate('', xy=(needle_angle, 1.3), xytext=(needle_angle, 0),
                   arrowprops=dict(arrowstyle='->', color='black', lw=2))
        
        # 값 표시
        ax.text(np.pi/2, -0.3, f'{value:.0f}', ha='center', va='center', 
               fontsize=24, fontweight='bold')
        
        # 레이블
        if value < 25:
            label = "극도의 공포"
            color = colors[0]
        elif value < 45:
            label = "공포"
            color = colors[1]
        elif value < 55:
            label = "중립"
            color = colors[2]
        elif value < 75:
            label = "탐욕"
            color = colors[3]
        else:
            label = "극도의 탐욕"
            color = colors[4]
        
        ax.text(np.pi/2, -0.6, label, ha='center', va='center', 
               fontsize=14, fontweight='bold', color=color)
        
        ax.set_ylim(-1, 1.5)
        ax.set_theta_zero_location('S')
        ax.axis('off')
        ax.set_title('공포탐욕 지수', fontsize=14, fontweight='bold', pad=20)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        
        plt.show()
    
    def plot_market_dashboard(self, market_data: Dict,
                              save_path: Optional[str] = None) -> None:
        """시장 대시보드"""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # VIX
        ax1 = axes[0, 0]
        vix_value = market_data.get('vix', {}).get('current', 0)
        colors = ['#26A69A' if vix_value < 20 else '#FFD700' if vix_value < 30 else '#EF5350']
        ax1.barh(['VIX'], [vix_value], color=colors[0])
        ax1.axvline(x=20, color='gray', linestyle='--', alpha=0.7)
        ax1.axvline(x=30, color='gray', linestyle='--', alpha=0.7)
        ax1.set_xlim(0, 50)
        ax1.set_title(f'VIX: {vix_value:.1f}', fontweight='bold')
        ax1.text(20, -0.3, '20', ha='center', fontsize=9)
        ax1.text(30, -0.3, '30', ha='center', fontsize=9)
        
        # 10년 금리
        ax2 = axes[0, 1]
        rate = market_data.get('treasury_10y', {}).get('current', 0)
        ax2.barh(['10Y 금리'], [rate], color='#42A5F5')
        ax2.set_xlim(0, 6)
        ax2.set_title(f'10년 국채 금리: {rate:.2f}%', fontweight='bold')
        
        # S&P 500 Forward P/E
        ax3 = axes[1, 0]
        fpe = market_data.get('sp500_forward_pe', 20)
        color = '#26A69A' if fpe < 18 else '#FFD700' if fpe < 22 else '#EF5350'
        ax3.barh(['F-P/E'], [fpe], color=color)
        ax3.axvline(x=15, color='gray', linestyle='--', alpha=0.7)
        ax3.axvline(x=20, color='gray', linestyle='--', alpha=0.7)
        ax3.axvline(x=25, color='gray', linestyle='--', alpha=0.7)
        ax3.set_xlim(0, 35)
        ax3.set_title(f'S&P 500 Forward P/E: {fpe:.1f}', fontweight='bold')
        
        # 공포탐욕 지수
        ax4 = axes[1, 1]
        fg = market_data.get('fear_greed', {}).get('value', 50)
        if fg < 25:
            color = '#8B0000'
        elif fg < 45:
            color = '#FF4500'
        elif fg < 55:
            color = '#FFD700'
        elif fg < 75:
            color = '#90EE90'
        else:
            color = '#006400'
        ax4.barh(['공포탐욕'], [fg], color=color)
        ax4.set_xlim(0, 100)
        ax4.set_title(f'공포탐욕 지수: {fg:.0f}', fontweight='bold')
        ax4.text(25, -0.3, '공포', ha='center', fontsize=9)
        ax4.text(50, -0.3, '중립', ha='center', fontsize=9)
        ax4.text(75, -0.3, '탐욕', ha='center', fontsize=9)
        
        plt.suptitle('시장 대시보드', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        
        plt.show()
    
    def plot_valuation_comparison(self, stocks_data: List[Dict],
                                   save_path: Optional[str] = None) -> None:
        """밸류에이션 비교 차트"""
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        tickers = [s.get('ticker', 'N/A') for s in stocks_data]
        pers = [s.get('trailing_pe', 0) or 0 for s in stocks_data]
        pbrs = [s.get('price_to_book', 0) or 0 for s in stocks_data]
        margins = [(s.get('profit_margin', 0) or 0) * 100 for s in stocks_data]
        
        # PER 비교
        colors = [self.colors['up'] if p < 20 else self.colors['down'] if p > 30 else self.colors['neutral'] for p in pers]
        axes[0].bar(tickers, pers, color=colors)
        axes[0].axhline(y=20, color='gray', linestyle='--', alpha=0.7)
        axes[0].set_title('P/E Ratio', fontweight='bold')
        axes[0].set_ylabel('PER')
        
        # PBR 비교
        colors = [self.colors['up'] if p < 2 else self.colors['down'] if p > 4 else self.colors['neutral'] for p in pbrs]
        axes[1].bar(tickers, pbrs, color=colors)
        axes[1].axhline(y=3, color='gray', linestyle='--', alpha=0.7)
        axes[1].set_title('P/B Ratio', fontweight='bold')
        axes[1].set_ylabel('PBR')
        
        # 이익률 비교
        colors = [self.colors['up'] if m > 15 else self.colors['down'] if m < 5 else self.colors['neutral'] for m in margins]
        axes[2].bar(tickers, margins, color=colors)
        axes[2].set_title('Profit Margin', fontweight='bold')
        axes[2].set_ylabel('이익률 (%)')
        
        plt.suptitle('밸류에이션 비교', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        
        plt.show()


if __name__ == "__main__":
    # 테스트
    import yfinance as yf
    
    visualizer = StockVisualizer()
    
    # 테스트 데이터
    spy = yf.Ticker("SPY")
    data = spy.history(period="1y")
    
    print("=== 차트 테스트 ===")
    # visualizer.plot_price_with_ma(data, "SPY")
    # visualizer.plot_fear_greed_gauge(35)
    
    test_market = {
        'vix': {'current': 18.5},
        'treasury_10y': {'current': 4.25},
        'sp500_forward_pe': 21.5,
        'fear_greed': {'value': 62}
    }
    # visualizer.plot_market_dashboard(test_market)
    
    print("시각화 테스트 코드 준비 완료")
