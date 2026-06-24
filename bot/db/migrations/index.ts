import { migration001 } from './001_initial_schema';

export interface Migration {
  version: number;
  name: string;
  sql: string;
}

export const migrations: Migration[] = [migration001];
