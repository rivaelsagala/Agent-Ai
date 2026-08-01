CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS market_news;

CREATE TABLE IF NOT EXISTS market_news.news_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    base_url TEXT NOT NULL,
    source_type VARCHAR(30) NOT NULL CHECK (
        source_type IN (
            'idx_disclosure',
            'idx_news',
            'ojk',
            'bank_indonesia',
            'media'
        )
    ),
    fetch_method VARCHAR(20) NOT NULL DEFAULT 'html'
        CHECK (fetch_method IN ('api', 'rss', 'html')),
    is_official BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    poll_interval_minutes INTEGER NOT NULL DEFAULT 15
        CHECK (poll_interval_minutes > 0),
    last_cursor TEXT,
    last_fetched_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_news.securities (
    ticker VARCHAR(15) PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    sector VARCHAR(150),
    subsector VARCHAR(150),
    listing_board VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_news.news_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES market_news.news_sources(id),
    external_id VARCHAR(255),
    canonical_url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    source_excerpt TEXT,
    published_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    summary TEXT,
    impact_reason TEXT,
    category VARCHAR(50) CHECK (
        category IS NULL OR category IN (
            'disclosure',
            'financial_report',
            'corporate_action',
            'regulation',
            'monetary_policy',
            'market_event',
            'general'
        )
    ),
    impact_level SMALLINT CHECK (impact_level BETWEEN 1 AND 5),
    sentiment NUMERIC(4, 3) CHECK (sentiment BETWEEN -1 AND 1),
    confidence NUMERIC(4, 3) CHECK (confidence BETWEEN 0 AND 1),
    processing_status VARCHAR(20) NOT NULL DEFAULT 'new' CHECK (
        processing_status IN ('new', 'processing', 'processed', 'ignored', 'failed')
    ),
    content_hash CHAR(64) NOT NULL,
    raw_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    llm_model VARCHAR(100),
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_news_items_published_at
    ON market_news.news_items (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_items_processing
    ON market_news.news_items (processing_status, collected_at);
CREATE INDEX IF NOT EXISTS idx_news_items_impact
    ON market_news.news_items (impact_level DESC, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_items_content_hash
    ON market_news.news_items (content_hash);

CREATE TABLE IF NOT EXISTS market_news.news_securities (
    news_id UUID NOT NULL REFERENCES market_news.news_items(id) ON DELETE CASCADE,
    ticker VARCHAR(15) NOT NULL
        REFERENCES market_news.securities(ticker) ON DELETE CASCADE,
    relevance_score NUMERIC(4, 3) CHECK (relevance_score BETWEEN 0 AND 1),
    match_method VARCHAR(20) NOT NULL DEFAULT 'rule'
        CHECK (match_method IN ('rule', 'llm', 'manual')),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (news_id, ticker)
);

CREATE INDEX IF NOT EXISTS idx_news_securities_ticker
    ON market_news.news_securities (ticker, news_id);

CREATE TABLE IF NOT EXISTS market_news.subscribers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name VARCHAR(150) NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Jakarta',
    language VARCHAR(10) NOT NULL DEFAULT 'id',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_news.notification_channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id UUID NOT NULL
        REFERENCES market_news.subscribers(id) ON DELETE CASCADE,
    channel_type VARCHAR(20) NOT NULL
        CHECK (channel_type IN ('telegram', 'whatsapp', 'email')),
    destination TEXT NOT NULL,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    consented_at TIMESTAMPTZ,
    channel_config JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (subscriber_id, channel_type, destination)
);

CREATE TABLE IF NOT EXISTS market_news.watchlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id UUID NOT NULL
        REFERENCES market_news.subscribers(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL DEFAULT 'Default',
    receive_all BOOLEAN NOT NULL DEFAULT FALSE,
    minimum_impact SMALLINT NOT NULL DEFAULT 3
        CHECK (minimum_impact BETWEEN 1 AND 5),
    instant_notification BOOLEAN NOT NULL DEFAULT TRUE,
    digest_notification BOOLEAN NOT NULL DEFAULT TRUE,
    digest_time TIME NOT NULL DEFAULT '17:00:00',
    categories TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_news.watchlist_securities (
    watchlist_id UUID NOT NULL
        REFERENCES market_news.watchlists(id) ON DELETE CASCADE,
    ticker VARCHAR(15) NOT NULL
        REFERENCES market_news.securities(ticker) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (watchlist_id, ticker)
);

CREATE TABLE IF NOT EXISTS market_news.notification_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL
        REFERENCES market_news.notification_channels(id) ON DELETE CASCADE,
    delivery_type VARCHAR(20) NOT NULL
        CHECK (delivery_type IN ('instant', 'digest', 'test')),
    dedupe_key VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'processing', 'sent', 'failed', 'cancelled')
    ),
    message_text TEXT,
    provider_message_id VARCHAR(255),
    error_message TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    next_retry_at TIMESTAMPTZ,
    locked_at TIMESTAMPTZ,
    locked_by VARCHAR(100),
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_pending
    ON market_news.notification_deliveries (
        status, scheduled_at, next_retry_at
    );

CREATE TABLE IF NOT EXISTS market_news.delivery_items (
    delivery_id UUID NOT NULL
        REFERENCES market_news.notification_deliveries(id) ON DELETE CASCADE,
    news_id UUID NOT NULL
        REFERENCES market_news.news_items(id) ON DELETE CASCADE,
    display_order INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (delivery_id, news_id)
);

CREATE TABLE IF NOT EXISTS market_news.source_poll_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL
        REFERENCES market_news.news_sources(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('running', 'success', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    fetched_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE INDEX IF NOT EXISTS idx_source_poll_runs
    ON market_news.source_poll_runs (source_id, started_at DESC);

INSERT INTO market_news.news_sources (
    code, name, base_url, source_type, fetch_method, is_official
)
VALUES
    (
        'IDX_DISCLOSURE',
        'Keterbukaan Informasi BEI',
        'https://www.idx.id/id/perusahaan-tercatat/keterbukaan-informasi',
        'idx_disclosure',
        'html',
        TRUE
    ),
    (
        'IDX_NEWS',
        'Siaran Pers BEI',
        'https://www.idx.id/id/berita/siaran-pers/',
        'idx_news',
        'html',
        TRUE
    ),
    (
        'OJK_PRESS',
        'Siaran Pers OJK',
        'https://www.ojk.go.id/id/berita-dan-kegiatan/siaran-pers/Default.aspx',
        'ojk',
        'html',
        TRUE
    ),
    (
        'BI_PRESS',
        'Siaran Pers Bank Indonesia',
        'https://www.bi.go.id/id/publikasi/ruang-media/news-release/Default.aspx',
        'bank_indonesia',
        'html',
        TRUE
    )
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    base_url = EXCLUDED.base_url,
    source_type = EXCLUDED.source_type,
    is_official = EXCLUDED.is_official,
    updated_at = NOW();
