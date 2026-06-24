import path from 'path';
import { openDatabase } from './connection';
import { runMigrations } from './migrations/runner';
import { seedDefaults } from './seed';

const dbPath = process.argv[2] ?? path.join(process.cwd(), 'data', 'quickstock.db');

const db = openDatabase(dbPath);
runMigrations(db);
seedDefaults(db);
db.close();

console.log(`Database initialized: ${dbPath}`);
console.log('Inspect with:  sqlite3 ' + dbPath + ' ".tables"');
