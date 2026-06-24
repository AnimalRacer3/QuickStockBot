export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface LogEvent {
  id?: number;
  level: LogLevel;
  message: string;
  context?: Record<string, unknown> | null;
  occurredAt: number;
}
