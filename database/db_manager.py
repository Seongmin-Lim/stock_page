"""
📦 데이터베이스 관리자
SQLite / PostgreSQL 지원 - 환경 변수로 전환 가능
서버 배포 시 DATABASE_URL 환경 변수 설정하면 PostgreSQL 사용
"""
import sqlite3
import hashlib
import json
import os
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from contextlib import contextmanager

# 환경 변수에서 DB 설정 읽기
# 로컬: DATABASE_URL 없으면 SQLite 사용
# 서버: DATABASE_URL=postgresql://user:pass@host:port/dbname
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")

# SQLite 기본 경로
DB_PATH = os.path.join(os.path.dirname(__file__), "stock_app.db")

# PostgreSQL 사용 시 psycopg2 임포트
if USE_POSTGRES:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        print("✅ PostgreSQL 모드로 실행")
    except ImportError:
        print("⚠️ psycopg2가 설치되지 않음, SQLite로 전환")
        USE_POSTGRES = False


@dataclass
class User:
    """사용자 모델"""
    id: int
    username: str
    email: str
    created_at: str
    last_login: str


@dataclass
class Portfolio:
    """포트폴리오 모델"""
    id: int
    user_id: int
    name: str
    description: str
    created_at: str
    target_allocations: Dict[str, float]


@dataclass
class Trade:
    """거래 기록 모델"""
    id: int
    user_id: int
    portfolio_id: int
    ticker: str
    trade_type: str
    quantity: float
    price: float
    total_amount: float
    currency: str
    trade_date: str
    notes: str
    created_at: str


class DatabaseManager:
    """
    데이터베이스 관리자 (SQLite / PostgreSQL 지원)
    
    환경 변수:
    - DATABASE_URL: PostgreSQL 연결 문자열 (없으면 SQLite 사용)
      예: postgresql://user:password@localhost:5432/stock_db
    
    서버 배포 시:
    1. pip install psycopg2-binary
    2. DATABASE_URL 환경 변수 설정
    """
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.use_postgres = USE_POSTGRES
        self._init_db()
    
    @contextmanager
    def _get_connection(self):
        """데이터베이스 연결 컨텍스트 매니저"""
        if self.use_postgres:
            conn = psycopg2.connect(DATABASE_URL)
            try:
                yield conn
            finally:
                conn.close()
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()
    
    def _get_cursor(self, conn):
        """커서 반환"""
        if self.use_postgres:
            return conn.cursor(cursor_factory=RealDictCursor)
        return conn.cursor()
    
    def _param(self, idx: int = None) -> str:
        """파라미터 플레이스홀더 반환"""
        return "%s" if self.use_postgres else "?"
    
    def _init_db(self):
        """데이터베이스 초기화 (테이블 생성)"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            
            if self.use_postgres:
                # PostgreSQL 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(100) UNIQUE NOT NULL,
                        password_hash VARCHAR(64) NOT NULL,
                        email VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS portfolios (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        name VARCHAR(200) NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        target_allocations TEXT
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        portfolio_id INTEGER NOT NULL REFERENCES portfolios(id),
                        ticker VARCHAR(20) NOT NULL,
                        trade_type VARCHAR(10) NOT NULL,
                        quantity REAL NOT NULL,
                        price REAL NOT NULL,
                        total_amount REAL NOT NULL,
                        currency VARCHAR(10) DEFAULT 'USD',
                        trade_date DATE NOT NULL,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS target_allocations (
                        id SERIAL PRIMARY KEY,
                        portfolio_id INTEGER NOT NULL REFERENCES portfolios(id),
                        ticker VARCHAR(20) NOT NULL,
                        target_percent REAL NOT NULL,
                        asset_class VARCHAR(50),
                        notes TEXT,
                        UNIQUE(portfolio_id, ticker)
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_settings (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        setting_key VARCHAR(100) NOT NULL,
                        setting_value TEXT,
                        UNIQUE(user_id, setting_key)
                    )
                """)
            else:
                # SQLite 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        email TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        last_login TEXT
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS portfolios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        target_allocations TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        portfolio_id INTEGER NOT NULL,
                        ticker TEXT NOT NULL,
                        trade_type TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        price REAL NOT NULL,
                        total_amount REAL NOT NULL,
                        currency TEXT DEFAULT 'USD',
                        trade_date TEXT NOT NULL,
                        notes TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id),
                        FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS target_allocations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        portfolio_id INTEGER NOT NULL,
                        ticker TEXT NOT NULL,
                        target_percent REAL NOT NULL,
                        asset_class TEXT,
                        notes TEXT,
                        FOREIGN KEY (portfolio_id) REFERENCES portfolios(id),
                        UNIQUE(portfolio_id, ticker)
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        setting_key TEXT NOT NULL,
                        setting_value TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(id),
                        UNIQUE(user_id, setting_key)
                    )
                """)
            
            conn.commit()
    
    # ==================== 사용자 관리 ====================
    
    def _hash_password(self, password: str) -> str:
        """비밀번호 해시"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, username: str, password: str, email: str = "") -> Optional[int]:
        """사용자 생성"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            try:
                if self.use_postgres:
                    cursor.execute(f"""
                        INSERT INTO users (username, password_hash, email)
                        VALUES ({p}, {p}, {p})
                        RETURNING id
                    """, (username, self._hash_password(password), email))
                    row = cursor.fetchone()
                    user_id = row['id']
                else:
                    cursor.execute(f"""
                        INSERT INTO users (username, password_hash, email)
                        VALUES ({p}, {p}, {p})
                    """, (username, self._hash_password(password), email))
                    user_id = cursor.lastrowid
                
                conn.commit()
                
                # 기본 포트폴리오 생성
                self.create_portfolio(user_id, "기본 포트폴리오", "자동 생성된 기본 포트폴리오")
                
                return user_id
            except Exception:
                conn.rollback()
                return None  # 사용자명 중복
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """사용자 인증"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            cursor.execute(f"""
                SELECT id, username, email, created_at, last_login
                FROM users
                WHERE username = {p} AND password_hash = {p}
            """, (username, self._hash_password(password)))
            
            row = cursor.fetchone()
            
            if row:
                # 마지막 로그인 시간 업데이트
                user_id = row['id'] if isinstance(row, dict) else row[0]
                cursor.execute(f"""
                    UPDATE users SET last_login = {p} WHERE id = {p}
                """, (datetime.now().isoformat(), user_id))
                conn.commit()
                
                if isinstance(row, dict):
                    return row
                return {
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'created_at': row[3],
                    'last_login': row[4]
                }
            
            return None
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """비밀번호 변경"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            cursor.execute(f"""
                SELECT id FROM users WHERE id = {p} AND password_hash = {p}
            """, (user_id, self._hash_password(old_password)))
            
            if cursor.fetchone():
                cursor.execute(f"""
                    UPDATE users SET password_hash = {p} WHERE id = {p}
                """, (self._hash_password(new_password), user_id))
                conn.commit()
                return True
            
            return False
    
    # ==================== 포트폴리오 관리 ====================
    
    def create_portfolio(self, user_id: int, name: str, description: str = "") -> int:
        """포트폴리오 생성"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            if self.use_postgres:
                cursor.execute(f"""
                    INSERT INTO portfolios (user_id, name, description, target_allocations)
                    VALUES ({p}, {p}, {p}, {p})
                    RETURNING id
                """, (user_id, name, description, "{}"))
                row = cursor.fetchone()
                portfolio_id = row['id']
            else:
                cursor.execute(f"""
                    INSERT INTO portfolios (user_id, name, description, target_allocations)
                    VALUES ({p}, {p}, {p}, {p})
                """, (user_id, name, description, "{}"))
                portfolio_id = cursor.lastrowid
            
            conn.commit()
            return portfolio_id
    
    def get_portfolios(self, user_id: int) -> List[Dict]:
        """사용자의 모든 포트폴리오 조회"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            cursor.execute(f"""
                SELECT id, name, description, created_at, target_allocations
                FROM portfolios
                WHERE user_id = {p}
                ORDER BY created_at DESC
            """, (user_id,))
            
            portfolios = []
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    portfolios.append({
                        'id': row['id'],
                        'name': row['name'],
                        'description': row['description'],
                        'created_at': row['created_at'],
                        'target_allocations': json.loads(row['target_allocations'] or "{}")
                    })
                else:
                    portfolios.append({
                        'id': row[0],
                        'name': row[1],
                        'description': row[2],
                        'created_at': row[3],
                        'target_allocations': json.loads(row[4] or "{}")
                    })
            
            return portfolios
    
    def update_portfolio(self, portfolio_id: int, name: str = None, 
                        description: str = None, target_allocations: Dict = None):
        """포트폴리오 업데이트"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            updates = []
            params = []
            
            if name:
                updates.append(f"name = {p}")
                params.append(name)
            if description is not None:
                updates.append(f"description = {p}")
                params.append(description)
            if target_allocations is not None:
                updates.append(f"target_allocations = {p}")
                params.append(json.dumps(target_allocations))
            
            if updates:
                params.append(portfolio_id)
                cursor.execute(f"""
                    UPDATE portfolios SET {', '.join(updates)} WHERE id = {p}
                """, params)
                conn.commit()
    
    def delete_portfolio(self, portfolio_id: int):
        """포트폴리오 삭제"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            cursor.execute(f"DELETE FROM trades WHERE portfolio_id = {p}", (portfolio_id,))
            cursor.execute(f"DELETE FROM target_allocations WHERE portfolio_id = {p}", (portfolio_id,))
            cursor.execute(f"DELETE FROM portfolios WHERE id = {p}", (portfolio_id,))
            conn.commit()
    
    # ==================== 거래 기록 관리 ====================
    
    def add_trade(self, user_id: int, portfolio_id: int, ticker: str, 
                  trade_type: str, quantity: float, price: float,
                  trade_date: str, currency: str = "USD", notes: str = "") -> int:
        """거래 기록 추가"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            total_amount = quantity * price
            
            if self.use_postgres:
                cursor.execute(f"""
                    INSERT INTO trades 
                    (user_id, portfolio_id, ticker, trade_type, quantity, price, 
                     total_amount, currency, trade_date, notes)
                    VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                    RETURNING id
                """, (user_id, portfolio_id, ticker.upper(), trade_type, quantity, 
                      price, total_amount, currency, trade_date, notes))
                row = cursor.fetchone()
                trade_id = row['id']
            else:
                cursor.execute(f"""
                    INSERT INTO trades 
                    (user_id, portfolio_id, ticker, trade_type, quantity, price, 
                     total_amount, currency, trade_date, notes)
                    VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                """, (user_id, portfolio_id, ticker.upper(), trade_type, quantity, 
                      price, total_amount, currency, trade_date, notes))
                trade_id = cursor.lastrowid
            
            conn.commit()
            return trade_id
    
    def get_trades(self, user_id: int, portfolio_id: int = None, 
                   ticker: str = None, limit: int = 100) -> List[Dict]:
        """거래 기록 조회"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            query = f"SELECT * FROM trades WHERE user_id = {p}"
            params = [user_id]
            
            if portfolio_id:
                query += f" AND portfolio_id = {p}"
                params.append(portfolio_id)
            if ticker:
                query += f" AND ticker = {p}"
                params.append(ticker.upper())
            
            query += f" ORDER BY trade_date DESC, created_at DESC LIMIT {p}"
            params.append(limit)
            
            cursor.execute(query, params)
            
            trades = []
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    trades.append(row)
                else:
                    trades.append(dict(row))
            
            return trades
    
    def delete_trade(self, trade_id: int):
        """거래 기록 삭제"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            cursor.execute(f"DELETE FROM trades WHERE id = {p}", (trade_id,))
            conn.commit()
    
    def update_trade(self, trade_id: int, **kwargs):
        """거래 기록 수정"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            allowed_fields = ['ticker', 'trade_type', 'quantity', 'price', 
                              'trade_date', 'currency', 'notes']
            
            updates = []
            params = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = {p}")
                    params.append(value)
            
            # total_amount 재계산
            if 'quantity' in kwargs or 'price' in kwargs:
                cursor.execute(f"SELECT quantity, price FROM trades WHERE id = {p}", (trade_id,))
                row = cursor.fetchone()
                if row:
                    qty = kwargs.get('quantity', row['quantity'] if isinstance(row, dict) else row[0])
                    prc = kwargs.get('price', row['price'] if isinstance(row, dict) else row[1])
                    updates.append(f"total_amount = {p}")
                    params.append(qty * prc)
            
            if updates:
                params.append(trade_id)
                cursor.execute(f"""
                    UPDATE trades SET {', '.join(updates)} WHERE id = {p}
                """, params)
                conn.commit()
    
    # ==================== 보유 종목 계산 ====================
    
    def get_holdings(self, user_id: int, portfolio_id: int) -> List[Dict]:
        """포트폴리오의 현재 보유 종목 계산"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            cursor.execute(f"""
                SELECT 
                    ticker,
                    SUM(CASE WHEN trade_type = 'buy' THEN quantity ELSE -quantity END) as total_quantity,
                    SUM(CASE WHEN trade_type = 'buy' THEN total_amount ELSE -total_amount END) as net_cost
                FROM trades
                WHERE user_id = {p} AND portfolio_id = {p}
                GROUP BY ticker
                HAVING SUM(CASE WHEN trade_type = 'buy' THEN quantity ELSE -quantity END) > 0
            """, (user_id, portfolio_id))
            
            holdings = []
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    ticker = row['ticker']
                    quantity = row['total_quantity']
                    net_cost = row['net_cost']
                else:
                    ticker = row[0]
                    quantity = row[1]
                    net_cost = row[2]
                
                avg_price = net_cost / quantity if quantity > 0 else 0
                
                holdings.append({
                    'ticker': ticker,
                    'quantity': quantity,
                    'avg_price': avg_price,
                    'total_cost': net_cost
                })
            
            return holdings
    
    # ==================== 목표 배분 (리밸런싱) ====================
    
    def set_target_allocation(self, portfolio_id: int, ticker: str, 
                              target_percent: float, asset_class: str = "", notes: str = ""):
        """목표 배분 설정"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            if self.use_postgres:
                cursor.execute(f"""
                    INSERT INTO target_allocations 
                    (portfolio_id, ticker, target_percent, asset_class, notes)
                    VALUES ({p}, {p}, {p}, {p}, {p})
                    ON CONFLICT (portfolio_id, ticker) 
                    DO UPDATE SET target_percent = EXCLUDED.target_percent,
                                  asset_class = EXCLUDED.asset_class,
                                  notes = EXCLUDED.notes
                """, (portfolio_id, ticker.upper(), target_percent, asset_class, notes))
            else:
                cursor.execute(f"""
                    INSERT OR REPLACE INTO target_allocations 
                    (portfolio_id, ticker, target_percent, asset_class, notes)
                    VALUES ({p}, {p}, {p}, {p}, {p})
                """, (portfolio_id, ticker.upper(), target_percent, asset_class, notes))
            
            conn.commit()
    
    def get_target_allocations(self, portfolio_id: int) -> List[Dict]:
        """목표 배분 조회"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            cursor.execute(f"""
                SELECT ticker, target_percent, asset_class, notes
                FROM target_allocations
                WHERE portfolio_id = {p}
                ORDER BY target_percent DESC
            """, (portfolio_id,))
            
            allocations = []
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    allocations.append(row)
                else:
                    allocations.append({
                        'ticker': row[0],
                        'target_percent': row[1],
                        'asset_class': row[2],
                        'notes': row[3]
                    })
            
            return allocations
    
    def delete_target_allocation(self, portfolio_id: int, ticker: str):
        """목표 배분 삭제"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            cursor.execute(f"""
                DELETE FROM target_allocations 
                WHERE portfolio_id = {p} AND ticker = {p}
            """, (portfolio_id, ticker.upper()))
            conn.commit()
    
    # ==================== 사용자 설정 ====================
    
    def set_user_setting(self, user_id: int, key: str, value: Any):
        """사용자 설정 저장"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            if self.use_postgres:
                cursor.execute(f"""
                    INSERT INTO user_settings (user_id, setting_key, setting_value)
                    VALUES ({p}, {p}, {p})
                    ON CONFLICT (user_id, setting_key) 
                    DO UPDATE SET setting_value = EXCLUDED.setting_value
                """, (user_id, key, json.dumps(value)))
            else:
                cursor.execute(f"""
                    INSERT OR REPLACE INTO user_settings (user_id, setting_key, setting_value)
                    VALUES ({p}, {p}, {p})
                """, (user_id, key, json.dumps(value)))
            
            conn.commit()
    
    def get_user_setting(self, user_id: int, key: str, default: Any = None) -> Any:
        """사용자 설정 조회"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            cursor.execute(f"""
                SELECT setting_value FROM user_settings
                WHERE user_id = {p} AND setting_key = {p}
            """, (user_id, key))
            
            row = cursor.fetchone()
            
            if row:
                value = row['setting_value'] if isinstance(row, dict) else row[0]
                return json.loads(value)
            return default
    
    def get_all_user_settings(self, user_id: int) -> Dict:
        """모든 사용자 설정 조회"""
        with self._get_connection() as conn:
            cursor = self._get_cursor(conn)
            p = self._param()
            
            cursor.execute(f"""
                SELECT setting_key, setting_value FROM user_settings
                WHERE user_id = {p}
            """, (user_id,))
            
            settings = {}
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    settings[row['setting_key']] = json.loads(row['setting_value'])
                else:
                    settings[row[0]] = json.loads(row[1])
            
            return settings


# 전역 인스턴스
db = DatabaseManager()
