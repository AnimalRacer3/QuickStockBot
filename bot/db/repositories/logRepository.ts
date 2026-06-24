import Database from 'better-sqlite3';
import { LogEvent, LogLevel } from '../../../shared/models';

interface LogEventRow {
  id: number;
  level: string;
  message: string;
  context: string | null;
  occurred_at: number;
}

export class LogRepository {
  constructor(private db: Database.Database) {}

  private toModel(row: LogEventRow): LogEvent {
    return {
      id: row.id,
      level: row.level as LogLevel,
      message: row.message,
      context: row.context ? (JSON.parse(row.context) as Record<string, unknown>) : null,
      occurredAt: row.occurred_at,
    };
  }

  insert(event: Omit<LogEvent, 'id'>): LogEvent {
    const occurredAt = event.occurredAt ?? Math.floor(Date.now() / 1000);
    const result = this.db
      .prepare(
        `INSERT INTO log_events (level, message, context, occurred_at)
         VALUES (?, ?, ?, ?)`,
      )
      .run(
        event.level,
        event.message,
        event.context ? JSON.stringify(event.context) : null,
        occurredAt,
      );
    return { ...event, id: result.lastInsertRowid as number, occurredAt };
  }

  getRecent(limit = 100): LogEvent[] {
    const rows = this.db
      .prepare('SELECT * FROM log_events ORDER BY occurred_at DESC, id DESC LIMIT ?')
      .all(limit) as LogEventRow[];
    return rows.map((r) => this.toModel(r));
  }

  getByLevel(level: LogLevel): LogEvent[] {
    const rows = this.db
      .prepare('SELECT * FROM log_events WHERE level = ? ORDER BY occurred_at DESC, id DESC')
      .all(level) as LogEventRow[];
    return rows.map((r) => this.toModel(r));
  }
}
