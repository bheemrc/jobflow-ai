import { Pool, types } from "pg";

// Return timestamps as strings instead of Date objects
types.setTypeParser(1114, (val: string) => val); // timestamp without tz
types.setTypeParser(1184, (val: string) => val); // timestamptz

let pool: Pool | null = null;
let tablesEnsured = false;

function getPool(): Pool {
  if (!pool) {
    pool = new Pool({
      connectionString: import.meta.env.DATABASE_URL || process.env.DATABASE_URL,
    });
  }
  return pool;
}

async function maybeEnsureTables(): Promise<void> {
  if (tablesEnsured) return;
  tablesEnsured = true;
  try {
    await ensureTables();
  } catch (err) {
    tablesEnsured = false;
    console.error("Failed to ensure tables:", (err as Error).message);
  }
}

export async function query<T = Record<string, unknown>>(
  sql: string,
  params?: unknown[]
): Promise<T[]> {
  await maybeEnsureTables();
  const result = await getPool().query(sql, params);
  return result.rows as T[];
}

export async function queryOne<T = Record<string, unknown>>(
  sql: string,
  params?: unknown[]
): Promise<T | null> {
  await maybeEnsureTables();
  const result = await getPool().query(sql, params);
  return (result.rows[0] as T) ?? null;
}

export async function execute(
  sql: string,
  params?: unknown[]
): Promise<{ rowCount: number }> {
  await maybeEnsureTables();
  const result = await getPool().query(sql, params);
  return { rowCount: result.rowCount ?? 0 };
}

async function ensureTables(): Promise<void> {
  const p = getPool();
  await p.query(`
    CREATE TABLE IF NOT EXISTS search_history (
      id SERIAL PRIMARY KEY,
      user_id TEXT NOT NULL DEFAULT '',
      search_term TEXT NOT NULL,
      location TEXT NOT NULL DEFAULT '',
      is_remote BOOLEAN NOT NULL DEFAULT FALSE,
      site_name TEXT NOT NULL DEFAULT '',
      results_count INTEGER NOT NULL DEFAULT 0,
      searched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_search_history_term ON search_history(search_term);
    CREATE INDEX IF NOT EXISTS idx_search_history_date ON search_history(searched_at);
    CREATE INDEX IF NOT EXISTS idx_search_history_user_id ON search_history(user_id);
  `);

  // Composite unique index on saved_jobs (user_id, job_url)
  await p.query(`
    DO $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'saved_jobs' AND indexname = 'saved_jobs_job_url_key'
      ) THEN
        ALTER TABLE saved_jobs DROP CONSTRAINT saved_jobs_job_url_key;
      END IF;
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END $$;
  `);

  await p.query(`
    CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_jobs_user_url ON saved_jobs(user_id, job_url);
    CREATE INDEX IF NOT EXISTS idx_saved_jobs_user_id ON saved_jobs(user_id);
  `);
}
