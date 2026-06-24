import Database from 'better-sqlite3';
import { ListEntry, ListType } from '../../../shared/models';

interface ListEntryRow {
  id: number;
  symbol: string;
  list_type: string;
  reason: string | null;
  active: number;
  added_at: number;
}

export class ListRepository {
  constructor(private db: Database.Database) {}

  private toModel(row: ListEntryRow): ListEntry {
    return {
      id: row.id,
      symbol: row.symbol,
      listType: row.list_type as ListType,
      reason: row.reason,
      active: row.active === 1,
      addedAt: row.added_at,
    };
  }

  add(entry: Omit<ListEntry, 'id' | 'addedAt'>): ListEntry {
    const now = Math.floor(Date.now() / 1000);
    this.db
      .prepare(
        `INSERT INTO lists (symbol, list_type, reason, active, added_at)
         VALUES (?, ?, ?, ?, ?)
         ON CONFLICT(symbol, list_type) DO UPDATE SET
           reason   = excluded.reason,
           active   = excluded.active,
           added_at = excluded.added_at`,
      )
      .run(entry.symbol, entry.listType, entry.reason ?? null, entry.active ? 1 : 0, now);
    const row = this.db
      .prepare('SELECT * FROM lists WHERE symbol = ? AND list_type = ?')
      .get(entry.symbol, entry.listType) as ListEntryRow;
    return this.toModel(row);
  }

  getBySymbol(symbol: string): ListEntry[] {
    const rows = this.db
      .prepare('SELECT * FROM lists WHERE symbol = ? ORDER BY added_at DESC')
      .all(symbol) as ListEntryRow[];
    return rows.map((r) => this.toModel(r));
  }

  getByType(listType: ListType): ListEntry[] {
    const rows = this.db
      .prepare('SELECT * FROM lists WHERE list_type = ? ORDER BY added_at DESC')
      .all(listType) as ListEntryRow[];
    return rows.map((r) => this.toModel(r));
  }

  deactivate(symbol: string, listType: ListType): void {
    this.db
      .prepare('UPDATE lists SET active = 0 WHERE symbol = ? AND list_type = ?')
      .run(symbol, listType);
  }

  remove(symbol: string, listType: ListType): void {
    this.db
      .prepare('DELETE FROM lists WHERE symbol = ? AND list_type = ?')
      .run(symbol, listType);
  }

  isListed(symbol: string, listType: ListType): boolean {
    return (
      this.db
        .prepare('SELECT 1 FROM lists WHERE symbol = ? AND list_type = ? AND active = 1')
        .get(symbol, listType) !== undefined
    );
  }
}
