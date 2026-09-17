-- ==========================================
-- பழைய பத்திரிக்கை விற்பனை மேலாண்மை — Neon DB Schema
-- இதை Neon-ன் SQL Editor-ல் ஒரு முறை ரன் செய்யவும்
-- (இதுவே init_db() ஆல் தானாகவும் செய்யப்படும் — இது backup/manual option)
-- ==========================================

CREATE TABLE IF NOT EXISTS libraries (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    type TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sales_records (
    id SERIAL PRIMARY KEY,
    library_name TEXT NOT NULL,
    library_type TEXT DEFAULT '',
    period TEXT NOT NULL,
    rcnum TEXT DEFAULT '',
    letter_date TEXT DEFAULT '',
    weights JSONB DEFAULT '{}'::jsonb,
    quotes JSONB DEFAULT '[]'::jsonb,
    saved_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (library_name, period)
);

CREATE INDEX IF NOT EXISTS idx_sales_library ON sales_records (library_name);
CREATE INDEX IF NOT EXISTS idx_sales_period ON sales_records (period);
