import Database from 'better-sqlite3';
import { MlSample } from '../../../shared/models';

interface MlSampleRow {
  id: number;
  symbol: string;
  features: string;
  label: number | null;
  model_version: string | null;
  trade_id: string | null;
  sampled_at: number;
}

export class MlSampleRepository {
  constructor(private db: Database.Database) {}

  private toModel(row: MlSampleRow): MlSample {
    return {
      id: row.id,
      symbol: row.symbol,
      features: JSON.parse(row.features) as Record<string, number>,
      label: row.label,
      modelVersion: row.model_version,
      tradeId: row.trade_id,
      sampledAt: row.sampled_at,
    };
  }

  insert(sample: Omit<MlSample, 'id'>): MlSample {
    const sampledAt = sample.sampledAt ?? Math.floor(Date.now() / 1000);
    const result = this.db
      .prepare(
        `INSERT INTO ml_samples (symbol, features, label, model_version, trade_id, sampled_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
      )
      .run(
        sample.symbol,
        JSON.stringify(sample.features),
        sample.label ?? null,
        sample.modelVersion ?? null,
        sample.tradeId ?? null,
        sampledAt,
      );
    return {
      ...sample,
      id: result.lastInsertRowid as number,
      sampledAt,
      label: sample.label ?? null,
      modelVersion: sample.modelVersion ?? null,
      tradeId: sample.tradeId ?? null,
    };
  }

  getById(id: number): MlSample | null {
    const row = this.db
      .prepare('SELECT * FROM ml_samples WHERE id = ?')
      .get(id) as MlSampleRow | undefined;
    return row ? this.toModel(row) : null;
  }

  getUnlabeled(): MlSample[] {
    const rows = this.db
      .prepare('SELECT * FROM ml_samples WHERE label IS NULL ORDER BY sampled_at ASC')
      .all() as MlSampleRow[];
    return rows.map((r) => this.toModel(r));
  }

  setLabel(id: number, label: number): MlSample {
    this.db.prepare('UPDATE ml_samples SET label = ? WHERE id = ?').run(label, id);
    const sample = this.getById(id);
    if (!sample) throw new Error(`MlSample not found: ${id}`);
    return sample;
  }

  getByTradeId(tradeId: string): MlSample[] {
    const rows = this.db
      .prepare('SELECT * FROM ml_samples WHERE trade_id = ? ORDER BY sampled_at ASC')
      .all(tradeId) as MlSampleRow[];
    return rows.map((r) => this.toModel(r));
  }
}
