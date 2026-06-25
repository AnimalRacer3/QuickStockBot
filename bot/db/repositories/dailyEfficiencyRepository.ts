import Database from 'better-sqlite3';
import { DailyEfficiency } from '../../../shared/models';

interface DailyEfficiencyRow {
  date: string;
  trades_to_goal: number;
  goal_reached: number;
  daily_pnl_pct: number;
  recorded_at: number;
}

export class DailyEfficiencyRepository {
  constructor(private db: Database.Database) {}

  private toModel(row: DailyEfficiencyRow): DailyEfficiency {
    return {
      date: row.date,
      tradesToGoal: row.trades_to_goal,
      goalReached: row.goal_reached === 1,
      dailyPnlPct: row.daily_pnl_pct,
      recordedAt: row.recorded_at,
    };
  }

  upsert(record: Omit<DailyEfficiency, 'recordedAt'>): DailyEfficiency {
    const now = Math.floor(Date.now() / 1000);
    this.db
      .prepare(
        `INSERT INTO daily_efficiency
           (date, trades_to_goal, goal_reached, daily_pnl_pct, recorded_at)
         VALUES (?, ?, ?, ?, ?)
         ON CONFLICT(date) DO UPDATE SET
           trades_to_goal = excluded.trades_to_goal,
           goal_reached   = excluded.goal_reached,
           daily_pnl_pct  = excluded.daily_pnl_pct,
           recorded_at    = excluded.recorded_at`,
      )
      .run(
        record.date,
        record.tradesToGoal,
        record.goalReached ? 1 : 0,
        record.dailyPnlPct,
        now,
      );
    return this.getByDate(record.date)!;
  }

  getByDate(date: string): DailyEfficiency | null {
    const row = this.db
      .prepare('SELECT * FROM daily_efficiency WHERE date = ?')
      .get(date) as DailyEfficiencyRow | undefined;
    return row ? this.toModel(row) : null;
  }

  /** Return all records ordered by date ascending (oldest first). */
  getAll(): DailyEfficiency[] {
    const rows = this.db
      .prepare('SELECT * FROM daily_efficiency ORDER BY date ASC')
      .all() as DailyEfficiencyRow[];
    return rows.map((r) => this.toModel(r));
  }

  /** Return the N most-recent records (most recent first). */
  getRecent(n: number): DailyEfficiency[] {
    const rows = this.db
      .prepare('SELECT * FROM daily_efficiency ORDER BY date DESC LIMIT ?')
      .all(n) as DailyEfficiencyRow[];
    return rows.map((r) => this.toModel(r));
  }

  /** Fraction of days in the DB where the goal was reached. */
  hitRate(): number {
    const row = this.db
      .prepare(
        `SELECT COUNT(*) as total,
                SUM(goal_reached) as hits
         FROM daily_efficiency`,
      )
      .get() as { total: number; hits: number | null };

    if (!row.total) return 0;
    return (row.hits ?? 0) / row.total;
  }
}
