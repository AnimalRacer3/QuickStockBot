import { migration001 } from './001_initial_schema';
import { migration002 } from './002_section04_ta';
import { migration003 } from './003_section05_scanner';
import { migration004 } from './004_section08_control';

export interface Migration {
  version: number;
  name: string;
  sql: string;
}

export const migrations: Migration[] = [migration001, migration002, migration003, migration004];
