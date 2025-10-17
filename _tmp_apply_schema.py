import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='Report_Generator', user='cullyuser', password='L!ff3Yc4mPus')
conn.autocommit = True
cur = conn.cursor()
cur.execute("ALTER TABLE fds_reports ADD COLUMN IF NOT EXISTS system_architecture_json TEXT")
cur.execute("""
CREATE TABLE IF NOT EXISTS equipment_assets (
    id SERIAL PRIMARY KEY,
    model_key VARCHAR(200) UNIQUE NOT NULL,
    display_name VARCHAR(200),
    manufacturer VARCHAR(120),
    image_url VARCHAR(500),
    thumbnail_url VARCHAR(500),
    local_path VARCHAR(500),
    asset_source VARCHAR(120),
    confidence FLOAT,
    metadata_json TEXT,
    fetched_at TIMESTAMP,
    is_user_override BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
""")
cur.close()
conn.close()
print('DDL executed successfully.')
