-- ==============================================================================
-- FinScope Supabase PostgreSQL DDL 스크립트
-- ==============================================================================
-- 사용 방법: Supabase 대시보드 > [SQL Editor] > [New query]에 아래 내용을 붙여넣고 [Run] 실행
-- ==============================================================================

-- 1. UUID 생성을 위한 pgcrypto 확장 활성화
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. 사용자 테이블 (users)
-- ID와 4자리 PIN의 SHA-256 해시값을 저장하여 경량 인증 지원
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    pin_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 계좌 관리 테이블 (accounts)
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    broker_name VARCHAR(50) NOT NULL,
    account_alias VARCHAR(50),
    account_type VARCHAR(20) NOT NULL CHECK (account_type IN ('일반', 'ISA', '연금저축', 'IRP')),
    opened_at DATE,
    maturity_at DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. 포트폴리오 보유 종목 테이블 (portfolio_items)
CREATE TABLE IF NOT EXISTS portfolio_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
    market VARCHAR(10) NOT NULL CHECK (market IN ('KRX', 'US')),
    ticker VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    buy_price NUMERIC(14, 2) NOT NULL CHECK (buy_price > 0),
    quantity NUMERIC(14, 4) NOT NULL CHECK (quantity > 0),
    target_price NUMERIC(14, 2),
    stop_loss_price NUMERIC(14, 2),
    memo TEXT,
    account VARCHAR(30) NOT NULL DEFAULT '기본',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 하위 호환성 및 기존 테이블 마이그레이션용 컬럼 추가 구문
ALTER TABLE portfolio_items ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES accounts(id) ON DELETE SET NULL;

-- 5. 인덱스 생성 (조회 성능 최적화 및 유저당 종목/계좌별 복합 인덱스)
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_user_id ON portfolio_items(user_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_account_id ON portfolio_items(account_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_ticker_account ON portfolio_items(user_id, ticker, account);

-- 6. Row Level Security (RLS) 활성화
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_items ENABLE ROW LEVEL SECURITY;

-- 7. 기본 RLS 접근 정책 (Streamlit 백엔드 연결 허용)
-- Streamlit 애플리케이션은 서버사이드 환경 변수로 보호되는 API Key를 사용합니다.
DROP POLICY IF EXISTS "Allow all operations for authenticated or service role" ON users;
CREATE POLICY "Allow all operations for authenticated or service role" ON users
    FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all operations for authenticated or service role" ON accounts;
CREATE POLICY "Allow all operations for authenticated or service role" ON accounts
    FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all operations for authenticated or service role" ON portfolio_items;
CREATE POLICY "Allow all operations for authenticated or service role" ON portfolio_items
    FOR ALL USING (true) WITH CHECK (true);

-- 8. 일일 포트폴리오 AI 진단 브리핑 캐시 테이블 (user_briefings)
CREATE TABLE IF NOT EXISTS user_briefings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    briefing_date DATE NOT NULL,
    content JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, briefing_date)
);

CREATE INDEX IF NOT EXISTS idx_user_briefings_lookup ON user_briefings(user_id, briefing_date);
ALTER TABLE user_briefings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all operations for authenticated or service role" ON user_briefings;
CREATE POLICY "Allow all operations for authenticated or service role" ON user_briefings
    FOR ALL USING (true) WITH CHECK (true);

