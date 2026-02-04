"""
📊 주식 분석 대시보드 v2.0 - Streamlit 웹앱
추천 포트폴리오, 섹터별 대표 주식/ETF, 전문적 시장 전망 포함
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import sys
import os

# 환경 변수 로드 (로컬: .env, 클라우드: st.secrets 자동 연동)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # 클라우드 환경에서는 dotenv 불필요

# Streamlit Cloud secrets를 환경변수로 설정 (secrets.toml이 있을 때만)
try:
    if hasattr(st, 'secrets') and len(st.secrets) > 0:
        for key, value in st.secrets.items():
            if isinstance(value, str):
                os.environ.setdefault(key, value)
except Exception:
    pass  # 로컬 환경에서 secrets.toml 없어도 정상 작동

# 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 포트폴리오 데이터 임포트
from config.portfolio_data import (
    RECOMMENDED_PORTFOLIOS, SECTOR_REPRESENTATIVES, 
    REPRESENTATIVE_STOCKS, CYCLE_PORTFOLIO_ADJUSTMENTS,
    ASSET_CLASS_RECOMMENDATIONS
)

# 데이터베이스 임포트
from database.db_manager import db

# 리밸런싱 계산기 임포트
from utils.rebalance_calculator import rebalance_calculator

# 페이지 설정
st.set_page_config(
    page_title="📊 주식 분석 대시보드 v2",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일 추가
st.markdown("""
<style>
    .big-font { font-size: 24px !important; font-weight: bold; color: #FAFAFA !important; }
    .medium-font { font-size: 18px !important; color: #FAFAFA !important; }
    .card { 
        padding: 20px; 
        border-radius: 10px; 
        background-color: #262730;
        margin: 10px 0;
        color: #FAFAFA;
    }
    /* 다크모드용 메트릭 스타일 */
    [data-testid="stMetricValue"] { color: #FAFAFA !important; }
    [data-testid="stMetricLabel"] { color: #FAFAFA !important; }
    [data-testid="stMetricDelta"] svg { fill: currentColor; }
    
    /* 마크다운 테이블 다크모드 */
    .stMarkdown table { color: #FAFAFA !important; }
    .stMarkdown th, .stMarkdown td { color: #FAFAFA !important; border-color: #444 !important; }
    .stMarkdown th { background-color: #333 !important; }
    
    .risk-low { color: #28a745 !important; }
    .risk-medium { color: #ffc107 !important; }
    .risk-high { color: #dc3545 !important; }
    .ai-toggle-on { background-color: #28a745 !important; color: white !important; }
    .ai-toggle-off { background-color: #6c757d !important; color: white !important; }
    .login-box { 
        max-width: 400px; 
        margin: 50px auto; 
        padding: 30px;
        border-radius: 10px;
        background-color: #262730;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        color: #FAFAFA;
    }
    .profit { color: #28a745 !important; }
    .loss { color: #dc3545 !important; }
    
    /* caption 글씨 밝게 */
    .stCaption, small { color: #B0B0B0 !important; }
</style>
""", unsafe_allow_html=True)

# ==================== 앱 접근 비밀번호 (URL 공유 시 보호) ====================
def check_app_password():
    """앱 접근 비밀번호 확인 - URL을 공유받은 사람만 사용 가능"""
    
    # 앱 비밀번호 (Streamlit secrets 또는 환경변수에서 가져옴)
    # secrets.toml에 APP_PASSWORD = "your_password" 설정
    app_password = os.environ.get("APP_PASSWORD", "")
    
    # 비밀번호가 설정되지 않았으면 인증 건너뜀 (로컬 개발용)
    if not app_password:
        return True
    
    # 이미 앱 인증됨
    if st.session_state.get('app_authenticated', False):
        return True
    
    # 비밀번호 입력 UI
    st.markdown("""
    <div style="max-width: 400px; margin: 100px auto; padding: 40px; 
                border-radius: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);">
        <h1 style="color: white; text-align: center; margin-bottom: 10px;">📊 주식 분석 대시보드</h1>
        <p style="color: rgba(255,255,255,0.8); text-align: center; margin-bottom: 30px;">
            이 앱은 초대된 사용자만 이용할 수 있습니다
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password_input = st.text_input(
            "🔐 접근 비밀번호",
            type="password",
            placeholder="비밀번호를 입력하세요",
            key="app_password_input"
        )
        
        if st.button("🚀 입장하기", use_container_width=True, type="primary"):
            if password_input == app_password:
                st.session_state.app_authenticated = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 틀렸습니다")
        
        st.markdown("""
        <p style="text-align: center; color: #666; font-size: 12px; margin-top: 20px;">
            비밀번호는 초대한 사람에게 문의하세요
        </p>
        """, unsafe_allow_html=True)
    
    return False

# ==================== 인증 관련 세션 상태 ====================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'selected_portfolio_id' not in st.session_state:
    st.session_state.selected_portfolio_id = None

# 세션 상태 초기화
if 'analyzer' not in st.session_state:
    from main import StockAnalyzer
    st.session_state.analyzer = StockAnalyzer(ai_provider="github")  # GitHub Models 기본

if 'economic_cycle' not in st.session_state:
    st.session_state.economic_cycle = None

if 'market_data' not in st.session_state:
    st.session_state.market_data = None

# AI 제공자별 ON/OFF 상태 초기화
if 'ai_settings' not in st.session_state:
    st.session_state.ai_settings = {
        # Native API (기본 OFF - 수동 요청 시만 사용)
        'native_claude': False,
        'native_gpt': False,
        'native_gemini': False,
        # GitHub Models (기본 ON - 초기 로딩에 사용)
        'github_gpt': True,
        'github_deepseek': True,
        'github_llama': True,
        'github_phi': True,
        'github_mistral': True,
    }

# 분석 모드 초기화 (auto=초기 로딩, manual=버튼 클릭)
if 'analysis_mode' not in st.session_state:
    st.session_state.analysis_mode = 'auto'  # 기본값: 자동(GitHub 우선)


def get_active_models() -> dict:
    """현재 활성화된 AI 모델들 반환"""
    from ai_providers.team_debate import MODELS_BY_FAMILY, get_model_source
    
    active = {'native': [], 'github': []}
    settings = st.session_state.ai_settings
    
    # 설정에 따라 활성 모델 수집
    model_mapping = {
        'native_claude': ('claude', 'native'),
        'native_gpt': ('gpt', 'native'),
        'native_gemini': ('gemini', 'native'),
        'github_gpt': ('gpt', 'github'),
        'github_deepseek': ('deepseek', 'github'),
        'github_llama': ('llama', 'github'),
        'github_phi': ('phi', 'github'),
        'github_mistral': ('mistral', 'github'),
    }
    
    for setting_key, (family, expected_source) in model_mapping.items():
        if settings.get(setting_key, False):
            if family in MODELS_BY_FAMILY:
                for model in MODELS_BY_FAMILY[family]['models']:
                    source = get_model_source(model)
                    if expected_source == 'native' and source == 'native':
                        active['native'].append(model)
                    elif expected_source == 'github' and source == 'github':
                        active['github'].append(model)
    
    return active


def get_economic_cycle():
    """경제 사이클 데이터 (캐시)"""
    if st.session_state.economic_cycle is None:
        with st.spinner("🔄 경제 사이클 분석 중..."):
            st.session_state.economic_cycle = st.session_state.analyzer.get_economic_cycle()
    return st.session_state.economic_cycle


def get_market_data():
    """시장 데이터 (캐시)"""
    if st.session_state.market_data is None:
        with st.spinner("📊 시장 데이터 수집 중..."):
            st.session_state.market_data = st.session_state.analyzer.get_market_overview()
    return st.session_state.market_data


def create_gauge_chart(value, title, min_val=0, max_val=100, 
                       ranges=None, suffix=""):
    """게이지 차트 생성"""
    if ranges is None:
        ranges = [
            (0, 25, "green"),
            (25, 50, "lightgreen"),
            (50, 75, "orange"),
            (75, 100, "red")
        ]
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={'text': title, 'font': {'size': 16}},
        number={'suffix': suffix, 'font': {'size': 24}},
        gauge={
            'axis': {'range': [min_val, max_val]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [r[0], r[1]], 'color': r[2]} 
                for r in ranges
            ],
        }
    ))
    
    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    return fig


def create_colorbar_with_marker(value: float, title: str, min_val: float, max_val: float,
                                  ranges: list, current_label: str = None) -> go.Figure:
    """
    컬러바에 마커를 표시하는 시각화 생성
    
    Args:
        value: 현재 값
        title: 차트 제목
        min_val: 최소값
        max_val: 최대값
        ranges: [(start, end, color), ...] 형태의 범위 리스트
        current_label: 현재 상태 라벨
    
    Returns:
        Plotly Figure
    """
    fig = go.Figure()
    
    # 색상 범위 막대 추가
    for i, (start, end, color) in enumerate(ranges):
        fig.add_shape(
            type="rect",
            x0=start, x1=end, y0=0.3, y1=0.7,
            fillcolor=color,
            line=dict(width=0),
            layer="below"
        )
    
    # 현재 값 마커 (삼각형)
    fig.add_trace(go.Scatter(
        x=[value],
        y=[0.5],
        mode='markers+text',
        marker=dict(
            symbol='diamond',
            size=20,
            color='white',
            line=dict(color='black', width=2)
        ),
        text=[f"<b>{value:.1f}</b>"],
        textposition="top center",
        textfont=dict(size=14, color='white'),
        showlegend=False,
        hovertemplate=f"{title}: {value:.1f}<extra></extra>"
    ))
    
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>" + (f"<br><span style='font-size:12px;color:gray'>{current_label}</span>" if current_label else ""),
            x=0.5,
            font=dict(size=14)
        ),
        xaxis=dict(
            range=[min_val, max_val],
            showgrid=False,
            zeroline=False,
            showticklabels=True,
            tickvals=[r[0] for r in ranges] + [ranges[-1][1]],
            tickfont=dict(size=10)
        ),
        yaxis=dict(
            range=[0, 1],
            showgrid=False,
            zeroline=False,
            showticklabels=False
        ),
        height=100,
        margin=dict(l=10, r=10, t=50, b=20),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig


def create_historical_trend_chart(ticker: str, title: str, years: int = 5, 
                                   color: str = "#1f77b4") -> go.Figure:
    """
    최근 N년간 히스토리컬 추이 차트 생성
    
    Args:
        ticker: yfinance 티커 심볼
        title: 차트 제목
        years: 조회 기간 (년)
        color: 라인 색상
    
    Returns:
        Plotly Figure
    """
    import yfinance as yf
    from datetime import datetime, timedelta
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years*365)
    
    try:
        data = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), 
                          end=end_date.strftime('%Y-%m-%d'), progress=False)
        
        if data.empty:
            # 데이터가 없으면 빈 차트 반환
            fig = go.Figure()
            fig.add_annotation(
                text="데이터 없음",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(height=150, margin=dict(l=10, r=10, t=30, b=10))
            return fig
        
        # Close 컬럼 추출 (MultiIndex 대응)
        if isinstance(data.columns, pd.MultiIndex):
            close_data = data['Close'].iloc[:, 0] if len(data['Close'].columns) > 0 else data['Close']
        else:
            close_data = data['Close']
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=close_data.index,
            y=close_data.values,
            mode='lines',
            line=dict(color=color, width=2),
            fill='tozeroy',
            fillcolor=f'rgba{tuple(list(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + [0.1])}',
            hovertemplate='%{x|%Y-%m-%d}<br>값: %{y:.2f}<extra></extra>'
        ))
        
        # 최고/최저점 표시
        max_idx = close_data.idxmax()
        min_idx = close_data.idxmin()
        max_val = close_data.max()
        min_val = close_data.min()
        
        fig.add_trace(go.Scatter(
            x=[max_idx, min_idx],
            y=[max_val, min_val],
            mode='markers+text',
            marker=dict(size=8, color=['red', 'green']),
            text=[f'최고: {max_val:.1f}', f'최저: {min_val:.1f}'],
            textposition=['top center', 'bottom center'],
            textfont=dict(size=9),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        fig.update_layout(
            title=dict(text=f"📈 {title} ({years}년 추이)", font=dict(size=12)),
            xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
            yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
            height=180,
            margin=dict(l=10, r=10, t=35, b=10),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            hovermode='x unified'
        )
        
        return fig
        
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(
            text=f"차트 로드 실패",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=12, color="gray")
        )
        fig.update_layout(height=150, margin=dict(l=10, r=10, t=30, b=10))
        return fig


def create_vix_fear_greed_combined_chart(vix_value: float, fg_value: float, period: str = "1Y") -> go.Figure:
    """
    VIX와 공포탐욕 지수를 함께 보여주는 이중축 차트 (히스토리컬 + 현재값)
    
    Args:
        vix_value: 현재 VIX 값
        fg_value: 현재 공포탐욕 지수
        period: 기간 ("1M", "3M", "6M", "1Y", "2Y", "5Y")
    
    Returns:
        Plotly Figure
    """
    import yfinance as yf
    from datetime import datetime, timedelta
    
    # 기간 매핑
    period_days = {
        "1M": 30, "3M": 90, "6M": 180, 
        "1Y": 365, "2Y": 730, "5Y": 1825
    }
    days = period_days.get(period, 365)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    try:
        # VIX 데이터 가져오기
        vix_data = yf.download("^VIX", start=start_date.strftime('%Y-%m-%d'), 
                              end=end_date.strftime('%Y-%m-%d'), progress=False)
        
        if not vix_data.empty:
            if isinstance(vix_data.columns, pd.MultiIndex):
                vix_close = vix_data['Close'].iloc[:, 0]
            else:
                vix_close = vix_data['Close']
            
            # VIX 라인 (왼쪽 Y축)
            fig.add_trace(
                go.Scatter(
                    x=vix_close.index, y=vix_close.values,
                    name="VIX", line=dict(color="#dc3545", width=2),
                    hovertemplate='VIX: %{y:.1f}<extra></extra>'
                ),
                secondary_y=False
            )
            
            # 현재 VIX 마커
            fig.add_trace(
                go.Scatter(
                    x=[vix_close.index[-1]], y=[vix_value],
                    mode='markers+text',
                    marker=dict(size=12, color="#dc3545", symbol='diamond'),
                    text=[f'{vix_value:.1f}'],
                    textposition='top right',
                    name=f'현재 VIX: {vix_value:.1f}',
                    showlegend=False,
                    hoverinfo='skip'
                ),
                secondary_y=False
            )
        
        # 공포탐욕 지수는 히스토리컬 데이터가 없으므로 현재값만 표시
        # 가상의 평균선으로 참고 표시 (50 기준선)
        if fg_value:
            fig.add_hline(y=50, line_dash="dash", line_color="gray", 
                         annotation_text="F&G 중립(50)", secondary_y=True)
            
            # 현재 공포탐욕 수평선
            fig.add_hline(y=fg_value, line_dash="dot", line_color="#1f77b4",
                         annotation_text=f"현재 F&G: {fg_value:.0f}", secondary_y=True)
        
        # VIX 영역 표시 (배경)
        fig.add_hrect(y0=0, y1=15, fillcolor="green", opacity=0.1, 
                     line_width=0, secondary_y=False, annotation_text="안정")
        fig.add_hrect(y0=15, y1=20, fillcolor="lightgreen", opacity=0.1, 
                     line_width=0, secondary_y=False)
        fig.add_hrect(y0=20, y1=30, fillcolor="yellow", opacity=0.1, 
                     line_width=0, secondary_y=False, annotation_text="주의")
        fig.add_hrect(y0=30, y1=80, fillcolor="red", opacity=0.1, 
                     line_width=0, secondary_y=False, annotation_text="공포")
        
        fig.update_layout(
            title=dict(text=f"📊 VIX & 공포탐욕 지수 ({period})", font=dict(size=14)),
            height=280,
            margin=dict(l=10, r=10, t=40, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode='x unified'
        )
        
        fig.update_yaxes(title_text="VIX", secondary_y=False, range=[0, 80])
        fig.update_yaxes(title_text="공포탐욕(F&G)", secondary_y=True, range=[0, 100])
        
        return fig
        
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(text="데이터 로드 실패", x=0.5, y=0.5, 
                          xref="paper", yref="paper", showarrow=False)
        fig.update_layout(height=200)
        return fig


def create_index_chart(ticker: str, name: str, period: str = "1Y") -> go.Figure:
    """
    주요 지수 차트 생성
    
    Args:
        ticker: yfinance 티커
        name: 지수 이름
        period: 기간
    
    Returns:
        Plotly Figure
    """
    import yfinance as yf
    from datetime import datetime, timedelta
    
    period_days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "2Y": 730, "5Y": 1825}
    days = period_days.get(period, 365)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    try:
        data = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'),
                          end=end_date.strftime('%Y-%m-%d'), progress=False)
        
        if data.empty:
            fig = go.Figure()
            fig.add_annotation(text="데이터 없음", x=0.5, y=0.5,
                              xref="paper", yref="paper", showarrow=False)
            fig.update_layout(height=200)
            return fig
        
        if isinstance(data.columns, pd.MultiIndex):
            close = data['Close'].iloc[:, 0]
        else:
            close = data['Close']
        
        # 수익률 계산
        start_price = close.iloc[0]
        end_price = close.iloc[-1]
        return_pct = ((end_price - start_price) / start_price) * 100
        
        color = "#28a745" if return_pct >= 0 else "#dc3545"
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=close.index, y=close.values,
            mode='lines', name=name,
            line=dict(color=color, width=2),
            fill='tozeroy',
            fillcolor=f'rgba{tuple(list(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + [0.1])}',
            hovertemplate='%{x|%Y-%m-%d}<br>%{y:,.0f}<extra></extra>'
        ))
        
        # 현재값 마커
        fig.add_trace(go.Scatter(
            x=[close.index[-1]], y=[end_price],
            mode='markers+text',
            marker=dict(size=10, color=color),
            text=[f'{end_price:,.0f}'],
            textposition='top right',
            showlegend=False,
            hoverinfo='skip'
        ))
        
        fig.update_layout(
            title=dict(text=f"📈 {name} ({period}) | 수익률: {return_pct:+.1f}%", font=dict(size=13)),
            height=250,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
            yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
            hovermode='x unified'
        )
        
        return fig
        
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(text="차트 로드 실패", x=0.5, y=0.5,
                          xref="paper", yref="paper", showarrow=False)
        fig.update_layout(height=200)
        return fig


def create_multi_index_chart(selected_indices: list, index_options: dict, period: str = "1Y") -> go.Figure:
    """
    여러 지수를 동시에 비교하는 차트 생성 (수익률 정규화)
    
    Args:
        selected_indices: 선택된 지수 이름 리스트
        index_options: 지수 옵션 딕셔너리 {이름: (티커, 국기)}
        period: 기간
    
    Returns:
        Plotly Figure
    """
    import yfinance as yf
    from datetime import datetime, timedelta
    
    period_days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "2Y": 730, "5Y": 1825}
    days = period_days.get(period, 365)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # 색상 팔레트
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
              '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    
    fig = go.Figure()
    returns_info = []
    
    for i, index_name in enumerate(selected_indices):
        if index_name not in index_options:
            continue
            
        ticker, flag = index_options[index_name]
        color = colors[i % len(colors)]
        
        try:
            data = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'),
                              end=end_date.strftime('%Y-%m-%d'), progress=False)
            
            if data.empty:
                continue
            
            if isinstance(data.columns, pd.MultiIndex):
                close = data['Close'].iloc[:, 0]
            else:
                close = data['Close']
            
            # 수익률로 정규화 (시작점 = 0%)
            normalized = ((close / close.iloc[0]) - 1) * 100
            
            # 최종 수익률
            final_return = normalized.iloc[-1]
            returns_info.append((index_name, final_return, flag))
            
            fig.add_trace(go.Scatter(
                x=normalized.index, 
                y=normalized.values,
                mode='lines',
                name=f"{flag} {index_name}",
                line=dict(color=color, width=2),
                hovertemplate=f'{index_name}<br>%{{x|%Y-%m-%d}}<br>수익률: %{{y:+.1f}}%<extra></extra>'
            ))
            
        except Exception as e:
            continue
    
    # 0% 기준선
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    # 수익률 순위 정보
    if returns_info:
        returns_info.sort(key=lambda x: x[1], reverse=True)
        rank_text = " | ".join([f"{flag}{name}: {ret:+.1f}%" for name, ret, flag in returns_info])
    else:
        rank_text = "데이터 없음"
    
    fig.update_layout(
        title=dict(text=f"📊 지수 비교 ({period})", font=dict(size=14)),
        height=320,
        margin=dict(l=10, r=10, t=40, b=50),
        xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
        yaxis=dict(
            showgrid=True, 
            gridcolor='rgba(128,128,128,0.2)',
            title="수익률 (%)",
            ticksuffix="%"
        ),
        legend=dict(
            orientation="h", 
            yanchor="bottom", 
            y=-0.25, 
            xanchor="center", 
            x=0.5
        ),
        hovermode='x unified'
    )
    
    # 수익률 순위 annotation
    fig.add_annotation(
        text=rank_text,
        xref="paper", yref="paper",
        x=0.5, y=-0.35,
        showarrow=False,
        font=dict(size=10),
        align="center"
    )
    
    return fig


def get_exchange_rates() -> dict:
    """
    주요 환율 정보 가져오기 (달러/원, 엔/원, 위안/원, 유로/원)
    
    Returns:
        dict: 환율 정보
    """
    import yfinance as yf
    
    # 환율 티커 (yfinance)
    exchange_tickers = {
        "USD/KRW": "KRW=X",      # 달러/원
        "JPY/KRW": "JPYKRW=X",   # 엔/원 (100엔 기준은 별도 계산)
        "CNY/KRW": "CNYKRW=X",   # 위안/원
        "EUR/KRW": "EURKRW=X",   # 유로/원
    }
    
    rates = {}
    
    for name, ticker in exchange_tickers.items():
        try:
            data = yf.Ticker(ticker)
            hist = data.history(period="5d")
            
            if not hist.empty:
                current = hist['Close'].iloc[-1]
                previous = hist['Close'].iloc[-2] if len(hist) > 1 else current
                change = current - previous
                change_pct = (change / previous) * 100 if previous else 0
                
                rates[name] = {
                    "current": current,
                    "previous": previous,
                    "change": change,
                    "change_percent": change_pct
                }
            else:
                rates[name] = {"current": None, "error": "데이터 없음"}
        except Exception as e:
            rates[name] = {"current": None, "error": str(e)}
    
    return rates


def main():
    """메인 페이지"""
    
    # ===== 앱 접근 비밀번호 확인 =====
    if not check_app_password():
        return  # 비밀번호 틀리면 여기서 중단
    
    # 로그인된 사용자 활동 시간 갱신 (5분마다)
    if st.session_state.authenticated and st.session_state.user:
        last_activity_update = st.session_state.get('last_activity_update', 0)
        import time
        current_time = time.time()
        if current_time - last_activity_update > 300:  # 5분(300초) 경과 시
            db.update_last_activity(st.session_state.user['id'])
            st.session_state.last_activity_update = current_time
    
    # 헤더
    st.title("📊 주식 분석 대시보드 v2")
    st.markdown("*VIX, 10Y 금리, S&P F-P/E, 공포탐욕 지수 | 경제 사이클 | AI 분석 | 추천 포트폴리오*")
    
    # 사이드바
    with st.sidebar:
        st.header("⚙️ 설정")
        
        # ===== AI ON/OFF 토글 섹션 =====
        st.subheader("🤖 AI 모델 ON/OFF")
        
        st.caption("🔑 **Native API** (로그인 필요)")
        
        # 로그인 여부에 따라 Native API 활성화
        native_disabled = not st.session_state.authenticated
        if native_disabled:
            st.caption("⚠️ 로그인하면 Native API 사용 가능")
        
        col_n1, col_n2 = st.columns(2)
        with col_n1:
            st.session_state.ai_settings['native_claude'] = st.toggle(
                "🧠 Claude", 
                value=st.session_state.ai_settings.get('native_claude', False) if not native_disabled else False,
                key="toggle_native_claude",
                help="Anthropic Claude (API 키 필요)",
                disabled=native_disabled
            )
            st.session_state.ai_settings['native_gpt'] = st.toggle(
                "🤖 GPT",
                value=st.session_state.ai_settings.get('native_gpt', False) if not native_disabled else False,
                key="toggle_native_gpt",
                help="OpenAI GPT (API 키 필요)",
                disabled=native_disabled
            )
        with col_n2:
            st.session_state.ai_settings['native_gemini'] = st.toggle(
                "💎 Gemini",
                value=st.session_state.ai_settings.get('native_gemini', False) if not native_disabled else False,
                key="toggle_native_gemini",
                help="Google Gemini (API 키 필요)",
                disabled=native_disabled
            )
        
        st.caption("🐙 **GitHub Models** (초기 분석 시 사용)")
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.session_state.ai_settings['github_gpt'] = st.toggle(
                "🤖 GPT-4o",
                value=st.session_state.ai_settings.get('github_gpt', True),
                key="toggle_github_gpt",
                help="GitHub Models GPT-4o (무료)"
            )
            st.session_state.ai_settings['github_deepseek'] = st.toggle(
                "🔬 DeepSeek",
                value=st.session_state.ai_settings.get('github_deepseek', True),
                key="toggle_github_deepseek",
                help="DeepSeek R1 (무료)"
            )
            st.session_state.ai_settings['github_llama'] = st.toggle(
                "🦙 Llama",
                value=st.session_state.ai_settings.get('github_llama', True),
                key="toggle_github_llama",
                help="Meta Llama (무료)"
            )
        with col_g2:
            st.session_state.ai_settings['github_phi'] = st.toggle(
                "🔷 Phi",
                value=st.session_state.ai_settings.get('github_phi', True),
                key="toggle_github_phi",
                help="Microsoft Phi (무료)"
            )
            st.session_state.ai_settings['github_mistral'] = st.toggle(
                "⚡ Mistral",
                value=st.session_state.ai_settings.get('github_mistral', True),
                key="toggle_github_mistral",
                help="Mistral Codestral (무료)"
            )
        
        # 활성화된 AI 수 표시
        active_models = get_active_models()
        native_count = len(active_models['native'])
        github_count = len(active_models['github'])
        st.caption(f"활성: 🔑 Native {native_count}개 / 🐙 GitHub {github_count}개")
        
        st.divider()
        
        if st.button("🔄 데이터 새로고침"):
            st.session_state.economic_cycle = None
            st.session_state.market_data = None
            st.rerun()
        
        st.divider()
        
        # 로그인 상태 표시
        if st.session_state.authenticated:
            st.success(f"👤 {st.session_state.user['username']}님")
            if st.button("🚪 로그아웃"):
                st.session_state.authenticated = False
                st.session_state.user = None
                st.session_state.selected_portfolio_id = None
                st.rerun()
        else:
            st.info("🔐 로그인하면 포트폴리오 저장 가능")
        
        st.divider()
        
        # 현재 접속 중인 사용자 표시
        st.subheader("👥 현재 접속자")
        try:
            active_users = db.get_recently_active_users(minutes=30)
            if active_users:
                user_list = [u['username'] for u in active_users]
                # 현재 로그인한 사용자는 강조
                current_user = st.session_state.user['username'] if st.session_state.authenticated else None
                
                for username in user_list:
                    if username == current_user:
                        st.markdown(f"🟢 **{username}** (나)")
                    else:
                        st.markdown(f"🟢 {username}")
                
                st.caption(f"최근 30분 내 활동: {len(active_users)}명")
            else:
                st.caption("현재 접속자 없음")
        except Exception as e:
            st.caption(f"접속자 정보 로드 실패")
        
        st.divider()
        
        st.header("📑 메뉴")
        
        # 기본 메뉴
        menu_items = [
            "🏠 홈 (시장 개요)", 
            "📈 대표 주식 분석",
            "🔍 개별 주식 분석",
            "💼 포트폴리오",
            "🏭 섹터별 대표 종목",
            "📰 뉴스", 
            "🤖 AI 분석",
            "🎬 AI 토론"
        ]
        
        # 로그인 시 추가 메뉴
        if st.session_state.authenticated:
            menu_items.extend([
                "⚙️ 설정"
            ])
        else:
            menu_items.append("🔐 로그인/회원가입")
        
        page = st.radio(
            "페이지 선택",
            menu_items,
            index=0
        )
        
        st.divider()
        st.caption("📌 모든 분석은 참고용이며\n투자 결정은 본인 책임입니다.")
    
    # 페이지 라우팅
    if page == "🏠 홈 (시장 개요)":
        show_home_page()
    elif page == "📈 대표 주식 분석":
        show_representative_stocks_page()
    elif page == "🔍 개별 주식 분석":
        show_stock_analysis_page()
    elif page == "💼 포트폴리오":
        show_unified_portfolio_page()
    elif page == "🏭 섹터별 대표 종목":
        show_sector_representatives_page()
    elif page == "📰 뉴스":
        show_news_page()
    elif page == "🤖 AI 분석":
        show_ai_analysis_page()
    elif page == "🎬 AI 토론":
        show_unified_debate_page()
    elif page == "🔐 로그인/회원가입":
        show_login_page()
    elif page == "⚙️ 설정":
        show_settings_page()


def show_home_page():
    """홈 페이지 - 시장 개요"""
    
    # 데이터 로드
    market_data = get_market_data()
    economic_cycle = get_economic_cycle()
    
    # 경제 사이클 배너 (개선된 스타일)
    phase = economic_cycle['current_phase']
    confidence = economic_cycle['confidence']
    
    phase_colors = {
        "회복기": ("🟢", "#28a745"),
        "확장기": ("🔵", "#007bff"),
        "과열기": ("🟠", "#fd7e14"),
        "수축기": ("🟡", "#ffc107"),
        "침체기": ("🔴", "#dc3545")
    }
    
    phase_icon, phase_color = phase_colors.get(phase, ("⚪", "#6c757d"))
    
    st.markdown(f"""
    <div style="background-color: {phase_color}20; padding: 20px; border-radius: 10px; border-left: 5px solid {phase_color}; margin-bottom: 20px;">
        <h3>{phase_icon} 현재 경제 사이클: <strong>{phase}</strong></h3>
        <p>{economic_cycle.get('description', '')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 핵심 지표 카드
    st.subheader("📊 핵심 시장 지표")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # VIX
    vix_data = market_data['market_data']['vix']
    vix_value = vix_data['current']
    vix_change = vix_data.get('change_percent', 0)
    
    with col1:
        st.metric(
            label="🔥 VIX (변동성)",
            value=f"{vix_value:.2f}",
            delta=f"{vix_change:+.2f}%" if vix_change else None,
            delta_color="inverse"
        )
        st.caption(vix_data['interpretation'].get('level', ''))
    
    # 10년 국채 금리
    tnx_data = market_data['market_data']['treasury_10y']
    
    with col2:
        st.metric(
            label="📈 10Y 국채금리",
            value=f"{tnx_data['current']:.2f}%",
            delta=f"{tnx_data.get('change_percent', 0):+.2f}%" if tnx_data.get('change_percent') else None
        )
    
    # S&P 500 Forward P/E
    fpe = market_data['market_data']['sp500_forward_pe']
    sp500_data = market_data['market_data']['sp500']
    
    with col3:
        st.metric(
            label="📊 S&P F-P/E",
            value=f"{fpe:.1f}" if fpe else "N/A",
            delta=None
        )
        # S&P 500 현재가를 caption으로 표시
        if sp500_data:
            st.caption(f"S&P 500: {sp500_data['current']:,.0f} ({sp500_data.get('change_percent', 0):+.2f}%)")
    
    # 공포탐욕 지수
    fg_data = market_data['fear_greed_index']
    fg_value = fg_data.get('value', 50)
    
    with col4:
        st.metric(
            label="😱 공포탐욕 지수",
            value=f"{fg_value:.0f}" if fg_value else "N/A",
            delta=fg_data.get('rating', '')
        )
    
    # ===== 환율 정보 섹션 (테이블) =====
    st.divider()
    st.subheader("💱 주요 환율")
    
    exchange_rates = get_exchange_rates()
    
    # 환율 데이터를 테이블로 구성
    exchange_table_data = []
    
    # USD/KRW
    usd = exchange_rates.get("USD/KRW", {})
    if usd.get("current"):
        change_pct = usd.get('change_percent', 0)
        change_arrow = "🔺" if change_pct > 0 else "🔻" if change_pct < 0 else "➖"
        exchange_table_data.append({
            "통화": "🇺🇸 달러/원 (USD/KRW)",
            "현재": f"₩{usd['current']:,.1f}",
            "전일대비": f"{change_arrow} {change_pct:+.2f}%",
            "전일종가": f"₩{usd.get('previous', 0):,.1f}"
        })
    
    # JPY/KRW (100엔 기준)
    jpy = exchange_rates.get("JPY/KRW", {})
    if jpy.get("current"):
        jpy_100 = jpy['current'] * 100
        jpy_prev_100 = jpy.get('previous', jpy['current']) * 100
        change_pct = jpy.get('change_percent', 0)
        change_arrow = "🔺" if change_pct > 0 else "🔻" if change_pct < 0 else "➖"
        exchange_table_data.append({
            "통화": "🇯🇵 100엔/원 (JPY/KRW)",
            "현재": f"₩{jpy_100:,.1f}",
            "전일대비": f"{change_arrow} {change_pct:+.2f}%",
            "전일종가": f"₩{jpy_prev_100:,.1f}"
        })
    
    # CNY/KRW
    cny = exchange_rates.get("CNY/KRW", {})
    if cny.get("current"):
        change_pct = cny.get('change_percent', 0)
        change_arrow = "🔺" if change_pct > 0 else "🔻" if change_pct < 0 else "➖"
        exchange_table_data.append({
            "통화": "🇨🇳 위안/원 (CNY/KRW)",
            "현재": f"₩{cny['current']:,.1f}",
            "전일대비": f"{change_arrow} {change_pct:+.2f}%",
            "전일종가": f"₩{cny.get('previous', 0):,.1f}"
        })
    
    # EUR/KRW
    eur = exchange_rates.get("EUR/KRW", {})
    if eur.get("current"):
        change_pct = eur.get('change_percent', 0)
        change_arrow = "🔺" if change_pct > 0 else "🔻" if change_pct < 0 else "➖"
        exchange_table_data.append({
            "통화": "🇪🇺 유로/원 (EUR/KRW)",
            "현재": f"₩{eur['current']:,.1f}",
            "전일대비": f"{change_arrow} {change_pct:+.2f}%",
            "전일종가": f"₩{eur.get('previous', 0):,.1f}"
        })
    
    if exchange_table_data:
        df_exchange = pd.DataFrame(exchange_table_data)
        st.dataframe(
            df_exchange,
            hide_index=True,
            use_container_width=True,
            column_config={
                "통화": st.column_config.TextColumn("통화", width="medium"),
                "현재": st.column_config.TextColumn("현재가", width="small"),
                "전일대비": st.column_config.TextColumn("전일대비", width="small"),
                "전일종가": st.column_config.TextColumn("전일종가", width="small")
            }
        )
    else:
        st.warning("환율 데이터를 가져올 수 없습니다.")
    
    st.divider()
    
    # ===== 지표 시각화 섹션 (개선) =====
    st.subheader("📉 지표 시각화")
    
    # 기간 선택 및 지수 선택
    opt_col1, opt_col2 = st.columns([1, 2])
    
    with opt_col1:
        chart_period = st.selectbox(
            "📅 차트 기간",
            options=["1M", "3M", "6M", "1Y", "2Y", "5Y"],
            index=3,  # 기본값 1Y
            key="home_chart_period"
        )
    
    with opt_col2:
        index_options = {
            "S&P 500": ("^GSPC", "🇺🇸"),
            "나스닥 100": ("^NDX", "🇺🇸"),
            "다우존스": ("^DJI", "🇺🇸"),
            "코스피": ("^KS11", "🇰🇷"),
            "코스닥": ("^KQ11", "🇰🇷"),
            "니케이 225": ("^N225", "🇯🇵"),
            "항셍": ("^HSI", "🇭🇰"),
            "상해종합": ("000001.SS", "🇨🇳"),
            "DAX": ("^GDAXI", "🇩🇪"),
            "FTSE 100": ("^FTSE", "🇬🇧")
        }
        selected_indices = st.multiselect(
            "📊 비교할 지수 선택 (다중 선택 가능)",
            options=list(index_options.keys()),
            default=["S&P 500", "코스피"],
            key="home_index_multiselect"
        )
    
    # 색상 범례 (접을 수 있게)
    with st.expander("📋 VIX & 공포탐욕 지수 범례", expanded=False):
        col_legend1, col_legend2 = st.columns(2)
        
        with col_legend1:
            st.markdown("""
            <div style="background: linear-gradient(90deg, #28a745, #90EE90, #ffc107, #dc3545); height: 12px; border-radius: 6px; margin-bottom: 5px;"></div>
            """, unsafe_allow_html=True)
            st.markdown("""
            | VIX 범위 | 상태 | 투자 의미 |
            |:---:|:---:|:---|
            | **0-15** 🟢 | 극저변동성 | 시장 안정 |
            | **15-20** 🟢 | 저변동성 | 정상 환경 |
            | **20-30** 🟡 | 중간 변동성 | 주의 필요 |
            | **30+** 🔴 | 고변동성 | 공포/기회 |
            """)
        
        with col_legend2:
            st.markdown("""
            <div style="background: linear-gradient(90deg, #dc3545, #fd7e14, #6c757d, #90EE90, #28a745); height: 12px; border-radius: 6px; margin-bottom: 5px;"></div>
            """, unsafe_allow_html=True)
            st.markdown("""
            | F&G 범위 | 상태 | 투자 의미 |
            |:---:|:---:|:---|
            | **0-25** 🔴 | 극도의 공포 | 매수 기회 |
            | **25-45** 🟠 | 공포 | 저가 매수 |
            | **45-55** ⚪ | 중립 | 균형 시장 |
            | **55-75** 🟢 | 탐욕 | 차익 실현 |
            | **75-100** 💚 | 극도의 탐욕 | 과열 경계 |
            """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # VIX 컬러바
        st.caption("💡 VIX: 낮을수록(🟢) 시장 안정, 높을수록(🔴) 변동성 확대")
        
        if vix_value < 15:
            vix_label = "🟢 극저변동성 - 시장 안정"
        elif vix_value < 20:
            vix_label = "🟢 저변동성 - 정상 환경"
        elif vix_value < 30:
            vix_label = "🟡 중간 변동성 - 주의 필요"
        else:
            vix_label = "🔴 고변동성 - 공포/매수기회"
        
        vix_colorbar = create_colorbar_with_marker(
            vix_value, "VIX 지수",
            min_val=0, max_val=50,
            ranges=[
                (0, 15, "#28a745"),
                (15, 20, "#90EE90"),
                (20, 30, "#ffc107"),
                (30, 50, "#dc3545")
            ],
            current_label=vix_label
        )
        st.plotly_chart(vix_colorbar, use_container_width=True)
        
        # VIX와 공포탐욕 통합 차트
        fg_val = fg_value if fg_value else 50
        combined_chart = create_vix_fear_greed_combined_chart(vix_value, fg_val, chart_period)
        st.plotly_chart(combined_chart, use_container_width=True)
    
    with col2:
        # 공포탐욕 컬러바
        st.caption("💡 Fear & Greed: 낮을수록(🔴) 공포(매수기회), 높을수록(🟢) 탐욕(과열주의)")
        
        fg_val = fg_value if fg_value else 50
        
        if fg_val < 25:
            fg_label = "🔴 극도의 공포 - 매수 기회"
        elif fg_val < 45:
            fg_label = "🟠 공포 - 저가 매수 구간"
        elif fg_val < 55:
            fg_label = "⚪ 중립 - 균형 시장"
        elif fg_val < 75:
            fg_label = "🟢 탐욕 - 차익 실현 고려"
        else:
            fg_label = "💚 극도의 탐욕 - 과열 경계"
        
        fg_colorbar = create_colorbar_with_marker(
            fg_val, "공포탐욕 지수",
            min_val=0, max_val=100,
            ranges=[
                (0, 25, "#dc3545"),
                (25, 45, "#fd7e14"),
                (45, 55, "#6c757d"),
                (55, 75, "#90EE90"),
                (75, 100, "#28a745")
            ],
            current_label=fg_label
        )
        st.plotly_chart(fg_colorbar, use_container_width=True)
    
    # 다중 지수 비교 차트 (전체 너비)
    if selected_indices:
        multi_index_chart = create_multi_index_chart(selected_indices, index_options, chart_period)
        st.plotly_chart(multi_index_chart, use_container_width=True)
    else:
        st.info("📊 비교할 지수를 선택해주세요.")
    
    # 추천 자산 배분 및 섹터
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💡 경제 사이클 기반 추천 자산 배분")
        allocation = economic_cycle.get('recommendations', {}).get('asset_allocation', {})
        
        if allocation:
            # 호버 정보 생성
            asset_names = list(allocation.keys())
            asset_values = list(allocation.values())
            
            # 호버 텍스트 생성 - 각 자산에 대한 상세 정보
            hover_texts = []
            custom_data = []
            
            for asset_name in asset_names:
                # ASSET_CLASS_RECOMMENDATIONS에서 매핑된 키 찾기
                asset_key_map = {
                    "주식": "주식", "주식형": "주식", "미국주식": "주식", "주식(미국)": "주식",
                    "채권": "채권", "채권형": "채권", "국채": "채권", "회사채": "채권",
                    "금": "금", "골드": "금", "금/원자재": "금",
                    "현금": "현금", "현금성": "현금", "달러": "현금", "현금/달러": "현금",
                    "원자재": "원자재", "커머디티": "원자재",
                    "부동산": "부동산", "리츠": "부동산", "REITs": "부동산"
                }
                
                # 매핑된 키로 데이터 가져오기
                mapped_key = None
                for key, mapped in asset_key_map.items():
                    if key in asset_name or asset_name in key:
                        mapped_key = mapped
                        break
                
                if mapped_key and mapped_key in ASSET_CLASS_RECOMMENDATIONS:
                    rec = ASSET_CLASS_RECOMMENDATIONS[mapped_key]
                    
                    # 현재 경기 사이클에 맞는 추천 가져오기
                    cycle_rec = rec.get('cycle_recommendations', {}).get(phase, "시장 상황에 따라 조절")
                    
                    # ETF 목록 문자열 생성
                    etfs = rec.get('etfs', [])
                    etf_str = ", ".join([f"{e['ticker']}({e['name']})" for e in etfs[:3]])
                    
                    hover_text = (
                        f"<b>{rec['icon']} {asset_name}</b><br>"
                        f"<b>비중:</b> %{{percent}}<br><br>"
                        f"<b>설명:</b> {rec['description']}<br><br>"
                        f"<b>추천 ETF:</b><br>{etf_str}<br><br>"
                        f"<b>{phase} 전략:</b><br>{cycle_rec}"
                    )
                    custom_data.append([rec['description'], etf_str, cycle_rec])
                else:
                    hover_text = f"<b>{asset_name}</b><br>비중: %{{percent}}"
                    custom_data.append(["", "", ""])
                
                hover_texts.append(hover_text)
            
            fig = go.Figure(data=[go.Pie(
                values=asset_values,
                labels=asset_names,
                hole=0.4,
                hovertemplate="%{customdata[0]}<br><br><b>추천 ETF:</b><br>%{customdata[1]}<br><br><b>전략:</b> %{customdata[2]}<extra>%{label}: %{percent}</extra>",
                customdata=custom_data,
                textinfo='label+percent',
                textfont=dict(size=12)
            )])
            
            fig.update_layout(
                title=dict(text=f"🔄 {phase} 추천 자산 배분", font=dict(size=16)),
                height=400,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.15),
                annotations=[dict(
                    text=f"<b>{phase}</b>",
                    x=0.5, y=0.5,
                    font_size=14,
                    showarrow=False
                )]
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 자산별 간단 설명 expander
            with st.expander("💡 자산별 추천 상세보기"):
                for asset_name in asset_names:
                    # 매핑 찾기
                    asset_key_map = {
                        "주식": "주식", "주식형": "주식", "미국주식": "주식", "주식(미국)": "주식",
                        "채권": "채권", "채권형": "채권", "국채": "채권", "회사채": "채권",
                        "금": "금", "골드": "금", "금/원자재": "금",
                        "현금": "현금", "현금성": "현금", "달러": "현금", "현금/달러": "현금",
                        "원자재": "원자재", "커머디티": "원자재",
                        "부동산": "부동산", "리츠": "부동산", "REITs": "부동산"
                    }
                    
                    mapped_key = None
                    for key, mapped in asset_key_map.items():
                        if key in asset_name or asset_name in key:
                            mapped_key = mapped
                            break
                    
                    if mapped_key and mapped_key in ASSET_CLASS_RECOMMENDATIONS:
                        rec = ASSET_CLASS_RECOMMENDATIONS[mapped_key]
                        st.markdown(f"**{rec['icon']} {asset_name}** ({allocation.get(asset_name, 0)}%)")
                        st.caption(f"└ {rec['description']}")
                        
                        etfs = rec.get('etfs', [])
                        etf_str = " | ".join([f"`{e['ticker']}`" for e in etfs[:3]])
                        st.caption(f"└ 추천 ETF: {etf_str}")
                        
                        cycle_rec = rec.get('cycle_recommendations', {}).get(phase, "")
                        if cycle_rec:
                            st.caption(f"└ {phase} 전략: {cycle_rec}")
                        st.markdown("---")
    
    with col2:
        st.subheader("🏭 추천 섹터 및 대표 ETF")
        sectors = economic_cycle.get('recommendations', {}).get('sectors', [])
        
        for sector in sectors:
            sector_data = SECTOR_REPRESENTATIVES.get(sector, {})
            st.markdown(f"**• {sector}**")
            if sector_data:
                etfs = sector_data.get('etfs', [])[:2]
                for etf in etfs:
                    st.caption(f"  └ {etf['ticker']}: {etf['name']} (보수: {etf['expense_ratio']}%)")


def create_economic_cycle_gauge(phase: str, confidence: int) -> go.Figure:
    """
    경제 사이클 속도계 스타일 게이지 차트 생성
    
    5단계: 침체기(0-20) → 회복기(20-40) → 확장기(40-60) → 과열기(60-80) → 수축기(80-100)
    
    Args:
        phase: 현재 경제 단계
        confidence: 신뢰도 (%)
    
    Returns:
        Plotly Figure
    """
    
    # 각 단계별 점수 매핑
    phase_scores = {
        "침체기": 10,
        "회복기": 30,
        "확장기": 50,
        "과열기": 70,
        "수축기": 90
    }
    
    score = phase_scores.get(phase, 50)
    
    # 이모지 매핑
    phase_emojis = {
        "침체기": "❄️",
        "회복기": "🌱",
        "확장기": "☀️",
        "과열기": "🔥",
        "수축기": "🌧️"
    }
    
    emoji = phase_emojis.get(phase, "📊")
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={
            'text': f"<b>경제 사이클</b><br><span style='font-size:1.2em'>{emoji} {phase}</span><br><span style='font-size:0.7em;color:gray'>신뢰도: {confidence}%</span>", 
            'font': {'size': 20}
        },
        number={'suffix': "", 'font': {'size': 1, 'color': 'rgba(0,0,0,0)'}},  # 숫자 숨김
        gauge={
            'axis': {
                'range': [0, 100], 
                'tickwidth': 2, 
                'tickcolor': "darkblue",
                'ticktext': ["침체기", "회복기", "확장기", "과열기", "수축기"],
                'tickvals': [10, 30, 50, 70, 90],
                'tickfont': {'size': 11}
            },
            'bar': {'color': "rgba(0,0,0,0.7)", 'thickness': 0.3},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 20], 'color': '#4169E1'},      # 침체기 - 파랑 (차가움)
                {'range': [20, 40], 'color': '#90EE90'},     # 회복기 - 연두색 (새싹)
                {'range': [40, 60], 'color': '#FFD700'},     # 확장기 - 금색 (번영)
                {'range': [60, 80], 'color': '#FF6347'},     # 과열기 - 토마토색 (뜨거움)
                {'range': [80, 100], 'color': '#708090'}     # 수축기 - 슬레이트그레이 (하강)
            ],
            'threshold': {
                'line': {'color': "black", 'width': 6},
                'thickness': 0.85,
                'value': score
            }
        }
    ))
    
    fig.update_layout(
        height=320,
        font={'family': "Arial", 'size': 14},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    
    return fig


def show_economic_cycle_page():
    """경제 사이클 상세 페이지 (전문적 분석 + AI 토론)"""
    
    st.header("🔄 경제 사이클 분석")
    
    economic_cycle = get_economic_cycle()
    market_data = get_market_data()
    
    # 현재 단계
    phase = economic_cycle['current_phase']
    confidence = economic_cycle['confidence']
    description = economic_cycle['description']
    outlook = economic_cycle.get('market_outlook', {})
    
    # 사이클 시각화
    phases = ["회복기", "확장기", "과열기", "수축기", "침체기"]
    current_idx = phases.index(phase) if phase in phases else 0
    
    # ========== 속도계 스타일 경제 사이클 표시 ==========
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # 속도계 게이지
        cycle_gauge = create_economic_cycle_gauge(phase, confidence)
        st.plotly_chart(cycle_gauge, use_container_width=True)
    
    with col2:
        st.markdown("### 📊 현재 상태")
        st.info(description)
        
        # 매크로 관점 (전문적 분석)
        if outlook.get('macro_view'):
            st.markdown("### 🔭 매크로 관점")
            st.success(outlook['macro_view'])
    
    st.divider()
    
    # 동적 조정값 & 투자 지표
    st.subheader("📈 동적 투자 지표")
    col1, col2, col3, col4 = st.columns(4)
    
    adj = economic_cycle.get('dynamic_adjustments', {})
    
    with col1:
        st.metric("적정 PER", f"{adj.get('adjusted_per_fair', 20):.1f}")
    with col2:
        st.metric("VIX 경계", f"{adj.get('adjusted_vix_threshold', 25):.1f}")
    with col3:
        st.metric("PER 배수", f"{adj.get('per_multiplier', 1.0):.2f}x")
    with col4:
        if outlook.get('risk_level'):
            st.metric("리스크 수준", outlook['risk_level'])
    
    st.divider()
    
    # ========== AI 토론 기반 경제 분석 ==========
    st.subheader("🤖 AI 토론 기반 시장 심리 분석")
    
    st.markdown("""
    **Gemini 팀** (팀장: Gemini 3 Pro) vs **Claude 팀** (팀장: Claude Sonnet 4.5)
    
    심판: **Claude Opus 4.5**
    """)
    
    if st.button("🚀 AI 경제 분석 토론 시작", type="primary", use_container_width=True):
        run_economic_analysis_debate(market_data, economic_cycle)
    
    # 저장된 분석 결과가 있으면 표시
    if 'economic_analysis_result' in st.session_state:
        display_economic_analysis_result(st.session_state['economic_analysis_result'])
    
    st.divider()
    
    # 전문적 시장 전망
    st.subheader("🔮 전문가 수준 시장 전망")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**📅 단기 전망 (1-3개월)**")
        st.write(outlook.get('short_term', 'N/A'))
    
    with col2:
        st.markdown("**📅 중기 전망 (3-12개월)**")
        st.write(outlook.get('medium_term', 'N/A'))
    
    with col3:
        st.markdown("**📅 장기 전망 (1년+)**")
        st.write(outlook.get('long_term', 'N/A'))
    
    st.divider()
    
    # 리스크 & 기회 요인
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### ⚠️ 리스크 요인")
        risk_factors = outlook.get('risk_factors', [])
        if risk_factors:
            for risk in risk_factors:
                st.markdown(f"🔴 {risk}")
        else:
            st.write("현재 주요 리스크 요인 없음")
    
    with col2:
        st.markdown("### 💡 기회 요인")
        opp_factors = outlook.get('opportunity_factors', [])
        if opp_factors:
            for opp in opp_factors:
                st.markdown(f"🟢 {opp}")
        else:
            st.write("현재 주요 기회 요인 없음")
    
    # 투자 전략 권고
    st.divider()
    st.markdown("### 📋 투자 전략 권고")
    if outlook.get('strategy'):
        st.success(outlook['strategy'])
    
    # 주요 모니터링 지표
    st.markdown("### 📊 주요 모니터링 지표")
    key_indicators = outlook.get('key_indicators', [])
    if key_indicators:
        cols = st.columns(min(len(key_indicators), 4))
        for i, ind in enumerate(key_indicators):
            with cols[i % 4]:
                st.info(ind)
    
    # 사이클 다이어그램
    st.divider()
    st.markdown("### 🔄 경제 사이클 다이어그램")
    
    import math
    angles = [i * 72 for i in range(5)]  # 360/5 = 72도
    
    fig = go.Figure()
    
    for i, (p, angle) in enumerate(zip(phases, angles)):
        x = math.cos(math.radians(angle - 90))
        y = math.sin(math.radians(angle - 90))
        
        color = "#dc3545" if p == phase else "#e9ecef"
        size = 45 if p == phase else 30
        
        fig.add_trace(go.Scatter(
            x=[x], y=[y],
            mode='markers+text',
            marker=dict(size=size, color=color),
            text=[p],
            textposition="top center",
            textfont=dict(size=14 if p == phase else 11),
            name=p
        ))
    
    fig.update_layout(
        showlegend=False,
        xaxis=dict(visible=False, range=[-1.5, 1.5]),
        yaxis=dict(visible=False, range=[-1.5, 1.5]),
        height=400,
        title="경제 사이클 위치"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 추천 사항
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🏭 추천 섹터")
        sectors = economic_cycle.get('recommendations', {}).get('sectors', [])
        for sector in sectors:
            sector_info = SECTOR_REPRESENTATIVES.get(sector, {})
            if sector_info:
                st.write(f"**{sector}** - {sector_info.get('name', '')}")
            else:
                st.write(f"• {sector}")
    
    with col2:
        st.markdown("### 💰 추천 자산 배분")
        allocation = economic_cycle.get('recommendations', {}).get('asset_allocation', {})
        for asset, weight in allocation.items():
            st.write(f"• {asset}: {weight}%")


def create_sentiment_gauge(score: int, signal: str) -> go.Figure:
    """
    속도계 스타일 게이지 차트 생성 (AI 경제 분석용)
    
    Args:
        score: 0-100 점수
        signal: 시장 심리 신호 텍스트
    
    Returns:
        Plotly Figure
    """
    
    # 색상 구간 설정
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"<b>시장 심리</b><br><span style='font-size:0.8em;color:gray'>{signal}</span>", 
               'font': {'size': 24}},
        delta={'reference': 50, 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}},
        gauge={
            'axis': {
                'range': [0, 100], 
                'tickwidth': 2, 
                'tickcolor': "darkblue",
                'ticktext': ["극도의<br>공포", "공포", "중립", "탐욕", "극도의<br>탐욕"],
                'tickvals': [10, 30, 50, 70, 90],
                'tickfont': {'size': 12}
            },
            'bar': {'color': "darkblue", 'thickness': 0.3},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 20], 'color': '#006400'},      # 극도의 공포 - 진한 초록
                {'range': [20, 40], 'color': '#90EE90'},     # 공포 - 연한 초록
                {'range': [40, 60], 'color': '#FFD700'},     # 중립 - 노랑
                {'range': [60, 80], 'color': '#FFA500'},     # 탐욕 - 주황
                {'range': [80, 100], 'color': '#FF4500'}     # 극도의 탐욕 - 빨강
            ],
            'threshold': {
                'line': {'color': "black", 'width': 6},
                'thickness': 0.8,
                'value': score
            }
        }
    ))
    
    fig.update_layout(
        height=350,
        font={'family': "Arial", 'size': 16},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    
    return fig


def run_economic_analysis_debate(market_data: Dict, economic_cycle: Dict):
    """AI 경제 분석 토론 실행"""
    
    try:
        from ai_providers.team_debate import EconomicAnalysisDebate
    except ImportError as e:
        st.error(f"토론 모듈 로드 실패: {e}")
        return
    
    # 데이터 결합
    combined_data = {
        "market": market_data,
        "economic_cycle": economic_cycle,
        "timestamp": datetime.now().isoformat()
    }
    
    # UI 컨테이너
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    team_a_container = st.expander("🔵 GPT-4o 팀 분석", expanded=False)
    team_b_container = st.expander("🟣 GPT-4.1 팀 분석", expanded=False)
    debate_container = st.expander("⚔️ 토론 과정", expanded=False)
    judge_container = st.container()
    
    # 토론 실행
    debate = EconomicAnalysisDebate()
    result = None
    step = 0
    total_steps = 8
    
    for update in debate.analyze_economic_situation(combined_data):
        stage = update.get("stage", "")
        message = update.get("message", "")
        content = update.get("content", "")
        team = update.get("team", "")
        
        step += 1
        progress_bar.progress(min(step / total_steps, 0.99))
        status_text.text(message)
        
        # Team A 관련 stages
        if stage == "team_a_member_done":
            with team_a_container:
                st.markdown("**🧑‍💻 팀원 분석:**")
                st.markdown(content[:500] + "..." if len(str(content)) > 500 else content)
        
        elif stage == "team_a_done":
            with team_a_container:
                st.markdown("**👔 팀장 최종 분석:**")
                st.markdown(content)
        
        # Team B 관련 stages
        elif stage == "team_b_member_done":
            with team_b_container:
                st.markdown("**🧑‍💻 팀원 분석:**")
                st.markdown(content[:500] + "..." if len(str(content)) > 500 else content)
        
        elif stage == "team_b_done":
            with team_b_container:
                st.markdown("**👔 팀장 최종 분석:**")
                st.markdown(content)
        
        # 토론 stages
        elif stage == "team_a_rebuttal":
            with debate_container:
                st.markdown("**🔵 GPT-4o 팀 반박:**")
                st.markdown(content)
        
        elif stage == "team_b_rebuttal":
            with debate_container:
                st.markdown("**🟣 GPT-4.1 팀 반박:**")
                st.markdown(content)
        
        elif stage == "qa_done":
            with judge_container:
                st.markdown("### 🔍 QA 품질 검증 결과")
                
                # QA 결과 파싱 시도
                try:
                    import json
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', str(content))
                    if json_match:
                        qa_result = json.loads(json_match.group())
                        
                        # 팀별 분석 품질 요약
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("#### 🔵 GPT-4o 팀 평가")
                            quality = qa_result.get('quality_score', {})
                            team_a_score = quality.get('GPT-4o 팀', quality.get(debate.TEAM_A_NAME, 'N/A'))
                            st.metric("품질 점수", f"{team_a_score}/100" if isinstance(team_a_score, (int, float)) else team_a_score)
                            
                            strengths = qa_result.get('team_a_strengths', [])
                            if strengths:
                                st.markdown("**✅ 강점:**")
                                for s in strengths[:3]:
                                    st.markdown(f"- {s}")
                            
                            weaknesses = qa_result.get('team_a_weaknesses', [])
                            if weaknesses:
                                st.markdown("**⚠️ 약점:**")
                                for w in weaknesses[:3]:
                                    st.markdown(f"- {w}")
                        
                        with col2:
                            st.markdown("#### 🟣 GPT-4.1 팀 평가")
                            team_b_score = quality.get('GPT-4.1 팀', quality.get(debate.TEAM_B_NAME, 'N/A'))
                            st.metric("품질 점수", f"{team_b_score}/100" if isinstance(team_b_score, (int, float)) else team_b_score)
                            
                            strengths = qa_result.get('team_b_strengths', [])
                            if strengths:
                                st.markdown("**✅ 강점:**")
                                for s in strengths[:3]:
                                    st.markdown(f"- {s}")
                            
                            weaknesses = qa_result.get('team_b_weaknesses', [])
                            if weaknesses:
                                st.markdown("**⚠️ 약점:**")
                                for w in weaknesses[:3]:
                                    st.markdown(f"- {w}")
                        
                        st.divider()
                        
                        # QA 종합 의견
                        st.markdown("#### 📋 QA 종합 의견")
                        qa_verdict = qa_result.get('qa_verdict', '')
                        if qa_verdict:
                            st.info(qa_verdict)
                        
                        # 데이터/논리 오류
                        issues = qa_result.get('data_quality_issues', [])
                        if issues:
                            st.markdown("#### 🐛 발견된 문제점")
                            for issue in issues:
                                st.warning(issue)
                        
                        st.divider()
                        
                        # 최종 결론
                        st.markdown("#### 🎯 QA 최종 결론")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            better = qa_result.get('better_analysis', '동등')
                            st.metric("더 나은 분석", better)
                        
                        with col2:
                            score = qa_result.get('final_score', 50)
                            st.metric("시장 심리 점수", f"{score}/100")
                        
                        with col3:
                            signal = qa_result.get('final_signal', '중립')
                            st.metric("투자 신호", signal)
                        
                        # 핵심 인사이트
                        insights = qa_result.get('key_insights', [])
                        if insights:
                            st.markdown("#### 💡 핵심 인사이트")
                            for i, insight in enumerate(insights, 1):
                                st.markdown(f"{i}. {insight}")
                        
                        # 리스크 경고
                        risk = qa_result.get('risk_warning', '')
                        if risk:
                            st.error(f"⚠️ 리스크 경고: {risk}")
                        
                    else:
                        st.markdown(content)
                except Exception as e:
                    st.markdown(content)
        
        elif stage == "complete":
            result = update.get("result")
            progress_bar.progress(1.0)
            status_text.text("✅ 분석 완료!")
    
    if result:
        st.session_state['economic_analysis_result'] = result
        st.rerun()


def display_economic_analysis_result(result):
    """경제 분석 결과 표시 (속도계 게이지 포함)"""
    
    st.markdown("---")
    st.subheader("📊 AI 토론 결과")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # 속도계 게이지
        gauge_fig = create_sentiment_gauge(result.score, result.overall_signal)
        st.plotly_chart(gauge_fig, use_container_width=True)
    
    with col2:
        # 핵심 정보
        st.markdown("### 📈 시장 심리 지수")
        
        signal_colors = {
            "극도의 공포": "🟢",
            "공포": "🟢",
            "중립": "🟡",
            "탐욕": "🟠",
            "극도의 탐욕": "🔴"
        }
        
        st.metric("점수", f"{result.score}/100")
        st.metric("신호", f"{signal_colors.get(result.overall_signal, '⚪')} {result.overall_signal}")
        st.caption(f"분석 시간: {result.timestamp}")
    
    st.divider()
    
    # 포트폴리오 추천 (구체적 종목/ETF)
    st.subheader("💼 AI 추천 포트폴리오")
    
    portfolio = result.portfolio_recommendation
    if portfolio:
        # 포트폴리오 파이 차트
        col1, col2 = st.columns([1, 1])
        
        with col1:
            labels = list(portfolio.keys())
            values = list(portfolio.values())
            
            # 색상 매핑
            colors = []
            for label in labels:
                label_lower = label.lower()
                if 'spy' in label_lower or 'qqq' in label_lower or label_lower in ['주식', 'stock']:
                    colors.append('#2E86AB')  # 파랑 (주식)
                elif 'tlt' in label_lower or 'ief' in label_lower or label_lower in ['채권', 'bond']:
                    colors.append('#A23B72')  # 보라 (채권)
                elif 'gld' in label_lower or 'gold' in label_lower or label_lower in ['금', '원자재']:
                    colors.append('#F18F01')  # 금색
                elif '현금' in label_lower or 'cash' in label_lower:
                    colors.append('#95D5B2')  # 연한 초록
                else:
                    colors.append('#6C757D')  # 회색
            
            fig = go.Figure(data=[go.Pie(
                labels=labels, 
                values=values, 
                hole=0.4,
                marker_colors=colors,
                textinfo='label+percent',
                textfont_size=12
            )])
            
            fig.update_layout(
                title="추천 자산 배분",
                height=350,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2)
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### 📋 종목별 비중")
            
            for ticker, weight in sorted(portfolio.items(), key=lambda x: x[1], reverse=True):
                # 프로그레스 바로 시각화
                st.markdown(f"**{ticker}**")
                st.progress(weight / 100)
                st.caption(f"{weight}%")
    
    # 팀별 분석 요약
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.expander("🔵 Gemini 팀 분석", expanded=False):
            st.markdown(result.gemini_analysis)
    
    with col2:
        with st.expander("🟣 Claude 팀 분석", expanded=False):
            st.markdown(result.claude_analysis)
    
    # 최종 판결
    with st.expander("🏛️ Opus 심판 최종 판결", expanded=True):
        st.markdown(result.final_verdict)


def show_stock_analysis_page():
    """개별 주식 분석 페이지"""
    
    st.header("🔍 개별 주식 분석")
    st.markdown("*원하는 개별 종목을 직접 분석합니다*")
    
    # 티커 입력
    col1, col2 = st.columns([3, 1])
    
    with col1:
        ticker = st.text_input("티커 심볼 입력", value="AAPL", placeholder="예: AAPL, MSFT, GOOGL")
    
    with col2:
        st.write("")
        st.write("")
        analyze_btn = st.button("🔍 분석", use_container_width=True)
    
    if analyze_btn and ticker:
        with st.spinner(f"{ticker.upper()} 분석 중..."):
            try:
                analysis = st.session_state.analyzer.analyze_stock(ticker.upper())
                
                # 기본 정보
                val = analysis['valuation']
                
                st.subheader(f"🏢 {val.get('name', ticker.upper())}")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("현재가", f"${val['current_price']:,.2f}" if val['current_price'] else "N/A")
                
                with col2:
                    st.metric("PER", f"{val['trailing_pe']:.2f}" if val['trailing_pe'] else "N/A",
                             help=val.get('per_interpretation', ''))
                
                with col3:
                    st.metric("PBR", f"{val['price_to_book']:.2f}" if val['price_to_book'] else "N/A",
                             help=val.get('pbr_interpretation', ''))
                
                with col4:
                    st.metric("PEG", f"{val['peg_ratio']:.2f}" if val['peg_ratio'] else "N/A")
                
                # 경제 사이클 맥락
                ec = analysis.get('economic_context', {})
                st.info(f"📊 경제 단계: **{ec.get('phase', 'N/A')}** | 조정 적정 PER: **{val.get('adjusted_fair_per', 20):.1f}**")
                
                st.divider()
                
                # 수익성 & 성장성
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### 💰 수익성")
                    profit_margin = val.get('profit_margin')
                    operating_margin = val.get('operating_margin')
                    
                    if profit_margin:
                        st.metric("이익률", f"{profit_margin*100:.1f}%")
                    if operating_margin:
                        st.metric("영업이익률", f"{operating_margin*100:.1f}%")
                
                with col2:
                    st.markdown("### 📈 성장성")
                    growth = analysis['growth_metrics']
                    
                    if growth.get('revenue_growth'):
                        st.metric("매출 성장률", f"{growth['revenue_growth']*100:.1f}%")
                    if growth.get('earnings_growth'):
                        st.metric("이익 성장률", f"{growth['earnings_growth']*100:.1f}%")
                
                # 기술적 분석
                if analysis.get('technical_analysis'):
                    st.divider()
                    st.markdown("### 📉 기술적 분석")
                    
                    tech = analysis['technical_analysis']
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        rsi = tech['momentum']['rsi_14']
                        st.metric("RSI (14)", f"{rsi:.1f}", help=tech['momentum']['rsi_signal'])
                    
                    with col2:
                        st.metric("단기 트렌드", tech['trend']['short_term'])
                    
                    with col3:
                        st.metric("종합 신호", tech['signals']['overall'])
                
                # AI 심층 분석 버튼
                st.divider()
                
                # 활성화된 AI 모델 확인
                active_models = get_active_models()
                has_ai = len(active_models['github']) > 0 or len(active_models['native']) > 0
                
                if not has_ai:
                    st.warning("⚠️ AI 분석을 사용하려면 사이드바에서 최소 1개의 AI 모델을 활성화하세요.")
                
                if st.button(f"🤖 AI로 {ticker.upper()} 심층 분석", disabled=not has_ai, key=f"ai_analyze_{ticker}"):
                    with st.spinner("AI 분석 중... (최대 30초 소요)"):
                        try:
                            # GitHub Token 확인
                            github_token = os.environ.get("GITHUB_TOKEN", "")
                            if not github_token and 'github' in str(active_models['github']):
                                st.warning("⚠️ GITHUB_TOKEN이 설정되지 않았습니다. Secrets 설정을 확인하세요.")
                            
                            ai_analysis = st.session_state.analyzer.get_ai_stock_analysis(ticker.upper())
                            
                            if ai_analysis and not ai_analysis.startswith("AI 클라이언트가"):
                                st.success("✅ AI 분석 완료!")
                                st.markdown(ai_analysis)
                            else:
                                st.error(f"AI 분석 실패: {ai_analysis}")
                                st.info("💡 해결 방법: 사이드바에서 다른 AI 모델을 활성화하거나, Secrets에 API 키를 추가하세요.")
                        except Exception as e:
                            st.error(f"AI 분석 실패: {e}")
                            import traceback
                            with st.expander("🔍 상세 에러 정보"):
                                st.code(traceback.format_exc())
                
            except Exception as e:
                st.error(f"분석 실패: {e}")
    
    # 여러 주식 비교
    st.divider()
    st.subheader("📊 여러 주식 비교")
    
    tickers_input = st.text_input("티커 입력 (쉼표로 구분)", value="AAPL,MSFT,GOOGL,AMZN")
    
    if st.button("📊 비교 분석"):
        tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
        
        if tickers:
            with st.spinner("분석 중..."):
                results = st.session_state.analyzer.analyze_multiple_stocks(tickers)
                
                # 테이블로 표시
                data = []
                for r in results:
                    if 'error' not in r:
                        val = r['valuation']
                        data.append({
                            "티커": r['ticker'],
                            "현재가": f"${val['current_price']:,.2f}" if val['current_price'] else "N/A",
                            "PER": f"{val['trailing_pe']:.1f}" if val['trailing_pe'] else "N/A",
                            "PBR": f"{val['price_to_book']:.2f}" if val['price_to_book'] else "N/A",
                            "이익률": f"{val['profit_margin']*100:.1f}%" if val['profit_margin'] else "N/A",
                            "평가": val.get('per_interpretation', '')
                        })
                
                if data:
                    df = pd.DataFrame(data)
                    st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================
# 대표 주식 분석 페이지 (신규)
# ============================================================
def show_representative_stocks_page():
    """대표 주식 분석 페이지"""
    
    st.header("📈 대표 주식 분석")
    st.markdown("*카테고리별 대표 주식을 일괄 분석합니다*")
    
    # 카테고리 선택
    category = st.selectbox(
        "분석 카테고리 선택",
        list(REPRESENTATIVE_STOCKS.keys()),
        format_func=lambda x: REPRESENTATIVE_STOCKS[x]['name']
    )
    
    selected_tickers = REPRESENTATIVE_STOCKS[category]['tickers']
    st.info(f"**{REPRESENTATIVE_STOCKS[category]['name']}**: {', '.join(selected_tickers)}")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("🔍 선택 카테고리 전체 분석", use_container_width=True):
            run_batch_analysis(selected_tickers)
    
    with col2:
        # 전체 분석 옵션
        if st.button("📊 모든 카테고리 요약", use_container_width=True):
            show_all_categories_summary()


def run_batch_analysis(tickers):
    """대표 주식 일괄 분석"""
    progress_bar = st.progress(0)
    results = []
    
    for i, ticker in enumerate(tickers):
        with st.spinner(f"{ticker} 분석 중..."):
            try:
                analysis = st.session_state.analyzer.analyze_stock(ticker)
                results.append(analysis)
            except Exception as e:
                results.append({"ticker": ticker, "error": str(e)})
        progress_bar.progress((i + 1) / len(tickers))
    
    # 결과 테이블
    st.subheader("📊 분석 결과")
    
    data = []
    for r in results:
        if 'error' not in r:
            val = r['valuation']
            data.append({
                "티커": r['ticker'],
                "종목명": val.get('name', ''),
                "현재가": f"${val['current_price']:,.2f}" if val.get('current_price') else "N/A",
                "PER": f"{val['trailing_pe']:.1f}" if val.get('trailing_pe') else "N/A",
                "Forward PER": f"{val['forward_pe']:.1f}" if val.get('forward_pe') else "N/A",
                "PBR": f"{val['price_to_book']:.2f}" if val.get('price_to_book') else "N/A",
                "이익률": f"{val['profit_margin']*100:.1f}%" if val.get('profit_margin') else "N/A",
                "평가": val.get('per_interpretation', ''),
            })
        else:
            data.append({
                "티커": r['ticker'],
                "종목명": "⚠️ 오류",
                "현재가": "N/A",
                "PER": "N/A",
                "Forward PER": "N/A",
                "PBR": "N/A",
                "이익률": "N/A",
                "평가": r.get('error', '분석 실패')[:30],
            })
    
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 개별 상세 분석
        st.divider()
        st.subheader("📋 개별 상세 분석")
        
        for r in results:
            if 'error' not in r:
                val = r['valuation']
                with st.expander(f"📊 {r['ticker']} - {val.get('name', '')}"):
                    show_stock_detail_card(r)


def show_stock_detail_card(analysis):
    """주식 상세 정보 카드"""
    val = analysis['valuation']
    growth = analysis.get('growth_metrics', {})
    tech = analysis.get('technical_analysis', {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**💰 밸류에이션**")
        st.write(f"• Trailing PER: {val.get('trailing_pe', 'N/A')}")
        st.write(f"• Forward PER: {val.get('forward_pe', 'N/A')}")
        st.write(f"• PBR: {val.get('price_to_book', 'N/A')}")
        st.write(f"• PEG: {val.get('peg_ratio', 'N/A')}")
        st.caption(f"평가: {val.get('per_interpretation', '')}")
    
    with col2:
        st.markdown("**📈 성장성**")
        if growth.get('revenue_growth'):
            st.write(f"• 매출 성장률: {growth['revenue_growth']*100:.1f}%")
        if growth.get('earnings_growth'):
            st.write(f"• 이익 성장률: {growth['earnings_growth']*100:.1f}%")
        if val.get('profit_margin'):
            st.write(f"• 이익률: {val['profit_margin']*100:.1f}%")
    
    with col3:
        st.markdown("**📉 기술적 분석**")
        if tech:
            momentum = tech.get('momentum', {})
            trend = tech.get('trend', {})
            signals = tech.get('signals', {})
            
            st.write(f"• RSI: {momentum.get('rsi_14', 'N/A'):.1f}" if momentum.get('rsi_14') else "• RSI: N/A")
            st.write(f"• 단기 트렌드: {trend.get('short_term', 'N/A')}")
            st.write(f"• 종합 신호: {signals.get('overall', 'N/A')}")
        else:
            st.write("기술적 분석 데이터 없음")


def show_all_categories_summary():
    """모든 카테고리 요약"""
    st.subheader("📊 모든 카테고리 요약")
    
    for cat_key, cat_data in REPRESENTATIVE_STOCKS.items():
        with st.expander(f"**{cat_data['name']}** ({len(cat_data['tickers'])}개 종목)"):
            st.write(f"종목: {', '.join(cat_data['tickers'])}")
            
            if st.button(f"🔍 {cat_data['name']} 분석", key=f"analyze_{cat_key}"):
                run_batch_analysis(cat_data['tickers'])


# ============================================================
# 통합 포트폴리오 페이지 (추천 + 대가 + 내 포트폴리오)
# ============================================================
def show_unified_portfolio_page():
    """통합 포트폴리오 페이지"""
    from analyzers.portfolio_analyzer import PortfolioAnalyzer
    
    st.header("💼 포트폴리오")
    
    # 로그인 여부에 따라 탭 구성
    if st.session_state.authenticated:
        tabs = st.tabs([
            "📊 내 포트폴리오", 
            "🏆 대가 포트폴리오",
            "🎯 투자 스타일별 추천"
        ])
        
        with tabs[0]:
            show_my_portfolio_section()
        
        with tabs[1]:
            show_famous_portfolios_section()
        
        with tabs[2]:
            show_style_portfolios_section()
    else:
        tabs = st.tabs([
            "🏆 대가 포트폴리오",
            "🎯 투자 스타일별 추천",
            "📝 포트폴리오 비교 (직접 입력)"
        ])
        
        with tabs[0]:
            show_famous_portfolios_section()
        
        with tabs[1]:
            show_style_portfolios_section()
        
        with tabs[2]:
            show_manual_portfolio_comparison()


def show_my_portfolio_section():
    """내 포트폴리오 관리 섹션 (로그인 필요)"""
    user_id = st.session_state.user['id']
    
    # 포트폴리오 선택
    portfolios = db.get_portfolios(user_id)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if portfolios:
            portfolio_options = {p['name']: p['id'] for p in portfolios}
            selected_name = st.selectbox(
                "📂 포트폴리오 선택",
                list(portfolio_options.keys()),
                key="pf_select_main"
            )
            st.session_state.selected_portfolio_id = portfolio_options[selected_name]
        else:
            st.info("포트폴리오가 없습니다. 새로 만들어주세요.")
    
    with col2:
        with st.popover("➕ 새 포트폴리오"):
            new_name = st.text_input("이름", key="new_pf_name_main")
            new_desc = st.text_input("설명", key="new_pf_desc_main")
            if st.button("생성", key="create_pf_main", use_container_width=True):
                if new_name:
                    pf_id = db.create_portfolio(user_id, new_name, new_desc)
                    st.session_state.selected_portfolio_id = pf_id
                    st.success("✅ 생성됨")
                    st.rerun()
    
    if not st.session_state.selected_portfolio_id:
        return
    
    portfolio_id = st.session_state.selected_portfolio_id
    
    # 서브탭
    sub_tabs = st.tabs(["📊 보유 현황", "➕ 매매 기록", "📋 거래 내역", "⚖️ 리밸런싱", "🔍 대가 비교"])
    
    with sub_tabs[0]:
        show_holdings_section(user_id, portfolio_id)
    
    with sub_tabs[1]:
        show_trade_form_section(user_id, portfolio_id)
    
    with sub_tabs[2]:
        show_trade_history_section(user_id, portfolio_id)
    
    with sub_tabs[3]:
        show_rebalance_section(user_id, portfolio_id)
    
    with sub_tabs[4]:
        show_compare_with_famous(user_id, portfolio_id)


def show_holdings_section(user_id: int, portfolio_id: int):
    """보유 현황 섹션"""
    holdings = db.get_holdings(user_id, portfolio_id)
    
    if holdings:
        tickers = [h['ticker'] for h in holdings]
        prices = rebalance_calculator.get_multiple_prices(tickers)
        total_value, details = rebalance_calculator.calculate_portfolio_value(holdings, prices)
        
        total_cost = sum(d['cost'] for d in details.values())
        total_profit = total_value - total_cost
        profit_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💵 총 평가금액", f"${total_value:,.2f}")
        with col2:
            st.metric("💰 총 투자금액", f"${total_cost:,.2f}")
        with col3:
            st.metric("📈 총 수익", f"${total_profit:,.2f}", f"{profit_pct:+.2f}%")
        
        holdings_data = []
        for ticker, detail in details.items():
            holdings_data.append({
                "종목": ticker,
                "수량": detail['quantity'],
                "평균단가": f"${detail['avg_price']:.2f}",
                "현재가": f"${detail['current_price']:.2f}",
                "평가금액": f"${detail['value']:.2f}",
                "수익률": f"{detail['profit_loss_percent']:+.2f}%",
                "비중": f"{detail['percent']:.1f}%"
            })
        
        st.dataframe(pd.DataFrame(holdings_data), use_container_width=True, hide_index=True)
        
        fig = px.pie(
            values=[d['value'] for d in details.values()],
            names=list(details.keys()),
            title="포트폴리오 구성",
            hole=0.4
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📭 보유 종목이 없습니다. '매매 기록' 탭에서 거래를 추가하세요.")


def show_trade_form_section(user_id: int, portfolio_id: int):
    """매매 기록 추가 섹션"""
    col1, col2 = st.columns(2)
    
    with col1:
        ticker = st.text_input("종목 코드 (예: AAPL)", key="trade_ticker_sec").upper()
        trade_type = st.selectbox(
            "거래 유형", 
            ["buy", "sell"], 
            format_func=lambda x: "🟢 매수" if x == "buy" else "🔴 매도", 
            key="trade_type_sec"
        )
        quantity = st.number_input("수량", min_value=0.0, step=1.0, key="trade_qty_sec")
    
    with col2:
        live_price = None
        if ticker:
            try:
                live_price = rebalance_calculator.get_current_price(ticker)
                if live_price:
                    st.success(f"💹 {ticker} 현재가: ${live_price:.2f}")
            except:
                pass
        
        use_live = st.checkbox("현재가 사용", key="use_live_sec", value=bool(live_price))
        
        if use_live and live_price:
            price = live_price
            st.info(f"적용 가격: ${price:.2f}")
        else:
            price = st.number_input("거래 단가 ($)", min_value=0.0, step=0.01, key="trade_price_sec")
        
        trade_date = st.date_input("거래일", datetime.now(), key="trade_date_sec")
    
    notes = st.text_input("메모 (선택)", key="trade_notes_sec")
    
    if quantity > 0 and price > 0:
        st.markdown(f"**💰 예상 금액: ${quantity * price:,.2f}**")
    
    if st.button("💾 거래 저장", use_container_width=True, type="primary", key="save_trade_sec"):
        if ticker and quantity > 0 and price > 0:
            db.add_trade(
                user_id, portfolio_id, ticker, trade_type,
                quantity, price, trade_date.isoformat(), "USD", notes
            )
            st.success(f"✅ {ticker} {'매수' if trade_type == 'buy' else '매도'} 기록 저장됨!")
            st.rerun()
        else:
            st.warning("종목, 수량, 가격을 입력해주세요.")


def show_trade_history_section(user_id: int, portfolio_id: int):
    """거래 내역 섹션"""
    col1, col2 = st.columns(2)
    with col1:
        filter_ticker = st.text_input("종목 필터", key="filter_ticker_sec").upper()
    with col2:
        filter_type = st.selectbox("거래 유형", ["전체", "매수", "매도"], key="filter_type_sec")
    
    trades = db.get_trades(user_id, portfolio_id, ticker=filter_ticker if filter_ticker else None, limit=100)
    
    if filter_type != "전체":
        type_filter = "buy" if filter_type == "매수" else "sell"
        trades = [t for t in trades if t['trade_type'] == type_filter]
    
    if trades:
        total_buy = sum(t['total_amount'] for t in trades if t['trade_type'] == 'buy')
        total_sell = sum(t['total_amount'] for t in trades if t['trade_type'] == 'sell')
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("총 매수", f"${total_buy:,.2f}")
        with col2:
            st.metric("총 매도", f"${total_sell:,.2f}")
        with col3:
            st.metric("순 투자", f"${total_buy - total_sell:,.2f}")
        
        trades_data = [{
            "ID": t['id'], "날짜": t['trade_date'], "종목": t['ticker'],
            "유형": "🟢" if t['trade_type'] == 'buy' else "🔴",
            "수량": t['quantity'], "단가": f"${t['price']:.2f}",
            "금액": f"${t['total_amount']:.2f}", "메모": t['notes'] or "-"
        } for t in trades]
        
        st.dataframe(pd.DataFrame(trades_data), use_container_width=True, hide_index=True)
        
        with st.expander("🗑️ 기록 삭제"):
            delete_id = st.number_input("삭제할 ID", min_value=1, step=1, key="del_id_sec")
            if st.button("삭제", key="del_btn_sec"):
                db.delete_trade(delete_id)
                st.success("삭제됨")
                st.rerun()
    else:
        st.info("거래 기록이 없습니다.")


def show_rebalance_section(user_id: int, portfolio_id: int):
    """리밸런싱 섹션"""
    rebal_tabs = st.tabs(["📊 현재 vs 목표", "🎯 목표 설정", "📋 리밸런싱 계획"])
    
    with rebal_tabs[0]:
        show_current_vs_target(user_id, portfolio_id)
    
    with rebal_tabs[1]:
        show_target_allocation_settings(user_id, portfolio_id)
    
    with rebal_tabs[2]:
        show_rebalance_plan(user_id, portfolio_id)


def show_compare_with_famous(user_id: int, portfolio_id: int):
    """대가 포트폴리오와 비교"""
    from analyzers.portfolio_analyzer import PortfolioAnalyzer
    
    st.subheader("🔍 내 포트폴리오 vs 대가 포트폴리오")
    
    holdings = db.get_holdings(user_id, portfolio_id)
    
    if not holdings:
        st.info("보유 종목이 없습니다. 먼저 매매 기록을 추가하세요.")
        return
    
    # 현재 보유 비중 계산
    tickers = [h['ticker'] for h in holdings]
    prices = rebalance_calculator.get_multiple_prices(tickers)
    total_value, details = rebalance_calculator.calculate_portfolio_value(holdings, prices)
    
    my_allocation = {ticker: detail['percent'] for ticker, detail in details.items()}
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📊 내 포트폴리오**")
        fig = px.pie(values=list(my_allocation.values()), names=list(my_allocation.keys()), hole=0.4)
        fig.update_layout(height=300, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**📋 보유 종목 비중**")
        for ticker, pct in sorted(my_allocation.items(), key=lambda x: x[1], reverse=True):
            st.write(f"- **{ticker}**: {pct:.1f}%")
    
    if st.button("🔍 대가 포트폴리오와 비교", use_container_width=True):
        with st.spinner("비교 분석 중..."):
            try:
                comparison = st.session_state.analyzer.compare_portfolio(my_allocation)
                
                st.success("✅ 분석 완료!")
                
                # 비교 결과 표시
                comparison_data = comparison.get('comparison', {})
                famous = comparison_data.get('famous_portfolios', {})
                
                for name, data in famous.items():
                    info = data.get('info', {})
                    user_metrics = comparison_data.get('user_portfolio', {}).get('metrics', {})
                    famous_metrics = data.get('metrics', {})
                    
                    user_return = user_metrics.get('annual_return', 0)
                    famous_return = famous_metrics.get('annual_return', 0)
                    similarity = max(0, 100 - abs(user_return - famous_return) * 2) if user_return and famous_return else 0
                    
                    with st.expander(f"📌 {info.get('name', name)} (유사도: {similarity:.1f}%)"):
                        if user_metrics and famous_metrics:
                            metrics_df = pd.DataFrame({
                                "지표": ["연간 수익률", "변동성", "샤프 비율", "최대 낙폭"],
                                "내 포트폴리오": [
                                    f"{user_metrics.get('annual_return', 0):.2f}%",
                                    f"{user_metrics.get('volatility', 0):.2f}%",
                                    f"{user_metrics.get('sharpe_ratio', 0):.2f}",
                                    f"{user_metrics.get('max_drawdown', 0):.2f}%"
                                ],
                                info.get('name', name): [
                                    f"{famous_metrics.get('annual_return', 0):.2f}%",
                                    f"{famous_metrics.get('volatility', 0):.2f}%",
                                    f"{famous_metrics.get('sharpe_ratio', 0):.2f}",
                                    f"{famous_metrics.get('max_drawdown', 0):.2f}%"
                                ]
                            })
                            st.dataframe(metrics_df, use_container_width=True, hide_index=True)
                
            except Exception as e:
                st.error(f"비교 실패: {e}")


def show_famous_portfolios_section():
    """대가 포트폴리오 섹션"""
    from analyzers.portfolio_analyzer import PortfolioAnalyzer
    
    st.markdown("### 🏆 유명 투자자들의 검증된 포트폴리오")
    
    famous_portfolios = PortfolioAnalyzer.FAMOUS_PORTFOLIOS
    
    for portfolio_key, portfolio_data in famous_portfolios.items():
        with st.expander(f"📌 {portfolio_data['name']} - by {portfolio_data['creator']}", expanded=False):
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.markdown(f"**설명:** {portfolio_data['description']}")
                st.markdown("---")
                st.markdown("**📊 자산 배분 (ETF)**")
                
                allocation_data = [{"티커": t, "비중": f"{w}%"} 
                                   for t, w in portfolio_data['allocation'].items()]
                df = pd.DataFrame(allocation_data)
                st.dataframe(df, hide_index=True, use_container_width=True)
            
            with col2:
                fig = px.pie(
                    values=list(portfolio_data['allocation'].values()),
                    names=list(portfolio_data['allocation'].keys()),
                    title=f"{portfolio_data['name']} 배분",
                    hole=0.4
                )
                fig.update_layout(height=300, showlegend=True)
                st.plotly_chart(fig, use_container_width=True)
            
            cat_allocation = portfolio_data.get('category_allocation', {})
            if cat_allocation:
                st.markdown("**📈 카테고리별 배분**")
                cat_cols = st.columns(len(cat_allocation))
                for i, (cat, weight) in enumerate(cat_allocation.items()):
                    with cat_cols[i]:
                        st.metric(cat, f"{weight}%")


def show_style_portfolios_section():
    """투자 스타일별 포트폴리오 섹션"""
    style_tabs = st.tabs([
        "🚀 성장형", "💰 배당형", "⚖️ 균형형", 
        "🔥 공격형", "🛡️ 안정형", "🌱 ESG", "💻 테크"
    ])
    
    style_mapping = ["growth", "dividend", "balanced", "aggressive", "conservative", "esg", "tech_focused"]
    
    for tab, style_key in zip(style_tabs, style_mapping):
        with tab:
            show_portfolio_detail(style_key)


def show_manual_portfolio_comparison():
    """직접 입력 포트폴리오 비교 (비로그인 시)"""
    st.markdown("### 📝 내 포트폴리오 입력")
    st.info("💡 로그인하면 보유 종목을 자동으로 관리할 수 있습니다.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**예시:** `SPY:40, QQQ:30, TLT:20, GLD:10`")
        portfolio_input = st.text_area(
            "포트폴리오 입력 (티커:비중%)",
            value="SPY:40\nQQQ:30\nTLT:20\nGLD:10",
            height=150,
            key="manual_pf_input"
        )
    
    with col2:
        holdings = {}
        for line in portfolio_input.strip().split("\n"):
            if ":" in line:
                parts = line.replace(",", "").split(":")
                if len(parts) == 2:
                    ticker = parts[0].strip().upper()
                    try:
                        weight = float(parts[1].strip())
                        holdings[ticker] = weight
                    except:
                        pass
        
        if holdings:
            fig = px.pie(values=list(holdings.values()), names=list(holdings.keys()), title="미리보기", hole=0.4)
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
    
    if st.button("🔍 대가 포트폴리오와 비교", use_container_width=True, key="compare_manual"):
        if holdings:
            with st.spinner("비교 분석 중..."):
                try:
                    comparison = st.session_state.analyzer.compare_portfolio(holdings)
                    st.success("✅ 분석 완료!")
                    
                    comparison_data = comparison.get('comparison', {})
                    famous = comparison_data.get('famous_portfolios', {})
                    
                    for name, data in famous.items():
                        info = data.get('info', {})
                        with st.expander(f"📌 {info.get('name', name)}"):
                            st.write(f"**설명:** {info.get('description', 'N/A')}")
                            st.write(f"**창시자:** {info.get('creator', 'N/A')}")
                except Exception as e:
                    st.error(f"비교 실패: {e}")
        else:
            st.warning("포트폴리오를 입력해주세요.")


# ============================================================
# 추천 포트폴리오 상세 (기존 함수 유지)
# ============================================================
def show_recommended_portfolios_page():
    """투자 스타일별 추천 포트폴리오 페이지"""
    
    st.header("💼 투자 스타일별 추천 포트폴리오")
    st.markdown("*투자 성향에 맞는 최적의 포트폴리오를 확인하세요*")
    
    # 포트폴리오 스타일 탭
    tabs = st.tabs([
        "🚀 성장형", "💰 배당형", "⚖️ 균형형", 
        "🔥 공격형", "🛡️ 안정형", "🌱 ESG", "💻 테크 집중"
    ])
    
    style_mapping = ["growth", "dividend", "balanced", "aggressive", "conservative", "esg", "tech_focused"]
    
    for tab, style_key in zip(tabs, style_mapping):
        with tab:
            show_portfolio_detail(style_key)


def show_portfolio_detail(style_key):
    """포트폴리오 상세 정보 표시"""
    portfolio = RECOMMENDED_PORTFOLIOS.get(style_key, {})
    
    if not portfolio:
        st.warning("포트폴리오 데이터가 없습니다.")
        return
    
    st.subheader(portfolio['name'])
    st.write(portfolio['description'])
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📌 포트폴리오 특성")
        
        # 위험 수준에 따른 색상
        risk_colors = {
            "낮음": "🟢", "중간": "🟡", "중상": "🟠", "높음": "🔴", "매우 높음": "🔴"
        }
        risk_icon = risk_colors.get(portfolio.get('risk_level', ''), "⚪")
        
        st.markdown(f"**위험 수준:** {risk_icon} {portfolio.get('risk_level', 'N/A')}")
        st.markdown(f"**적합 대상:** {portfolio.get('suitable_for', 'N/A')}")
        st.markdown(f"**투자 기간:** {portfolio.get('time_horizon', 'N/A')}")
        st.markdown(f"**예상 수익률:** {portfolio.get('expected_return', 'N/A')}")
        st.markdown(f"**예상 변동성:** {portfolio.get('expected_volatility', 'N/A')}")
        
        if portfolio.get('expected_yield'):
            st.markdown(f"**예상 배당수익률:** {portfolio['expected_yield']}")
        
        if portfolio.get('warning'):
            st.warning(f"⚠️ {portfolio['warning']}")
    
    with col2:
        # 파이 차트
        allocation = portfolio.get('allocation', {})
        if allocation:
            fig = px.pie(
                values=[v['weight'] for v in allocation.values()],
                names=[f"{k} ({v['weight']}%)" for k, v in allocation.items()],
                title="자산 배분",
                hole=0.35,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
    
    # 구성 상세 테이블
    st.divider()
    st.markdown("### 📋 포트폴리오 구성 상세")
    
    data = []
    for ticker, info in allocation.items():
        data.append({
            "티커": ticker,
            "종목명": info['name'],
            "비중": f"{info['weight']}%",
            "유형": info['type'],
            "설명": info['description']
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # 핵심 종목 분석
    st.divider()
    st.markdown("### 🔑 핵심 보유 종목")
    key_stocks = portfolio.get('key_stocks', [])
    st.write(", ".join(key_stocks))
    
    # 핵심 종목 분석 버튼
    if st.button(f"🔍 핵심 종목 분석", key=f"analyze_key_{style_key}"):
        run_batch_analysis(key_stocks)


# ============================================================
# 섹터별 대표 종목 페이지 (신규)
# ============================================================
def show_sector_representatives_page():
    """섹터별 대표 주식 & ETF 페이지"""
    
    st.header("🏭 섹터별 대표 주식 & ETF")
    st.markdown("*각 섹터의 대표 주식과 ETF를 확인하세요 (규모/보수율 포함)*")
    
    # 섹터 선택
    sector = st.selectbox(
        "섹터 선택",
        list(SECTOR_REPRESENTATIVES.keys()),
        format_func=lambda x: f"{x} - {SECTOR_REPRESENTATIVES[x]['name']}"
    )
    
    sector_data = SECTOR_REPRESENTATIVES[sector]
    
    st.subheader(f"{sector} ({sector_data['name']})")
    st.info(sector_data['description'])
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 대표 주식
        st.markdown("### 📈 대표 주식")
        
        stocks_data = []
        for stock in sector_data['stocks']:
            stocks_data.append({
                "티커": stock['ticker'],
                "종목명": stock['name'],
                "설명": stock['description']
            })
        
        st.dataframe(pd.DataFrame(stocks_data), use_container_width=True, hide_index=True)
    
    with col2:
        # 대표 ETF
        st.markdown("### 📊 대표 ETF")
        
        etfs_data = []
        for etf in sector_data['etfs']:
            etfs_data.append({
                "티커": etf['ticker'],
                "ETF명": etf['name'],
                "보수율": f"{etf['expense_ratio']}%",
                "운용규모": etf['aum'],
            })
        
        st.dataframe(pd.DataFrame(etfs_data), use_container_width=True, hide_index=True)
    
    # ETF 상세 정보
    st.divider()
    st.markdown("### 📋 ETF 상세 정보")
    
    for etf in sector_data['etfs']:
        with st.expander(f"**{etf['ticker']}** - {etf['name']}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("보수율", f"{etf['expense_ratio']}%")
            with col2:
                st.metric("운용 규모", etf['aum'])
            with col3:
                st.write("")
            st.write(f"**설명:** {etf['description']}")
    
    # 선택 종목 분석
    st.divider()
    st.markdown("### 🔍 종목 분석")
    
    all_tickers = [s['ticker'] for s in sector_data['stocks']] + [e['ticker'] for e in sector_data['etfs']]
    
    selected_tickers = st.multiselect(
        "분석할 종목 선택",
        all_tickers,
        default=[]
    )
    
    if st.button("🔍 선택 종목 분석", use_container_width=True) and selected_tickers:
        run_batch_analysis(selected_tickers)
    
    # 전체 섹터 비교
    st.divider()
    st.markdown("### 📊 전체 섹터 ETF 비교")
    
    if st.button("📊 전체 섹터 대표 ETF 비교"):
        show_all_sector_etfs_comparison()


def show_all_sector_etfs_comparison():
    """전체 섹터 대표 ETF 비교"""
    data = []
    
    for sector_name, sector_data in SECTOR_REPRESENTATIVES.items():
        # 각 섹터의 첫 번째 ETF만 사용
        if sector_data['etfs']:
            etf = sector_data['etfs'][0]
            data.append({
                "섹터": sector_name,
                "대표 ETF": etf['ticker'],
                "ETF명": etf['name'],
                "보수율": f"{etf['expense_ratio']}%",
                "운용규모": etf['aum']
            })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # 보수율 차트
    expense_data = []
    for sector_name, sector_data in SECTOR_REPRESENTATIVES.items():
        if sector_data['etfs']:
            etf = sector_data['etfs'][0]
            expense_data.append({
                "섹터": sector_name,
                "보수율": etf['expense_ratio']
            })
    
    fig = px.bar(
        expense_data,
        x="섹터",
        y="보수율",
        title="섹터별 대표 ETF 보수율 비교",
        color="보수율",
        color_continuous_scale="RdYlGn_r"
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)


def show_news_page():
    """뉴스 페이지 - 다중 소스 통합"""
    
    st.header("📰 시장 뉴스")
    st.caption("NewsAPI, Alpha Vantage, Finnhub, Marketaux, Yahoo Finance 통합")
    
    if st.button("🔄 뉴스 새로고침", use_container_width=True):
        st.session_state.pop('news_data', None)
        st.rerun()
    
    # 캐시된 뉴스 또는 새로 로드
    if 'news_data' not in st.session_state:
        with st.spinner("📰 뉴스 수집 중... (여러 소스에서 수집)"):
            try:
                st.session_state.news_data = st.session_state.analyzer.get_news_summary()
            except Exception as e:
                st.error(f"뉴스 수집 실패: {e}")
                st.session_state.news_data = {}
    
    news = st.session_state.news_data
    
    if not news:
        st.warning("뉴스 데이터를 불러올 수 없습니다. API 키를 확인해주세요.")
        return
    
    # 탭으로 구분
    tab1, tab2 = st.tabs(["📊 시장 뉴스", "📈 경제 뉴스"])
    
    with tab1:
        st.subheader("📊 시장 뉴스")
        
        market_data = news.get('market_news', {})
        market_articles = market_data.get('articles', [])
        market_sentiment = market_data.get('sentiment', {})
        
        # 감성 분석 요약
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            sentiment_label = market_sentiment.get('sentiment', 'N/A')
            emoji = "🟢" if sentiment_label == "positive" else "🔴" if sentiment_label == "negative" else "⚪"
            st.metric("전반적 감성", f"{emoji} {sentiment_label}")
        with col2:
            st.metric("감성 점수", f"{market_sentiment.get('score', 0):.2f}")
        with col3:
            st.metric("긍정 신호", market_sentiment.get('positive_signals', 0))
        with col4:
            st.metric("부정 신호", market_sentiment.get('negative_signals', 0))
        
        st.divider()
        
        # 뉴스 목록
        if market_articles:
            st.caption(f"총 {len(market_articles)}개 기사")
            
            for article in market_articles[:15]:
                with st.container():
                    # 소스 타입에 따른 아이콘
                    source_type = article.get('type', 'unknown')
                    source_icons = {
                        'alphavantage_news': '📈',
                        'finnhub_news': '💹',
                        'marketaux_news': '📰',
                        'market_news': '🔵',
                        'newsapi': '📋'
                    }
                    icon = source_icons.get(source_type, '📄')
                    
                    # Alpha Vantage 감성 표시
                    av_sentiment = article.get('sentiment', {})
                    sentiment_badge = ""
                    if av_sentiment:
                        label = av_sentiment.get('label', '')
                        if 'Bullish' in label:
                            sentiment_badge = "🟢"
                        elif 'Bearish' in label:
                            sentiment_badge = "🔴"
                        else:
                            sentiment_badge = "⚪"
                    
                    st.markdown(f"### {icon} {article.get('title', 'N/A')} {sentiment_badge}")
                    
                    # 메타 정보
                    source = article.get('source', 'Unknown')
                    published = article.get('published', '')[:16] if article.get('published') else ''
                    st.caption(f"📌 {source} | 🕐 {published} | 🏷️ {source_type}")
                    
                    # 요약
                    summary = article.get('summary', '')
                    if summary:
                        st.write(summary[:300] + "..." if len(summary) > 300 else summary)
                    
                    # 링크
                    if article.get('url'):
                        st.link_button("🔗 기사 보기", article['url'])
                    
                    st.divider()
        else:
            st.info("시장 뉴스가 없습니다.")
    
    with tab2:
        st.subheader("📈 경제 뉴스")
        
        economic_data = news.get('economic_news', {})
        economic_articles = economic_data.get('articles', [])
        economic_sentiment = economic_data.get('sentiment', {})
        
        # 감성 분석 요약
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            sentiment_label = economic_sentiment.get('sentiment', 'N/A')
            emoji = "🟢" if sentiment_label == "positive" else "🔴" if sentiment_label == "negative" else "⚪"
            st.metric("전반적 감성", f"{emoji} {sentiment_label}")
        with col2:
            st.metric("감성 점수", f"{economic_sentiment.get('score', 0):.2f}")
        with col3:
            st.metric("긍정 신호", economic_sentiment.get('positive_signals', 0))
        with col4:
            st.metric("부정 신호", economic_sentiment.get('negative_signals', 0))
        
        st.divider()
        
        # 뉴스 목록
        if economic_articles:
            st.caption(f"총 {len(economic_articles)}개 기사")
            
            for article in economic_articles[:10]:
                with st.container():
                    st.markdown(f"### 📈 {article.get('title', 'N/A')}")
                    
                    source = article.get('source', 'Unknown')
                    published = article.get('published', '')[:16] if article.get('published') else ''
                    st.caption(f"📌 {source} | 🕐 {published}")
                    
                    summary = article.get('summary', '')
                    if summary:
                        st.write(summary[:300] + "..." if len(summary) > 300 else summary)
                    
                    if article.get('url'):
                        st.link_button("🔗 기사 보기", article['url'])
                    
                    st.divider()
        else:
            st.info("경제 뉴스가 없습니다.")
    
    # API 상태 표시
    with st.expander("🔧 뉴스 API 상태", expanded=False):
        from data_collectors.news_collector import NewsCollector
        collector = NewsCollector()
        
        api_status = {
            "NewsAPI": "✅ 설정됨" if collector.news_api_key else "❌ 미설정",
            "Alpha Vantage": "✅ 설정됨" if collector.alpha_vantage_key else "❌ 미설정",
            "Finnhub": "✅ 설정됨" if collector.finnhub_key else "❌ 미설정 (선택)",
            "Marketaux": "✅ 설정됨" if collector.marketaux_key else "❌ 미설정 (선택)",
        }
        
        for api, status in api_status.items():
            st.write(f"- **{api}**: {status}")
        
        st.caption("💡 Alpha Vantage는 분당 5회 요청 제한이 있습니다.")


def show_ai_analysis_page():
    """AI 분석 페이지 (분야별 다른 AI 지원)"""
    
    st.header("🤖 AI 분석")
    st.markdown("*분석 분야별로 다른 AI를 선택할 수 있습니다*")
    
    # AI 제공자별 설정
    st.markdown("### ⚙️ 분석별 AI 설정")
    
    col1, col2, col3 = st.columns(3)
    
    ai_options = ["grok", "gemini", "openai", "anthropic", "github"]
    
    with col1:
        market_ai = st.selectbox("시장 분석 AI", ai_options, index=0, key="market_ai_select")
    
    with col2:
        stock_ai = st.selectbox("주식 분석 AI", ai_options, index=0, key="stock_ai_select")
    
    with col3:
        portfolio_ai = st.selectbox("포트폴리오 AI", ai_options, index=0, key="portfolio_ai_select")
    
    st.divider()
    
    tab1, tab2, tab3 = st.tabs(["📊 시장 분석", "📈 주식 분석", "💼 포트폴리오"])
    
    with tab1:
        st.subheader("📊 AI 시장 분석")
        st.caption(f"사용 AI: **{market_ai}**")
        
        include_news = st.checkbox("뉴스 분석 포함", value=True)
        
        if st.button("🤖 AI 시장 분석 실행", key="market_ai_btn"):
            # 선택된 AI로 분석기 생성
            from main import StockAnalyzer
            analyzer = StockAnalyzer(ai_provider=market_ai)
            
            with st.spinner(f"{market_ai}가 시장을 분석 중입니다..."):
                try:
                    analysis = analyzer.get_ai_market_analysis(include_news=include_news)
                    st.markdown(analysis)
                except Exception as e:
                    st.error(f"AI 분석 실패: {e}")
                    st.info(f"💡 .env 파일에 {market_ai.upper()}_API_KEY를 설정해주세요.")
    
    with tab2:
        st.subheader("📈 AI 주식 분석")
        st.caption(f"사용 AI: **{stock_ai}**")
        
        ticker = st.text_input("분석할 티커", value="AAPL", key="ai_ticker_input")
        
        if st.button("🤖 AI 주식 분석 실행", key="stock_ai_btn"):
            from main import StockAnalyzer
            analyzer = StockAnalyzer(ai_provider=stock_ai)
            
            with st.spinner(f"{stock_ai}가 {ticker.upper()}를 분석 중..."):
                try:
                    analysis = analyzer.get_ai_stock_analysis(ticker.upper())
                    st.markdown(analysis)
                except Exception as e:
                    st.error(f"AI 분석 실패: {e}")
    
    with tab3:
        st.subheader(" AI 포트폴리오 분석")
        st.caption(f"사용 AI: **{portfolio_ai}**")
        
        portfolio_input = st.text_input(
            "포트폴리오 (예: SPY:40,QQQ:30,TLT:30)", 
            value="SPY:40,QQQ:30,TLT:20,GLD:10",
            key="ai_portfolio_input"
        )
        
        if st.button("🤖 AI 포트폴리오 분석", key="portfolio_ai_btn"):
            # 파싱
            holdings = {}
            for item in portfolio_input.split(","):
                if ":" in item:
                    parts = item.strip().split(":")
                    if len(parts) == 2:
                        try:
                            holdings[parts[0].upper()] = float(parts[1])
                        except:
                            pass
            
            if holdings:
                from main import StockAnalyzer
                analyzer = StockAnalyzer(ai_provider=portfolio_ai)
                
                with st.spinner(f"{portfolio_ai}가 포트폴리오를 분석 중..."):
                    try:
                        analysis = analyzer.get_ai_portfolio_analysis(holdings)
                        st.markdown(analysis)
                    except Exception as e:
                        st.error(f"AI 분석 실패: {e}")
            else:
                st.warning("올바른 포트폴리오 형식을 입력하세요.")


# ============================================================
# AI 토론 페이지 (신규) - Gemini vs Grok
# ============================================================
def show_ai_debate_page():
    """AI 토론 페이지 - Gemini와 Grok이 서로 분석하고 평가"""
    
    st.header("🎭 AI 토론: Gemini vs Grok")
    st.markdown("""
    *두 AI가 서로의 분석을 비평하고 수정하면서 더 나은 결론에 도달합니다*
    
    **토론 진행 방식:**
    1. 🔵 **1차 AI**가 초기 분석 수행
    2. 🟠 **2차 AI**가 분석을 비평하고 문제점 지적
    3. 🔵 **1차 AI**가 비평을 반영하여 수정
    4. 🟠 **2차 AI**가 수정된 분석 평가
    5. 역할을 교체하며 반복 (최대 3라운드)
    6. 📋 최종 종합 보고서 생성
    """)
    
    st.divider()
    
    # AI 설정
    col1, col2, col3 = st.columns(3)
    
    all_ai_options = ["gemini", "grok", "openai", "anthropic", "github"]
    
    with col1:
        primary_ai = st.selectbox(
            "1차 분석 AI",
            all_ai_options,
            index=0,
            key="debate_primary_ai",
            help="github: GPT-4o, Llama, Mistral, Phi 등"
        )
    
    with col2:
        secondary_ai = st.selectbox(
            "2차 비평 AI",
            all_ai_options,
            index=1,
            key="debate_secondary_ai",
            help="github: GPT-4o, Llama, Mistral, Phi 등"
        )
    
    with col3:
        max_rounds = st.slider("최대 토론 라운드", 1, 5, 3, key="debate_max_rounds")
    
    if primary_ai == secondary_ai:
        st.warning("⚠️ 서로 다른 AI를 선택해주세요!")
        return
    
    st.divider()
    
    # 토론 유형 선택
    debate_type = st.radio(
        "토론 주제 선택",
        ["📊 시장 분석 토론", "📈 개별 주식 분석 토론"],
        horizontal=True
    )
    
    if debate_type == "📊 시장 분석 토론":
        show_market_debate(primary_ai, secondary_ai, max_rounds)
    else:
        show_stock_debate(primary_ai, secondary_ai, max_rounds)


def show_market_debate(primary_ai: str, secondary_ai: str, max_rounds: int):
    """시장 분석 토론"""
    
    st.subheader("📊 시장 분석 토론")
    
    if st.button("🚀 시장 분석 토론 시작", use_container_width=True, key="start_market_debate"):
        run_market_debate_ui(primary_ai, secondary_ai, max_rounds)


def show_stock_debate(primary_ai: str, secondary_ai: str, max_rounds: int):
    """주식 분석 토론"""
    
    st.subheader("📈 개별 주식 분석 토론")
    
    ticker = st.text_input("분석할 티커", value="NVDA", key="debate_ticker")
    
    if st.button("🚀 주식 분석 토론 시작", use_container_width=True, key="start_stock_debate"):
        if ticker:
            run_stock_debate_ui(ticker.upper(), primary_ai, secondary_ai, max_rounds)
        else:
            st.warning("티커를 입력해주세요.")


def run_market_debate_ui(primary_ai: str, secondary_ai: str, max_rounds: int):
    """시장 분석 토론 UI 실행"""
    from ai_providers.ai_debate import AIDebateSystem
    
    # 시장 데이터 수집
    with st.spinner("📊 시장 데이터 수집 중..."):
        market_data = get_market_data()
    
    # 토론 시스템 초기화
    debate_system = AIDebateSystem(primary_ai=primary_ai, secondary_ai=secondary_ai)
    
    # 결과 컨테이너
    initial_container = st.container()
    rounds_container = st.container()
    final_container = st.container()
    
    # 토론 실행
    current_round = 0
    
    for result in debate_system.run_market_debate(market_data, max_rounds=max_rounds):
        stage = result.get('stage', '')
        status = result.get('status', '')
        ai = result.get('ai', '')
        content = result.get('content', '')
        
        # 초기 분석
        if stage == "initial_analysis":
            with initial_container:
                if status == "시작":
                    st.info(f"🔵 **{ai.upper()}**가 초기 분석을 시작합니다...")
                elif status == "완료":
                    with st.expander(f"📊 초기 분석 ({ai.upper()})", expanded=True):
                        st.markdown(content)
        
        # 토론 라운드
        elif "round_" in stage:
            with rounds_container:
                # 라운드 시작
                if "critique" in stage and status == "비평 중":
                    round_num = stage.split("_")[1]
                    if int(round_num) > current_round:
                        current_round = int(round_num)
                        st.markdown(f"---\n### 🔄 라운드 {round_num}")
                    st.info(f"🟠 **{ai.upper()}**가 비평 중...")
                
                elif "critique" in stage and status == "완료":
                    with st.expander(f"🔍 비평 ({ai.upper()})", expanded=True):
                        st.markdown(content)
                
                elif "revision" in stage and status == "수정 중":
                    st.info(f"🔵 **{ai.upper()}**가 수정 중...")
                
                elif "revision" in stage and status == "완료":
                    with st.expander(f"✏️ 수정된 분석 ({ai.upper()})", expanded=True):
                        st.markdown(content)
                
                elif "evaluation" in stage and status == "평가 중":
                    st.info(f"🟠 **{ai.upper()}**가 평가 중...")
                
                elif "evaluation" in stage and status == "완료":
                    agreement_score = result.get('agreement_score', 0)
                    with st.expander(f"📋 평가 ({ai.upper()}) - 합의 점수: {agreement_score:.0f}점", expanded=False):
                        st.markdown(content)
                    
                    # 합의 점수 프로그레스 바
                    st.progress(agreement_score / 100)
                    if agreement_score >= 85:
                        st.success(f"✅ 높은 합의 달성! ({agreement_score:.0f}점)")
        
        # 합의 도달
        elif stage == "consensus_reached":
            with rounds_container:
                st.success(f"🎉 합의 도달! (점수: {result.get('score', 0):.0f}점)")
        
        # 최종 종합
        elif stage == "final_synthesis":
            with final_container:
                if status == "종합 중":
                    st.info("📋 최종 종합 보고서 작성 중...")
                elif status == "완료":
                    st.markdown("---\n## 📋 최종 종합 보고서")
                    st.success(f"✅ 총 {result.get('total_rounds', 0)} 라운드의 토론 완료")
                    st.markdown(content)


def run_stock_debate_ui(ticker: str, primary_ai: str, secondary_ai: str, max_rounds: int):
    """주식 분석 토론 UI 실행"""
    from ai_providers.ai_debate import AIDebateSystem
    
    # 주식 데이터 수집
    with st.spinner(f"📊 {ticker} 데이터 수집 중..."):
        try:
            stock_data = st.session_state.analyzer.analyze_stock(ticker)
        except Exception as e:
            st.error(f"주식 데이터 수집 실패: {e}")
            return
    
    # 기본 정보 표시
    val = stock_data.get('valuation', {})
    st.info(f"**{val.get('name', ticker)}** | 현재가: ${val.get('current_price', 0):,.2f} | PER: {val.get('trailing_pe', 'N/A')}")
    
    # 토론 시스템 초기화
    debate_system = AIDebateSystem(primary_ai=primary_ai, secondary_ai=secondary_ai)
    
    # 결과 컨테이너
    initial_container = st.container()
    rounds_container = st.container()
    final_container = st.container()
    
    # 토론 실행
    current_round = 0
    
    for result in debate_system.run_stock_debate(ticker, stock_data, max_rounds=max_rounds):
        stage = result.get('stage', '')
        status = result.get('status', '')
        ai = result.get('ai', '')
        content = result.get('content', '')
        
        # 초기 분석
        if stage == "initial_analysis":
            with initial_container:
                if status == "시작":
                    st.info(f"🔵 **{ai.upper()}**가 {ticker} 초기 분석을 시작합니다...")
                elif status == "완료":
                    with st.expander(f"📊 초기 분석 ({ai.upper()})", expanded=True):
                        st.markdown(content)
        
        # 토론 라운드
        elif "round_" in stage:
            with rounds_container:
                if "critique" in stage and status == "비평 중":
                    round_num = stage.split("_")[1]
                    if int(round_num) > current_round:
                        current_round = int(round_num)
                        st.markdown(f"---\n### 🔄 라운드 {round_num}")
                    st.info(f"🟠 **{ai.upper()}**가 비평 중...")
                
                elif "critique" in stage and status == "완료":
                    with st.expander(f"🔍 비평 ({ai.upper()})", expanded=True):
                        st.markdown(content)
                
                elif "revision" in stage and status == "수정 중":
                    st.info(f"🔵 **{ai.upper()}**가 수정 중...")
                
                elif "revision" in stage and status == "완료":
                    with st.expander(f"✏️ 수정된 분석 ({ai.upper()})", expanded=True):
                        st.markdown(content)
                
                elif "evaluation" in stage and status == "평가 중":
                    st.info(f"🟠 **{ai.upper()}**가 평가 중...")
                
                elif "evaluation" in stage and status == "완료":
                    agreement_score = result.get('agreement_score', 0)
                    with st.expander(f"📋 평가 ({ai.upper()}) - 합의 점수: {agreement_score:.0f}점", expanded=False):
                        st.markdown(content)
                    
                    st.progress(agreement_score / 100)
                    if agreement_score >= 85:
                        st.success(f"✅ 높은 합의 달성! ({agreement_score:.0f}점)")
        
        # 합의 도달
        elif stage == "consensus_reached":
            with rounds_container:
                st.success(f"🎉 합의 도달! (점수: {result.get('score', 0):.0f}점)")
        
        # 최종 종합
        elif stage == "final_synthesis":
            with final_container:
                if status == "종합 중":
                    st.info("📋 최종 종합 보고서 작성 중...")
                elif status == "완료":
                    st.markdown(f"---\n## 📋 {ticker} 최종 종합 보고서")
                    st.success(f"✅ 총 {result.get('total_rounds', 0)} 라운드의 토론 완료")
                    st.markdown(content)


# =====================================================
# 🏆 AI 팀 토론 페이지 v2
# =====================================================

def show_team_debate_page():
    """AI 팀 토론 페이지 - 사용자 정의 팀 구성"""
    
    st.header("🏆 AI 팀 토론")
    
    st.markdown("""
    **팀 기반 AI 토론 시스템 v2**
    
    - 🎯 **GitHub Models 우선 사용** (무료), 실패 시 자체 API로 fallback
    - 👥 **팀 개수 자유 설정** (2~5팀)
    - 🎨 **팀 구성 직접 선택** (팀장/팀원 모델)
    
    **토론 진행 방식:**
    
    | Phase | 단계 | 설명 |
    |-------|------|-----|
    | **Phase 1** | 팀 내부 작업 | 팀원이 분석 → 팀장이 검토/피드백 → 수정 반복 → **팀장 승인** |
    | **Phase 2** | 팀별 발표 | 모든 팀 승인 후, 각 팀장이 분석 결과 발표 |
    | **Phase 3** | 팀간 토론 | 주장 → 반박 → 최종 방어 |
    | **Phase 4** | QA 평가 | 심판이 종합 평가 및 최종 투자 권고 |
    """)
    
    st.divider()
    
    # 모듈 import
    try:
        from ai_providers.team_debate import (
            AITeamDebateSystem, GITHUB_MODELS, GITHUB_MODELS_BY_TIER,
            get_all_github_models, get_github_models_by_tier, create_team
        )
    except ImportError as e:
        st.error(f"팀 토론 모듈 로드 실패: {e}")
        return
    
    # GitHub Models 목록
    all_models = list(GITHUB_MODELS.keys())
    premium_models = GITHUB_MODELS_BY_TIER["premium"]
    standard_models = GITHUB_MODELS_BY_TIER["standard"]
    light_models = GITHUB_MODELS_BY_TIER["light"]
    
    # 팀 개수 선택
    st.subheader("1️⃣ 팀 개수 설정")
    num_teams = st.slider("참가 팀 수", 2, 5, 2, key="num_teams")
    
    st.divider()
    
    # 팀 구성 UI
    st.subheader("2️⃣ 팀 구성")
    
    teams = []
    team_colors = ["🔵", "🟢", "🟠", "🟣", "🔴"]
    team_color_codes = ["blue", "green", "orange", "purple", "red"]
    
    # 모델 선택 옵션 (티어별 그룹화)
    def format_model(model):
        if model in premium_models:
            return f"⭐ {model} (Premium)"
        elif model in standard_models:
            return f"📦 {model} (Standard)"
        else:
            return f"🪶 {model} (Light)"
    
    cols = st.columns(min(num_teams, 3))
    
    for i in range(num_teams):
        col_idx = i % len(cols)
        with cols[col_idx]:
            st.markdown(f"### {team_colors[i]} 팀 {i+1}")
            
            team_name = st.text_input(
                "팀 이름", 
                f"{team_colors[i]} Team {i+1}",
                key=f"team_name_{i}"
            )
            
            # 팀장 모델 (Premium 추천)
            st.markdown("**👔 팀장** (고급 모델 추천)")
            leader_model = st.selectbox(
                "팀장 모델",
                all_models,
                index=all_models.index(premium_models[i % len(premium_models)]) if premium_models[i % len(premium_models)] in all_models else 0,
                format_func=format_model,
                key=f"leader_{i}"
            )
            
            # 팀원 모델 (Standard/Light 추천)
            st.markdown("**👤 팀원** (경량 모델 추천)")
            member_model = st.selectbox(
                "팀원 모델",
                all_models,
                index=all_models.index(standard_models[i % len(standard_models)]) if standard_models[i % len(standard_models)] in all_models else 0,
                format_func=format_model,
                key=f"member_{i}"
            )
            
            teams.append(create_team(team_name, leader_model, member_model, team_color_codes[i]))
            
            st.info(f"팀장: `{leader_model}`\n팀원: `{member_model}`")
    
    st.divider()
    
    # QA 심판 설정
    st.subheader("3️⃣ QA 심판 설정")
    qa_model = st.selectbox(
        "QA 심판 모델",
        all_models,
        index=all_models.index("gpt-4o") if "gpt-4o" in all_models else 0,
        format_func=format_model,
        key="qa_model"
    )
    st.success(f"🏛️ QA 심판: `{qa_model}`")
    
    st.divider()
    
    # 토론 설정
    st.subheader("4️⃣ 토론 설정")
    col1, col2 = st.columns(2)
    
    with col1:
        max_revisions = st.slider(
            "팀 내부 최대 수정 횟수",
            1, 5, 2,
            key="max_revisions",
            help="팀장이 팀원에게 수정을 요청할 수 있는 최대 횟수"
        )
    
    with col2:
        analysis_task = st.text_area(
            "분석 과제",
            "현재 시장 상황을 분석하고 향후 3개월 투자 전략을 제시하세요.",
            key="analysis_task"
        )
    
    st.divider()
    
    # 팀 구성 요약
    st.subheader("📋 팀 구성 요약")
    
    summary_data = []
    for i, team in enumerate(teams):
        summary_data.append({
            "팀": team.name,
            "팀장 모델": team.leader_model,
            "팀원 모델": team.member_model
        })
    
    st.table(summary_data)
    
    # 토론 시작/중단 버튼
    col_start, col_stop = st.columns([3, 1])
    with col_start:
        if st.button("🚀 팀 토론 시작!", type="primary", use_container_width=True):
            st.session_state.team_debate_running = True
            st.session_state.team_debate_stop_requested = False
            run_team_debate_v2(teams, qa_model, max_revisions, analysis_task)
    
    with col_stop:
        if st.button("🛑 강제 중단", type="secondary", use_container_width=True, 
                     disabled=not st.session_state.get('team_debate_running', False)):
            st.session_state.team_debate_stop_requested = True
            st.warning("⚠️ 중단 요청됨. 현재 단계 완료 후 중단됩니다...")


def run_team_debate_v2(teams, qa_model: str, max_revisions: int, analysis_task: str):
    """팀 토론 실행 v2 - 개선된 플로우"""
    
    from ai_providers.team_debate import AITeamDebateSystem
    
    # 중단 체크 헬퍼 함수
    def check_stop_requested():
        return st.session_state.get('team_debate_stop_requested', False)
    
    try:
        # 시장 데이터 로드
        market_data = get_market_data()
        economic_cycle = get_economic_cycle()
        
        combined_data = {
            "market": market_data,
            "economic_cycle": economic_cycle,
            "timestamp": datetime.now().isoformat()
        }
        
        # 토론 시스템 초기화
        st.info("🔄 AI 클라이언트 초기화 중...")
        debate_system = AITeamDebateSystem(teams, qa_model)
        
        # 참가 불가 팀 표시
        if debate_system.unavailable_info:
            st.warning("⚠️ 일부 팀 참가 불가:\n" + "\n".join(debate_system.unavailable_info))
        
        # 강제 중단 버튼 (실시간)
        stop_placeholder = st.empty()
        
        # Phase 진행률 표시
        st.markdown("### 📋 토론 진행 상황")
        phases = ["Phase 1: 팀 내부 작업", "Phase 2: 팀별 발표", "Phase 3: 팀간 토론", "Phase 4: QA 평가"]
        phase_cols = st.columns(4)
        phase_placeholders = {}
        for i, (col, phase) in enumerate(zip(phase_cols, phases)):
            with col:
                phase_placeholders[i+1] = st.empty()
                phase_placeholders[i+1].markdown(f"⬜ {phase}")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 실시간 중단 버튼 표시
        with stop_placeholder.container():
            if st.button("🛑 토론 강제 중단", key="stop_during_debate", type="secondary"):
                st.session_state.team_debate_stop_requested = True
                st.warning("⚠️ 중단 요청됨...")
        
        st.divider()
        
        # 팀별 작업 컨테이너 (Phase 1용)
        st.markdown("## 📋 Phase 1: 팀 내부 작업")
        team_work_containers = {}
        for team in debate_system.available_teams:
            team_work_containers[team.name] = st.expander(f"🔍 {team.name}", expanded=True)
            with team_work_containers[team.name]:
                st.info("대기 중...")
        
        # Phase 2: 발표
        presentation_section = st.container()
        with presentation_section:
            st.markdown("## 🎤 Phase 2: 팀별 발표")
        presentation_containers = {}
        
        # Phase 3: 토론
        debate_section = st.container()
        with debate_section:
            st.markdown("## ⚔️ Phase 3: 팀간 토론")
        
        # Phase 4: QA
        qa_section = st.container()
        
        # 토론 실행
        total_phases = 4
        current_phase = 0
        
        results = {}  # 최종 결과 저장
        
        for update in debate_system.run_team_debate(combined_data, analysis_task, max_revisions):
            # 중단 요청 체크
            if check_stop_requested():
                st.warning("🛑 **토론이 강제 중단되었습니다.**")
                status_text.text("🛑 중단됨")
                progress_bar.progress(1.0)
                st.session_state.team_debate_running = False
                
                # 현재까지 결과 표시
                st.markdown("---")
                st.markdown("### ⚠️ 중단 시점까지의 결과")
                st.info(f"중단된 Phase: {current_phase}")
                return
            
            stage = update.get("stage", "")
            message = update.get("message", "")
            content = update.get("content", "")
            team_name = update.get("team", "")
            
            # 에러 처리
            if stage == "error":
                st.error(message)
                st.session_state.team_debate_running = False
                return
            
            # Phase 시작/완료 처리
            if stage == "phase_start":
                phase_num = update.get("phase", 1)
                current_phase = phase_num
                progress_bar.progress(phase_num / total_phases * 0.9)
                status_text.text(f"🔄 {update.get('phase_name', '')}")
                phase_placeholders[phase_num].markdown(f"🔵 **{phases[phase_num-1]}**")
            
            elif stage == "phase_complete":
                phase_num = update.get("phase", 1)
                phase_placeholders[phase_num].markdown(f"✅ ~~{phases[phase_num-1]}~~")
            
            # Phase 1: 팀 내부 작업
            elif stage == "team_internal_start":
                if team_name in team_work_containers:
                    with team_work_containers[team_name]:
                        st.markdown(f"---\n**{message}**")
            
            elif stage == "member_analyzing":
                status_text.text(message)
                if team_name in team_work_containers:
                    with team_work_containers[team_name]:
                        st.info(f"🔍 팀원({update.get('model', '')}) 분석 중...")
            
            elif stage == "member_draft_done":
                if team_name in team_work_containers:
                    with team_work_containers[team_name]:
                        with st.expander("📄 팀원 초안", expanded=False):
                            st.markdown(content[:800] + "..." if len(str(content)) > 800 else content)
            
            elif stage == "leader_reviewing":
                status_text.text(message)
                if team_name in team_work_containers:
                    with team_work_containers[team_name]:
                        st.info(f"👔 팀장({update.get('model', '')}) 검토 #{update.get('revision_round', 0)+1}")
            
            elif stage == "leader_decision":
                if team_name in team_work_containers:
                    with team_work_containers[team_name]:
                        if update.get("approved"):
                            st.success(f"✅ 승인! (점수: {update.get('score', 0)}/10)")
                        else:
                            st.warning(f"📝 수정 요청 (점수: {update.get('score', 0)}/10)")
            
            elif stage == "member_revising":
                status_text.text(message)
            
            elif stage == "member_revised":
                if team_name in team_work_containers:
                    with team_work_containers[team_name]:
                        with st.expander(f"✏️ 수정본 #{update.get('revision', 1)}", expanded=False):
                            st.markdown(content[:500] + "..." if len(str(content)) > 500 else content)
            
            elif stage == "team_approved" or stage == "team_force_submit":
                if team_name in team_work_containers:
                    with team_work_containers[team_name]:
                        if stage == "team_approved":
                            st.success(message)
                        else:
                            st.warning(message)
            
            elif stage == "team_internal_complete":
                if team_name in team_work_containers:
                    with team_work_containers[team_name]:
                        st.success(f"🏁 **{team_name} 내부 작업 완료** (수정 {update.get('revisions', 0)}회, 점수 {update.get('score', 0)}/10)")
            
            # Phase 2: 발표
            elif stage == "presentation_start":
                status_text.text(message)
                with presentation_section:
                    if team_name not in presentation_containers:
                        presentation_containers[team_name] = st.expander(f"🎤 {team_name} 발표", expanded=True)
            
            elif stage == "presentation_done":
                if team_name in presentation_containers:
                    with presentation_containers[team_name]:
                        st.markdown(content)
            
            # Phase 3: 토론
            elif stage == "debate_phase_start":
                status_text.text(message)
            
            elif stage == "debate_arguments":
                with debate_section:
                    st.markdown("### 💪 Round 1: 각 팀 강점 주장")
            
            elif stage == "team_arguing":
                status_text.text(message)
            
            elif stage == "team_argument_done":
                with debate_section:
                    with st.expander(f"💪 {team_name} 주장", expanded=False):
                        st.markdown(content)
            
            elif stage == "debate_rebuttals":
                with debate_section:
                    st.markdown("### ⚡ Round 2: 상호 반박")
            
            elif stage == "team_rebutting":
                status_text.text(message)
            
            elif stage == "team_rebuttal_done":
                with debate_section:
                    with st.expander(f"⚡ {team_name} 반박", expanded=False):
                        st.markdown(content)
            
            elif stage == "debate_defenses":
                with debate_section:
                    st.markdown("### 🛡️ Round 3: 최종 방어")
            
            elif stage == "team_defending":
                status_text.text(message)
            
            elif stage == "team_defense_done":
                with debate_section:
                    with st.expander(f"🛡️ {team_name} 최종 방어", expanded=False):
                        st.markdown(content)
            
            # Phase 4: QA 평가
            elif stage == "qa_phase_start":
                status_text.text(message)
                with qa_section:
                    st.markdown("## 🏛️ Phase 4: QA 최종 평가")
                    st.info(f"⚖️ {update.get('model', 'AI')} 심판이 평가 중...")
            
            elif stage == "qa_evaluating":
                status_text.text(message)
            
            elif stage == "qa_done":
                with qa_section:
                    st.markdown("### 📊 최종 평가 결과")
                    st.markdown(content)
            
            # 완료
            elif stage == "complete":
                progress_bar.progress(1.0)
                status_text.text("🏁 토론 완료!")
                st.balloons()
                
                results = update
                
                st.divider()
                st.markdown("## 🏆 최종 결과 요약")
                
                teams_data = update.get("teams", {})
                cols = st.columns(len(teams_data))
                
                for idx, (tname, data) in enumerate(teams_data.items()):
                    with cols[idx % len(cols)]:
                        st.markdown(f"### {tname}")
                        approved_icon = "✅" if data.get("approved") else "⚠️"
                        st.markdown(f"- 승인 상태: {approved_icon}")
                        st.markdown(f"- 팀장 점수: {data.get('score', 'N/A')}/10")
                        st.markdown(f"- 수정 횟수: {data.get('revisions', 0)}회")
                        
                        with st.expander("📄 최종 분석"):
                            st.markdown(data.get("analysis", "N/A"))
                        
                        with st.expander("🎤 발표"):
                            st.markdown(data.get("presentation", "N/A"))
                
                # QA 평가 결과
                st.markdown("### 🏛️ QA 최종 평가")
                st.markdown(update.get("qa_evaluation", "N/A"))
    
    finally:
        # 토론 상태 초기화
        st.session_state.team_debate_running = False
        st.session_state.team_debate_stop_requested = False


# =====================================================
# � 토론 결과 시각화 헬퍼 함수
# =====================================================

def _display_phase_result(phase_num: int, phase_result: dict, teams: list):
    """각 Phase 완료 시 실시간 결과 표시"""
    import plotly.graph_objects as go
    import plotly.express as px
    
    phase_names = {
        1: "📋 Phase 1: 팀 내부 작업 완료",
        2: "🎤 Phase 2: 팀별 발표 완료",
        3: "🔍 Phase 3: 상호 검토 완료",
        4: "💪 Phase 4: 분석 강화 완료",
        5: "🤝 Phase 5: 합의점 도출 완료",
        6: "🏛️ Phase 6: QA 평가 완료"
    }
    
    st.markdown(f"### {phase_names.get(phase_num, f'Phase {phase_num} 완료')}")
    
    if phase_num == 1:
        # Phase 1: 팀별 분석 결과 카드
        if phase_result:
            team_cols = st.columns(len(phase_result))
            for idx, (team_name, data) in enumerate(phase_result.items()):
                with team_cols[idx]:
                    approved_icon = "✅" if data.get("approved") else "⏳"
                    st.metric(
                        f"{approved_icon} {team_name}",
                        f"점수: {data.get('score', 0)}/10",
                        f"수정 {data.get('revisions', 0)}회"
                    )
                    with st.expander("📝 초기 분석", expanded=False):
                        st.markdown(data.get("analysis", "N/A")[:500] + "..." if len(data.get("analysis", "")) > 500 else data.get("analysis", "N/A"))
    
    elif phase_num == 2:
        # Phase 2: 발표 내용
        presentations = phase_result.get("presentations", {})
        if presentations:
            tabs = st.tabs([f"🎤 {name}" for name in presentations.keys()])
            for idx, (team_name, presentation) in enumerate(presentations.items()):
                with tabs[idx]:
                    st.markdown(presentation)
    
    elif phase_num == 3:
        # Phase 3: 상호 검토 피드백 매트릭스
        feedbacks = phase_result.get("feedbacks", {})
        reviews = phase_result.get("reviews", {})
        
        if reviews:
            st.markdown("**📊 피드백 매트릭스**")
            
            # 피드백 매트릭스 테이블 생성
            reviewer_names = list(reviews.keys())
            target_names = list(feedbacks.keys())
            
            for reviewer, targets in reviews.items():
                with st.expander(f"📝 [{reviewer}]의 피드백", expanded=False):
                    for target, content in targets.items():
                        st.markdown(f"**→ [{target}]에게:**")
                        st.info(content[:600] + "..." if len(content) > 600 else content)
    
    elif phase_num == 4:
        # Phase 4: 강화된 분석 및 포트폴리오
        enhanced_analyses = phase_result.get("enhanced_analyses", {})
        portfolios = phase_result.get("portfolios", {})
        
        if enhanced_analyses:
            tabs = st.tabs([f"💪 {name}" for name in enhanced_analyses.keys()])
            for idx, (team_name, analysis) in enumerate(enhanced_analyses.items()):
                with tabs[idx]:
                    st.markdown(analysis)
                    
                    # 포트폴리오 시각화
                    portfolio = portfolios.get(team_name, {})
                    if portfolio:
                        st.markdown("**📊 추천 포트폴리오**")
                        
                        # 파이 차트
                        fig = go.Figure(data=[go.Pie(
                            labels=list(portfolio.keys()),
                            values=list(portfolio.values()),
                            hole=0.4,
                            textinfo='label+percent'
                        )])
                        fig.update_layout(
                            title=f"{team_name} 추천 포트폴리오",
                            height=300,
                            margin=dict(t=30, b=0, l=0, r=0)
                        )
                        st.plotly_chart(fig, use_container_width=True, key=f"portfolio_pie_{team_name}_{phase_num}")
    
    elif phase_num == 5:
        # Phase 5: 합의점
        consensus = phase_result.get("consensus", "")
        if consensus:
            st.markdown(consensus)
    
    elif phase_num == 6:
        # Phase 6: QA 평가
        qa_evaluation = phase_result.get("qa_evaluation", "")
        if qa_evaluation:
            st.markdown(qa_evaluation)
    
    st.divider()


def _display_final_results(final_result: dict, teams: list):
    """최종 결과 시각화"""
    import plotly.graph_objects as go
    import plotly.express as px
    import pandas as pd
    
    st.divider()
    st.header("📊 최종 토론 결과")
    
    teams_data = final_result.get("teams", {})
    
    # ========== 1. 팀별 점수 비교 차트 ==========
    st.subheader("📈 팀별 점수 비교")
    
    if teams_data:
        team_names = list(teams_data.keys())
        scores = [teams_data[t].get("score", 0) for t in team_names]
        revisions = [teams_data[t].get("revisions", 0) for t in team_names]
        
        # 막대 차트
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='팀장 점수',
            x=team_names,
            y=scores,
            text=scores,
            textposition='outside',
            marker_color=['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A'][:len(team_names)]
        ))
        fig.update_layout(
            title="팀별 팀장 점수 (10점 만점)",
            yaxis_title="점수",
            yaxis_range=[0, 12],
            height=350
        )
        st.plotly_chart(fig, use_container_width=True, key="final_team_scores")
    
    # ========== 2. 팀별 상세 결과 탭 ==========
    st.subheader("📋 팀별 상세 결과")
    
    if teams_data:
        tabs = st.tabs([f"🏆 {name}" for name in teams_data.keys()])
        
        for idx, (team_name, team_data) in enumerate(teams_data.items()):
            with tabs[idx]:
                # 기본 정보
                col1, col2, col3 = st.columns(3)
                with col1:
                    approved_icon = "✅" if team_data.get("approved") else "⏳"
                    st.metric("승인 상태", approved_icon)
                with col2:
                    st.metric("팀장 점수", f"{team_data.get('score', 0)}/10")
                with col3:
                    st.metric("수정 횟수", f"{team_data.get('revisions', 0)}회")
                
                # 분석 내용들
                with st.expander("📝 초기 분석", expanded=False):
                    st.markdown(team_data.get("analysis", "N/A"))
                
                with st.expander("🎤 발표 내용", expanded=False):
                    st.markdown(team_data.get("presentation", "N/A"))
                
                with st.expander("💪 강화된 분석", expanded=True):
                    st.markdown(team_data.get("enhanced_analysis", "N/A"))
                
                # 받은 피드백
                feedbacks_received = team_data.get("feedbacks_received", [])
                if feedbacks_received:
                    with st.expander(f"📬 받은 피드백 ({len(feedbacks_received)}건)", expanded=False):
                        for fb in feedbacks_received:
                            st.info(f"**From [{fb.get('from', 'Unknown')}]:**\n{fb.get('content', '')[:400]}...")
                
                # 최종 포트폴리오
                portfolio = team_data.get("portfolio", {})
                if portfolio:
                    st.markdown("**📊 최종 추천 포트폴리오**")
                    
                    # 테이블로 표시
                    portfolio_df = pd.DataFrame([
                        {"종목/ETF": k, "비중(%)": v}
                        for k, v in portfolio.items()
                    ])
                    st.dataframe(portfolio_df, use_container_width=True, hide_index=True)
                    
                    # 파이 차트
                    fig = go.Figure(data=[go.Pie(
                        labels=list(portfolio.keys()),
                        values=list(portfolio.values()),
                        hole=0.4
                    )])
                    fig.update_layout(height=300, margin=dict(t=20, b=0, l=0, r=0))
                    st.plotly_chart(fig, use_container_width=True, key=f"final_portfolio_{team_name}")
    
    # ========== 3. 포트폴리오 비교 테이블 ==========
    st.subheader("📊 팀별 포트폴리오 비교")
    
    all_portfolios = {}
    all_tickers = set()
    for team_name, team_data in teams_data.items():
        portfolio = team_data.get("portfolio", {})
        all_portfolios[team_name] = portfolio
        all_tickers.update(portfolio.keys())
    
    if all_tickers:
        comparison_data = []
        for ticker in sorted(all_tickers):
            row = {"종목/ETF": ticker}
            for team_name, portfolio in all_portfolios.items():
                row[team_name] = f"{portfolio.get(ticker, 0)}%"
            comparison_data.append(row)
        
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)
    
    # ========== 4. 합의점 ==========
    consensus = final_result.get("consensus", "")
    if consensus:
        st.subheader("🤝 팀간 합의점")
        with st.expander("합의점 상세 내용", expanded=True):
            st.markdown(consensus)
    
    # ========== 5. QA 평가 ==========
    st.subheader("🏛️ QA 최종 평가")
    qa_evaluation = final_result.get("qa_evaluation", "")
    if qa_evaluation:
        st.markdown(qa_evaluation)
    else:
        st.info("QA 평가 결과가 없습니다.")
    
    # ========== 6. 요약 정보 ==========
    st.divider()
    summary = final_result.get("summary", {})
    st.caption(f"""
    📌 **요약**: 참가팀 {summary.get('total_teams', 0)}개 | 
    총 {summary.get('total_phases', 6)} Phase 완료 | 
    완료 시간: {final_result.get('timestamp', 'N/A')}
    """)


# =====================================================
# �🏆 통합 AI 토론 페이지 (개별/팀 토론 통합)
# =====================================================

def show_unified_debate_page():
    """통합 AI 토론 페이지 - 개별 토론과 팀 토론을 버튼으로 전환"""
    
    st.header("🏆 AI 토론")
    
    # 현재 작동 모델 표시
    try:
        from ai_providers.team_debate import GITHUB_MODELS, NATIVE_MODELS_FLAT, MODELS_BY_FAMILY
        github_models = list(GITHUB_MODELS.keys())
        native_models = list(NATIVE_MODELS_FLAT.keys())
        
        st.info(f"""**📡 사용 가능한 AI 모델:**
- **🐙 GitHub Models (무료)**: {', '.join(github_models[:6])}{'...' if len(github_models) > 6 else ''}
- **🔑 Native API (API 키 필요)**: {', '.join(native_models[:6])}{'...' if len(native_models) > 6 else ''}

> 💡 **초기 로딩**: GitHub Models 우선 | **버튼 클릭**: Native API 우선 (활성화 시)
""")
    except Exception as e:
        st.warning(f"모델 정보 로드 실패: {e}")
    
    st.divider()
    
    # 역할/직급별 철학 표시 (접을 수 있는 섹션)
    with st.expander("📚 AI 역할 및 직급별 철학 보기", expanded=False):
        try:
            from ai_providers.team_debate import ROLE_PHILOSOPHIES, POSITION_PHILOSOPHIES
            
            st.markdown("### 🎭 역할별 철학 (Role Philosophies)")
            role_cols = st.columns(2)
            for idx, (role_key, role_data) in enumerate(ROLE_PHILOSOPHIES.items()):
                with role_cols[idx % 2]:
                    st.markdown(f"**{role_data['name']}**")
                    st.info(role_data['philosophy'])
            
            st.markdown("---")
            st.markdown("### 👔 직급별 철학 (Position Philosophies)")
            pos_cols = st.columns(3)
            for idx, (pos_key, pos_data) in enumerate(POSITION_PHILOSOPHIES.items()):
                with pos_cols[idx % 3]:
                    st.markdown(f"**{pos_data['name']}**")
                    st.info(pos_data['philosophy'])
        except ImportError:
            st.warning("역할/직급 철학을 로드할 수 없습니다.")
    
    st.divider()
    
    # 토론 모드 선택 (버튼으로 전환)
    st.subheader("🎯 토론 모드 선택")
    
    col1, col2 = st.columns(2)
    
    with col1:
        individual_btn = st.button(
            "🎭 개별 토론 (1:1)",
            use_container_width=True,
            help="두 AI가 1:1로 토론하며 분석을 수정"
        )
    
    with col2:
        team_btn = st.button(
            "🏆 팀 토론 (다중 팀)",
            use_container_width=True,
            help="여러 팀이 각각 분석하고 토론"
        )
    
    # 세션 상태로 모드 관리
    if individual_btn:
        st.session_state.debate_mode = "individual"
    elif team_btn:
        st.session_state.debate_mode = "team"
    
    if "debate_mode" not in st.session_state:
        st.session_state.debate_mode = "team"  # 기본값
    
    st.divider()
    
    # 선택된 모드에 따라 UI 표시
    if st.session_state.debate_mode == "individual":
        st.markdown("### 🎭 개별 토론 모드 (1:1)")
        st.markdown("""
        *두 AI가 서로의 분석을 비평하고 수정하면서 더 나은 결론에 도달합니다*
        
        **토론 진행 방식:**
        1. 🔵 **1차 AI**가 초기 분석 수행
        2. 🟠 **2차 AI**가 분석을 비평하고 문제점 지적
        3. 🔵 **1차 AI**가 비평을 반영하여 수정
        4. 🟠 **2차 AI**가 수정된 분석 평가
        5. 역할을 교체하며 반복
        6. 📋 최종 종합 보고서 생성
        """)
        
        # 활성화된 모델만 사용 (사이드바 설정 연동)
        active_models = get_active_models()
        all_models = active_models['github'] + active_models['native']
        
        if not all_models:
            st.error("⚠️ 활성화된 AI 모델이 없습니다! 사이드바에서 최소 1개의 모델을 켜주세요.")
            return
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            primary_ai = st.selectbox(
                "1차 분석 AI",
                all_models,
                index=0,
                key="individual_primary_ai"
            )
        
        with col2:
            secondary_ai = st.selectbox(
                "2차 비평 AI",
                all_models,
                index=min(3, len(all_models)-1),
                key="individual_secondary_ai"
            )
        
        with col3:
            max_rounds = st.slider("최대 토론 라운드", 1, 5, 3, key="individual_max_rounds")
        
        if primary_ai == secondary_ai:
            st.warning("⚠️ 서로 다른 AI를 선택해주세요!")
        else:
            # 토론 유형 선택
            debate_type = st.radio(
                "토론 주제 선택",
                ["📊 시장 분석 토론", "📈 개별 주식 분석 토론"],
                horizontal=True,
                key="individual_debate_type"
            )
            
            if debate_type == "📊 시장 분석 토론":
                show_market_debate(primary_ai, secondary_ai, max_rounds)
            else:
                show_stock_debate(primary_ai, secondary_ai, max_rounds)
    
    else:  # 팀 토론 모드
        st.markdown("### 🏆 팀 토론 모드")
        st.markdown("""
        **팀 기반 AI 토론 시스템 v2**
        
        - 🎯 **GitHub Models 전용** (무료 GPT-4.1 포함)
        - 👥 **팀 개수 자유 설정** (2~5팀)
        - 🎨 **팀 구성 직접 선택** (팀장/팀원 모델)
        
        **새로운 토론 진행 방식 (6 Phases):**
        
        | Phase | 단계 | 설명 |
        |-------|------|-----|
        | **1** | 팀 내부 작업 | 팀원이 분석 → 팀장이 검토/피드백 → 수정 반복 → **승인** |
        | **2** | 팀별 발표 | 각 팀장이 분석 결과를 정리하여 발표 |
        | **3** | 상호 검토 | 직장 피드백 스타일로 건설적인 검토 💼 |
        | **4** | 분석 강화 | 받은 피드백을 반영하여 분석 보강 💪 |
        | **5** | 합의점 도출 | 모든 팀의 공통 견해 정리 🤝 |
        | **6** | QA 평가 | QA가 종합 평가 및 최종 투자 권고 🏛️ |
        
        > 💡 **핵심 변화**: 공격적 토론 → 건설적 피드백 기반 협업
        """)
        
        # 팀 토론 설정 UI 호출
        _show_team_debate_settings()


def _show_team_debate_settings():
    """팀 토론 설정 UI (내부 함수)"""
    
    try:
        from ai_providers.team_debate import (
            AITeamDebateSystem, GITHUB_MODELS, GITHUB_MODELS_BY_TIER,
            NATIVE_MODELS, NATIVE_MODELS_FLAT, NATIVE_MODELS_BY_TIER,
            ALL_AVAILABLE_MODELS, ALL_MODELS_BY_TIER,
            AI_PROVIDER_PHILOSOPHIES, MODELS_BY_FAMILY,
            get_model_source, get_model_provider, get_model_family,
            get_all_github_models, get_github_models_by_tier, create_team,
            ROLE_PHILOSOPHIES, POSITION_PHILOSOPHIES
        )
    except ImportError as e:
        st.error(f"팀 토론 모듈 로드 실패: {e}")
        return
    
    # ===== 사이드바 설정에 따라 활성화된 모델만 필터링 =====
    active_models = get_active_models()
    active_native = set(active_models['native'])
    active_github = set(active_models['github'])
    
    # 활성화된 모델이 없으면 경고
    if not active_native and not active_github:
        st.error("⚠️ 활성화된 AI 모델이 없습니다! 사이드바에서 최소 1개의 모델을 켜주세요.")
        return
    
    # 활성화된 모델만 필터링
    filtered_all_models = {}
    for model, info in ALL_AVAILABLE_MODELS.items():
        if model in active_native or model in active_github:
            filtered_all_models[model] = info
    
    # 필터링된 모델 기준으로 티어 분류
    all_models = list(filtered_all_models.keys())
    premium_models = [m for m in ALL_MODELS_BY_TIER["premium"] if m in filtered_all_models]
    standard_models = [m for m in ALL_MODELS_BY_TIER["standard"] if m in filtered_all_models]
    light_models = [m for m in ALL_MODELS_BY_TIER["light"] if m in filtered_all_models]
    
    # 모델 소스별 분류 (활성화된 것만)
    github_models_set = active_github
    native_models_set = active_native
    
    # 계열별 모델 정보 표시 (활성화된 것만)
    st.markdown(f"""
    ### 📊 활성화된 모델: **{len(all_models)}개**
    """)
    
    if len(all_models) == 0:
        st.warning("⚠️ 활성화된 모델이 없습니다. 사이드바에서 모델을 켜주세요.")
        return
    
    # 활성화된 계열만 표시
    active_families = {}
    for family_key, family_info in MODELS_BY_FAMILY.items():
        active_in_family = [m for m in family_info['models'] if m in filtered_all_models]
        if active_in_family:
            active_families[family_key] = {
                **family_info,
                'active_models': active_in_family
            }
    
    if active_families:
        family_cols = st.columns(min(len(active_families), 4))
        for idx, (family_key, family_info) in enumerate(active_families.items()):
            with family_cols[idx % len(family_cols)]:
                source_icon = "🔑" if family_info['source'] == 'native' else ("🐙" if family_info['source'] == 'github' else "🔀")
                st.markdown(f"**{family_info['name']}** {source_icon}")
                st.caption(", ".join(family_info['active_models'][:3]) + ("..." if len(family_info['active_models']) > 3 else ""))
    
    st.markdown("""
    > 💡 **🔑 Native API**: 직접 API 키 필요 (Anthropic, OpenAI, Google) | **🐙 GitHub Models**: 무료 사용 가능
    > 
    > ⚙️ **사이드바에서 모델을 켜고 끌 수 있습니다**
    """)
    
    # Native API 철학 표시 (접을 수 있는 섹션)
    with st.expander("🧠 Native API 제공자별 철학/특성 보기", expanded=False):
        cols = st.columns(2)
        for idx, (provider, info) in enumerate(AI_PROVIDER_PHILOSOPHIES.items()):
            with cols[idx % 2]:
                st.markdown(f"### {info['icon']} {info['name']}")
                st.info(info['philosophy'])
                st.caption(f"📌 분석 스타일: **{info['style']}**")
    
    st.divider()
    
    # 팀 모드 선택
    st.subheader("1️⃣ 팀 구성 모드")
    
    team_mode = st.radio(
        "팀 구성 방식",
        ["간편 모드 (2인 팀)", "확장 모드 (5인 팀)"],
        index=0,
        key="unified_team_mode",
        horizontal=True,
        help="간편 모드: 팀장 + 팀원 1명 | 확장 모드: 팀장 + 역할별 팀원 4명 (분석가, 전략가, 비평가, 리스크 관리자)"
    )
    use_extended_team = (team_mode == "확장 모드 (5인 팀)")
    
    if use_extended_team:
        st.info("""
        **📋 확장 모드 (5인 1팀 구성)**
        - 👔 **팀장 (종합가)**: 팀원들의 분석을 종합하여 최종 의견 도출
        - 📊 **분석가**: 데이터/수치 기반 정량적 분석
        - 🎯 **전략가**: 거시경제 관점의 중장기 전략
        - ❓ **비평가**: Devil's Advocate 역할, 반대 논거 제시
        - 🛡️ **리스크 관리자**: 하방 리스크와 헤지 전략
        
        > 각 역할이 독립적으로 분석 → 팀장이 종합하여 팀 최종 의견 생성
        """)
    else:
        st.caption("👔 팀장 + 👤 팀원 1명으로 구성된 간단한 팀 구조")
    
    # 팀 개수 선택
    st.subheader("2️⃣ 팀 개수 설정")
    num_teams = st.slider("참가 팀 수", 2, 5, 2, key="unified_num_teams")
    
    st.divider()
    
    # 팀 구성 UI
    st.subheader("3️⃣ 팀 구성")
    
    teams = []
    team_colors = ["🔵", "🟢", "🟠", "🟣", "🔴"]
    team_color_codes = ["blue", "green", "orange", "purple", "red"]
    
    # 모델 선택 옵션 (티어별 + 소스별 그룹화)
    def format_model(model):
        # 소스 표시
        if model in github_models_set:
            source = "🐙"
        elif model in native_models_set:
            provider = get_model_provider(model)
            provider_icons = {"anthropic": "🧠", "openai": "🤖", "gemini": "💎"}
            source = provider_icons.get(provider, "🔑")
        else:
            source = "❓"
        
        # 계열 표시 추가
        family = get_model_family(model) if 'get_model_family' in dir() else None
        
        # 티어 표시
        if model in premium_models:
            return f"⭐ {source} {model}"
        elif model in standard_models:
            return f"📦 {source} {model}"
        else:
            return f"🪶 {source} {model}"
    
    cols = st.columns(min(num_teams, 3))
    
    for i in range(num_teams):
        col_idx = i % len(cols)
        with cols[col_idx]:
            st.markdown(f"### {team_colors[i]} 팀 {i+1}")
            
            team_name = st.text_input(
                "팀 이름", 
                f"{team_colors[i]} Team {i+1}",
                key=f"unified_team_name_{i}"
            )
            
            # 팀장 모델 (Premium 추천)
            st.markdown("**👔 팀장 (종합가)** - 고급 모델 추천")
            
            # 기본 팀장 모델: Premium에서 순환 선택
            default_leader_idx = 0
            if i < len(premium_models) and premium_models[i] in all_models:
                default_leader_idx = all_models.index(premium_models[i])
            
            leader_model = st.selectbox(
                "팀장 모델",
                all_models,
                index=default_leader_idx,
                format_func=format_model,
                key=f"unified_leader_{i}"
            )
            
            # 간편 모드: 팀원 1명
            if not use_extended_team:
                st.markdown("**👤 팀원** (경량 모델 추천)")
                
                default_member_idx = 0
                if i < len(light_models) and light_models[i] in all_models:
                    default_member_idx = all_models.index(light_models[i])
                
                member_model = st.selectbox(
                    "팀원 모델",
                    all_models,
                    index=default_member_idx,
                    format_func=format_model,
                    key=f"unified_member_{i}"
                )
                
                teams.append(create_team(team_name, leader_model, member_model, team_color_codes[i]))
            
            # 확장 모드: 역할별 팀원 4명
            else:
                role_models = {}
                
                # 역할 정보
                roles_info = [
                    ("📊 분석가", "analyst", "데이터/수치 기반 정량 분석"),
                    ("🎯 전략가", "strategist", "거시경제 및 중장기 전략"),
                    ("❓ 비평가", "critic", "반대 논거 및 리스크 지적"),
                    ("🛡️ 리스크 관리자", "risk_manager", "하방 리스크 관리")
                ]
                
                # 역할별 기본 모델 추천 (다양한 소스에서 순환)
                role_default_models = [
                    light_models[0] if len(light_models) > 0 else all_models[0],  # analyst
                    standard_models[0] if len(standard_models) > 0 else all_models[0],  # strategist
                    light_models[1] if len(light_models) > 1 else all_models[0],  # critic
                    standard_models[1] if len(standard_models) > 1 else all_models[0],  # risk_manager
                ]
                
                with st.expander("👥 역할별 팀원 설정 (4명)", expanded=True):
                    for j, (role_label, role_key, role_desc) in enumerate(roles_info):
                        st.markdown(f"**{role_label}** - {role_desc}")
                        
                        default_idx = all_models.index(role_default_models[j]) if role_default_models[j] in all_models else 0
                        
                        role_models[role_key] = st.selectbox(
                            f"{role_label} 모델",
                            all_models,
                            index=default_idx,
                            format_func=format_model,
                            key=f"unified_{role_key}_{i}"
                        )
                
                # 확장 팀 생성 (create_team에 추가 파라미터 전달)
                team = create_team(team_name, leader_model, None, team_color_codes[i])
                team.use_extended_team = True
                team.analyst_model = role_models.get("analyst")
                team.strategist_model = role_models.get("strategist")
                team.critic_model = role_models.get("critic")
                team.risk_manager_model = role_models.get("risk_manager")
                teams.append(team)
            
            # 소스 및 철학 표시
            def get_source_info(model):
                if model in github_models_set:
                    return "🐙 GitHub Models", None
                elif model in native_models_set:
                    provider = get_model_provider(model)
                    if provider and provider in AI_PROVIDER_PHILOSOPHIES:
                        info = AI_PROVIDER_PHILOSOPHIES[provider]
                        return f"{info['icon']} Native ({info['name']})", info['style']
                    return "🔑 Native API", None
                return "❓ Unknown", None
            
            leader_src, leader_style = get_source_info(leader_model)
            
            if use_extended_team:
                caption_text = f"👔 팀장: `{leader_model}` ({leader_src})"
                if leader_style:
                    caption_text += f"\n  └ 스타일: {leader_style}"
                for role_label, role_key, _ in roles_info:
                    role_model = role_models.get(role_key, "N/A")
                    role_src, _ = get_source_info(role_model)
                    caption_text += f"\n{role_label}: `{role_model}` ({role_src})"
            else:
                member_src, member_style = get_source_info(member_model)
                caption_text = f"팀장: `{leader_model}` ({leader_src})"
                if leader_style:
                    caption_text += f"\n  └ 스타일: {leader_style}"
                caption_text += f"\n팀원: `{member_model}` ({member_src})"
                if member_style:
                    caption_text += f"\n  └ 스타일: {member_style}"
            
            st.caption(caption_text)
    
    st.divider()
    
    # 심판 선택
    st.subheader("4️⃣ 심판 (QA) 설정")
    
    # 기본 심판 모델: gpt-4.1 또는 gpt-4o (무료/안정적)
    default_qa_model = "gpt-4.1" if "gpt-4.1" in all_models else "gpt-4o"
    default_qa_idx = all_models.index(default_qa_model) if default_qa_model in all_models else 0
    
    qa_model = st.selectbox(
        "심판 모델 (Premium 추천)",
        all_models,
        index=default_qa_idx,
        format_func=format_model,
        key="unified_qa_model"
    )
    
    # QA 모델 소스 정보 표시
    def get_source_info_qa(model):
        if model in github_models_set:
            return "🐙 GitHub Models", None
        elif model in native_models_set:
            provider = get_model_provider(model)
            if provider and provider in AI_PROVIDER_PHILOSOPHIES:
                info = AI_PROVIDER_PHILOSOPHIES[provider]
                return f"{info['icon']} Native ({info['name']})", info['style']
            return "🔑 Native API", None
        return "❓ Unknown", None
    
    qa_src, qa_style = get_source_info_qa(qa_model)
    qa_caption = f"🏛️ 심판: `{qa_model}` ({qa_src})"
    if qa_style:
        qa_caption += f"\n  └ 평가 스타일: {qa_style}"
    st.caption(qa_caption)
    
    st.divider()
    
    # 토론 주제 입력
    st.subheader("5️⃣ 토론 주제")
    topic = st.text_area(
        "토론 주제를 입력하세요",
        "현재 시장 상황에서 최적의 투자 전략은 무엇인가?",
        height=100,
        key="unified_topic"
    )
    
    # 시장 데이터 포함 옵션
    include_market_data = st.checkbox("📊 현재 시장 데이터 포함", value=True, key="unified_include_market")
    
    st.divider()
    
    # 토론 시작/중단 버튼
    col_start, col_stop = st.columns([3, 1])
    with col_start:
        start_debate = st.button("🚀 팀 토론 시작", type="primary", use_container_width=True, key="unified_start_debate")
    with col_stop:
        if st.button("🛑 강제 중단", type="secondary", use_container_width=True, key="unified_stop_debate",
                     disabled=not st.session_state.get('unified_debate_running', False)):
            st.session_state.unified_debate_stop_requested = True
            st.warning("⚠️ 중단 요청됨...")
    
    if start_debate:
        st.session_state.unified_debate_running = True
        st.session_state.unified_debate_stop_requested = False
        
        # 시장 데이터 수집
        market_data_dict = {}
        
        if include_market_data:
            with st.spinner("시장 데이터 수집 중..."):
                try:
                    market_data = get_market_data()
                    economic_cycle = get_economic_cycle()
                    
                    market_data_dict = {
                        'vix': market_data.get('vix'),
                        'sp500_pe': market_data.get('sp500_pe'),
                        'treasury_10y': market_data.get('treasury_10y'),
                        'fear_greed': market_data.get('fear_greed'),
                        'economic_cycle': economic_cycle.get('current_phase', 'N/A'),
                        'cycle_confidence': economic_cycle.get('confidence', 0),
                        'recommendations': economic_cycle.get('recommendations', {})
                    }
                except Exception as e:
                    st.warning(f"시장 데이터 로드 실패: {e}")
        
        # 토론 시스템 초기화 및 실행
        try:
            # 수동 버튼 클릭 시 Native API 우선 (prefer_native=True)
            # 사용자 설정에서 Native API가 하나라도 켜져 있으면 Native 우선
            active = get_active_models()
            use_native_first = len(active['native']) > 0
            
            debate_system = AITeamDebateSystem(
                teams=teams, 
                qa_model=qa_model,
                prefer_native=use_native_first  # Native API가 활성화되어 있으면 우선 사용
            )
            
            # 진행 상황 표시
            total_phases = 6
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 실시간 중단 버튼
            stop_placeholder = st.empty()
            with stop_placeholder.container():
                if st.button("🛑 토론 강제 중단", key="unified_stop_during", type="secondary"):
                    st.session_state.unified_debate_stop_requested = True
            
            # Phase별 결과 표시 영역
            st.divider()
            phase_results_container = st.container()
            
            # 토론 실행 (run_team_debate 사용)
            final_result = None
            current_phase = 0
            phase_results = {}  # {phase_num: result_data}
            
            for update in debate_system.run_team_debate(market_data_dict, task=topic):
                # 중단 요청 체크
                if st.session_state.get('unified_debate_stop_requested', False):
                    st.warning("🛑 **토론이 강제 중단되었습니다.**")
                    status_text.text("🛑 중단됨")
                    progress_bar.progress(1.0)
                    st.session_state.unified_debate_running = False
                    st.session_state.unified_debate_stop_requested = False
                    st.info(f"중단된 Phase: {current_phase}")
                    break
                
                stage = update.get("stage", "")
                team = update.get("team", "")
                content = update.get("content", "")
                message = update.get("message", "")
                phase = update.get("phase", 0)
                
                if message:
                    status_text.text(f"[Phase {phase}/{total_phases}] {message}" if phase else message)
                
                # 진행률 업데이트
                if phase and isinstance(phase, int):
                    progress_bar.progress(min(phase / total_phases, 1.0))
                    current_phase = phase
                
                # Phase 완료 시 실시간 결과 표시
                if stage == "phase_complete":
                    phase_num = update.get("phase", 0)
                    phase_result_data = update.get("phase_result", {})
                    phase_results[phase_num] = phase_result_data
                    
                    with phase_results_container:
                        _display_phase_result(phase_num, phase_result_data, teams)
                
                # 최종 결과 저장
                if stage == "complete":
                    final_result = update
                    progress_bar.progress(1.0)
            
            # 토론 상태 초기화
            st.session_state.unified_debate_running = False
            st.session_state.unified_debate_stop_requested = False
            
            if final_result:
                st.success("🎉 토론이 완료되었습니다!")
                # ========== 최종 결과 시각화 ==========
                _display_final_results(final_result, teams)
            
        except Exception as e:
            st.error(f"토론 실행 오류: {e}")
            import traceback
            st.code(traceback.format_exc())
        finally:
            # 상태 정리
            st.session_state.unified_debate_running = False
            st.session_state.unified_debate_stop_requested = False


# ==================== 로그인/회원가입 페이지 ====================
def show_login_page():
    """로그인/회원가입 페이지"""
    st.header("🔐 로그인 / 회원가입")
    
    tab1, tab2 = st.tabs(["🔑 로그인", "📝 회원가입"])
    
    with tab1:
        st.subheader("기존 회원 로그인")
        
        with st.form("login_form"):
            username = st.text_input("사용자명", key="login_username")
            password = st.text_input("비밀번호", type="password", key="login_password")
            
            if st.form_submit_button("🔓 로그인", use_container_width=True):
                if username and password:
                    user = db.authenticate_user(username, password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        
                        # 기본 포트폴리오 선택
                        portfolios = db.get_portfolios(user['id'])
                        if portfolios:
                            st.session_state.selected_portfolio_id = portfolios[0]['id']
                        
                        st.success(f"✅ {username}님, 환영합니다!")
                        st.rerun()
                    else:
                        st.error("❌ 사용자명 또는 비밀번호가 올바르지 않습니다.")
                else:
                    st.warning("사용자명과 비밀번호를 입력해주세요.")
    
    with tab2:
        st.subheader("새 계정 만들기")
        
        with st.form("register_form"):
            new_username = st.text_input("사용자명 (영문/숫자)", key="reg_username")
            new_email = st.text_input("이메일 (선택)", key="reg_email")
            new_password = st.text_input("비밀번호", type="password", key="reg_password")
            confirm_password = st.text_input("비밀번호 확인", type="password", key="reg_confirm")
            
            if st.form_submit_button("📝 회원가입", use_container_width=True):
                if not new_username or not new_password:
                    st.warning("사용자명과 비밀번호를 입력해주세요.")
                elif new_password != confirm_password:
                    st.error("비밀번호가 일치하지 않습니다.")
                elif len(new_password) < 4:
                    st.error("비밀번호는 4자 이상이어야 합니다.")
                else:
                    user_id = db.create_user(new_username, new_password, new_email)
                    if user_id:
                        st.success("✅ 회원가입이 완료되었습니다! 로그인해주세요.")
                    else:
                        st.error("❌ 이미 존재하는 사용자명입니다.")


def show_current_vs_target(user_id: int, portfolio_id: int):
    """현재 vs 목표 배분 비교"""
    st.subheader("📊 현재 배분 vs 목표 배분")
    
    # 현재 보유
    holdings = db.get_holdings(user_id, portfolio_id)
    
    # 목표 배분
    targets = db.get_target_allocations(portfolio_id)
    
    if not holdings and not targets:
        st.info("보유 종목이나 목표 배분을 먼저 설정해주세요.")
        return
    
    # 현재 포트폴리오 가치 계산
    if holdings:
        tickers = [h['ticker'] for h in holdings]
        prices = rebalance_calculator.get_multiple_prices(tickers)
        total_value, current_details = rebalance_calculator.calculate_portfolio_value(holdings, prices)
    else:
        total_value = 0
        current_details = {}
    
    # 비교 테이블 생성
    all_tickers = set()
    for h in holdings:
        all_tickers.add(h['ticker'])
    for t in targets:
        all_tickers.add(t['ticker'])
    
    target_dict = {t['ticker']: t['target_percent'] for t in targets}
    
    comparison_data = []
    for ticker in sorted(all_tickers):
        current_pct = current_details.get(ticker, {}).get('percent', 0)
        target_pct = target_dict.get(ticker, 0)
        diff = current_pct - target_pct
        
        status = "✅" if abs(diff) < 2 else ("⬆️ 초과" if diff > 0 else "⬇️ 부족")
        
        comparison_data.append({
            "종목": ticker,
            "현재 비중": f"{current_pct:.1f}%",
            "목표 비중": f"{target_pct:.1f}%",
            "차이": f"{diff:+.1f}%",
            "상태": status
        })
    
    if comparison_data:
        df = pd.DataFrame(comparison_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 시각화
        fig = go.Figure()
        
        tickers_sorted = [d['종목'] for d in comparison_data]
        current_values = [current_details.get(t, {}).get('percent', 0) for t in tickers_sorted]
        target_values = [target_dict.get(t, 0) for t in tickers_sorted]
        
        fig.add_trace(go.Bar(name='현재', x=tickers_sorted, y=current_values, marker_color='steelblue'))
        fig.add_trace(go.Bar(name='목표', x=tickers_sorted, y=target_values, marker_color='lightgreen'))
        
        fig.update_layout(barmode='group', title="현재 vs 목표 배분", yaxis_title="비중 (%)")
        st.plotly_chart(fig, use_container_width=True)


def show_target_allocation_settings(user_id: int, portfolio_id: int):
    """목표 배분 설정"""
    st.subheader("🎯 목표 배분 설정")
    
    # 현재 목표 배분
    targets = db.get_target_allocations(portfolio_id)
    
    if targets:
        st.markdown("**현재 목표 배분:**")
        
        target_data = []
        total_pct = 0
        for t in targets:
            target_data.append({
                "종목": t['ticker'],
                "목표 비중": f"{t['target_percent']:.1f}%",
                "자산군": t.get('asset_class', '-'),
                "메모": t.get('notes', '-')
            })
            total_pct += t['target_percent']
        
        df = pd.DataFrame(target_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 합계 확인
        if abs(total_pct - 100) > 0.1:
            st.warning(f"⚠️ 목표 비중 합계: {total_pct:.1f}% (100%가 되어야 합니다)")
        else:
            st.success(f"✅ 목표 비중 합계: {total_pct:.1f}%")
        
        # 파이 차트
        fig = px.pie(
            values=[t['target_percent'] for t in targets],
            names=[t['ticker'] for t in targets],
            title="목표 포트폴리오 구성"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # 목표 배분 추가/수정
    st.markdown("**목표 배분 추가/수정:**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        ticker = st.text_input("종목 코드", key="target_ticker").upper()
        target_pct = st.number_input("목표 비중 (%)", min_value=0.0, max_value=100.0, step=1.0, key="target_pct")
    
    with col2:
        asset_class = st.selectbox(
            "자산군",
            ["주식", "채권", "ETF", "원자재", "현금", "기타"],
            key="target_class"
        )
        notes = st.text_input("메모", key="target_notes")
    
    with col3:
        st.markdown("")
        st.markdown("")
        if st.button("💾 저장", key="save_target"):
            if ticker and target_pct >= 0:
                db.set_target_allocation(portfolio_id, ticker, target_pct, asset_class, notes)
                st.success(f"✅ {ticker} 목표 비중이 저장되었습니다.")
                st.rerun()
            else:
                st.warning("종목 코드와 목표 비중을 입력해주세요.")
        
        if st.button("🗑️ 삭제", key="delete_target"):
            if ticker:
                db.delete_target_allocation(portfolio_id, ticker)
                st.success(f"✅ {ticker} 목표 비중이 삭제되었습니다.")
                st.rerun()
    
    # 프리셋 적용
    st.divider()
    st.markdown("**📦 프리셋 적용:**")
    
    preset_options = {
        "60/40 포트폴리오": {"SPY": 60, "TLT": 40},
        "올웨더": {"SPY": 30, "TLT": 40, "IEF": 15, "GLD": 7.5, "DBC": 7.5},
        "3펀드": {"VTI": 60, "VXUS": 30, "BND": 10},
        "배당 중심": {"VYM": 40, "SCHD": 30, "VIG": 20, "BND": 10},
    }
    
    col1, col2 = st.columns(2)
    with col1:
        preset = st.selectbox("프리셋 선택", list(preset_options.keys()), key="preset_select")
    with col2:
        st.markdown("")
        st.markdown("")
        if st.button("프리셋 적용", key="apply_preset"):
            # 기존 목표 배분 삭제
            for t in targets:
                db.delete_target_allocation(portfolio_id, t['ticker'])
            
            # 새 목표 배분 적용
            for ticker, pct in preset_options[preset].items():
                db.set_target_allocation(portfolio_id, ticker, pct, "ETF")
            
            st.success(f"✅ '{preset}' 프리셋이 적용되었습니다.")
            st.rerun()


def show_rebalance_plan(user_id: int, portfolio_id: int):
    """리밸런싱 계획"""
    st.subheader("📋 리밸런싱 계획")
    
    holdings = db.get_holdings(user_id, portfolio_id)
    targets = db.get_target_allocations(portfolio_id)
    
    if not targets:
        st.warning("목표 배분을 먼저 설정해주세요.")
        return
    
    # 옵션
    col1, col2 = st.columns(2)
    with col1:
        additional_cash = st.number_input("추가 투자금 ($)", min_value=0.0, step=100.0, value=0.0, key="rebal_cash")
    with col2:
        threshold = st.slider("리밸런싱 임계값 (%)", 1.0, 10.0, 2.0, 0.5, key="rebal_threshold",
                             help="이 비율 이상 차이나면 조정 권고")
    
    if st.button("🔄 리밸런싱 계산", use_container_width=True, key="calc_rebalance"):
        with st.spinner("계산 중..."):
            result = rebalance_calculator.calculate_rebalance(
                holdings, targets, additional_cash, threshold
            )
        
        # 요약
        summary = result['summary']
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("현재 포트폴리오", f"${result['total_value']:,.2f}")
        with col2:
            st.metric("매수 필요", f"{summary['buy_count']}건 / ${summary['total_buy_amount']:,.2f}")
        with col3:
            st.metric("매도 필요", f"{summary['sell_count']}건 / ${summary['total_sell_amount']:,.2f}")
        with col4:
            st.metric("순 필요 자금", f"${summary['net_cash_needed']:,.2f}")
        
        st.divider()
        
        # 액션 테이블
        actions_data = []
        for action in result['actions']:
            if action.action == "hold":
                action_icon = "⚪ 유지"
            elif action.action == "buy":
                action_icon = "🟢 매수"
            else:
                action_icon = "🔴 매도"
            
            actions_data.append({
                "우선순위": "⭐" * (4 - action.priority),
                "종목": action.ticker,
                "액션": action_icon,
                "현재": f"{action.current_percent:.1f}%",
                "목표": f"{action.target_percent:.1f}%",
                "차이": f"{action.diff_percent:+.1f}%",
                "주식수": f"{action.shares_to_trade}주",
                "예상금액": f"${abs(action.diff_value):,.2f}"
            })
        
        df = pd.DataFrame(actions_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 주문 리스트 생성
        orders = rebalance_calculator.generate_rebalance_orders(result['actions'])
        
        if orders:
            st.divider()
            st.markdown("**📋 실행 주문 리스트 (매도 우선):**")
            
            for order in orders:
                action_color = "🟢" if order['action'] == "BUY" else "🔴"
                st.markdown(f"""
                **{order['order']}.** {action_color} **{order['action']}** {order['ticker']} 
                - {order['shares']}주 @ ${order['estimated_price']:.2f} 
                ≈ **${order['estimated_amount']:.2f}**
                - *{order['reason']}*
                """)
        
        # 시장 상황 기반 제안
        st.divider()
        st.markdown("**💡 시장 상황 기반 제안:**")
        
        try:
            market_data = get_market_data()
            economic_cycle = get_economic_cycle()
            
            market_conditions = {
                'vix': market_data.get('market_data', {}).get('vix', {}).get('current', 20),
                'fear_greed': market_data.get('fear_greed_index', {}).get('current', 50),
                'economic_cycle': economic_cycle.get('current_phase', '확장기')
            }
            
            suggestions = rebalance_calculator.suggest_allocation_adjustments(
                {t['ticker']: t['target_percent'] for t in targets},
                market_conditions
            )
            
            if suggestions:
                for sug in suggestions:
                    priority_icon = "🔴" if sug['priority'] == 'high' else ("🟡" if sug['priority'] == 'medium' else "🟢")
                    st.info(f"{priority_icon} **{sug['reason']}**\n\n👉 {sug['suggestion']}")
            else:
                st.success("✅ 현재 시장 상황에서 특별한 조정이 필요하지 않습니다.")
        except Exception as e:
            st.warning(f"시장 데이터 로드 실패: {e}")


# ==================== 설정 페이지 ====================
def show_settings_page():
    """설정 페이지"""
    if not st.session_state.authenticated:
        st.warning("🔐 로그인이 필요합니다.")
        return
    
    user_id = st.session_state.user['id']
    st.header("⚙️ 설정")
    
    tab1, tab2, tab3 = st.tabs(["👤 계정 정보", "🔐 비밀번호 변경", "📁 포트폴리오 관리"])
    
    with tab1:
        st.subheader("👤 계정 정보")
        user = st.session_state.user
        
        st.markdown(f"""
        - **사용자명:** {user['username']}
        - **이메일:** {user.get('email', '-')}
        - **가입일:** {user.get('created_at', '-')}
        - **마지막 로그인:** {user.get('last_login', '-')}
        """)
    
    with tab2:
        st.subheader("🔐 비밀번호 변경")
        
        with st.form("change_password_form"):
            old_pwd = st.text_input("현재 비밀번호", type="password")
            new_pwd = st.text_input("새 비밀번호", type="password")
            confirm_pwd = st.text_input("새 비밀번호 확인", type="password")
            
            if st.form_submit_button("변경"):
                if not old_pwd or not new_pwd:
                    st.warning("모든 필드를 입력해주세요.")
                elif new_pwd != confirm_pwd:
                    st.error("새 비밀번호가 일치하지 않습니다.")
                elif len(new_pwd) < 4:
                    st.error("비밀번호는 4자 이상이어야 합니다.")
                else:
                    if db.change_password(user_id, old_pwd, new_pwd):
                        st.success("✅ 비밀번호가 변경되었습니다.")
                    else:
                        st.error("❌ 현재 비밀번호가 올바르지 않습니다.")
    
    with tab3:
        st.subheader("📁 포트폴리오 관리")
        
        portfolios = db.get_portfolios(user_id)
        
        if portfolios:
            for pf in portfolios:
                with st.expander(f"📂 {pf['name']}"):
                    st.markdown(f"- **설명:** {pf.get('description', '-')}")
                    st.markdown(f"- **생성일:** {pf.get('created_at', '-')}")
                    
                    # 삭제 버튼
                    if len(portfolios) > 1:  # 최소 1개는 유지
                        if st.button(f"🗑️ 삭제", key=f"delete_pf_{pf['id']}"):
                            db.delete_portfolio(pf['id'])
                            if st.session_state.selected_portfolio_id == pf['id']:
                                st.session_state.selected_portfolio_id = None
                            st.success(f"✅ '{pf['name']}' 포트폴리오가 삭제되었습니다.")
                            st.rerun()
                    else:
                        st.caption("(기본 포트폴리오는 삭제할 수 없습니다)")
        else:
            st.info("포트폴리오가 없습니다.")


if __name__ == "__main__":
    main()
