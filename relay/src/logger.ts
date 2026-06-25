const LEVELS = { debug: 0, info: 1, warning: 2, error: 3 } as const;
type Level = keyof typeof LEVELS;

const currentLevel: Level = (process.env.LOG_LEVEL as Level | undefined) ?? "info";

function log(level: Level, msg: string, ctx?: Record<string, unknown>): void {
  if (LEVELS[level] < LEVELS[currentLevel]) return;
  const line = ctx
    ? `[${level.toUpperCase()}] ${msg} ${JSON.stringify(ctx)}`
    : `[${level.toUpperCase()}] ${msg}`;
  if (level === "error") console.error(line);
  else console.log(line);
}

export const logger = {
  debug: (msg: string, ctx?: Record<string, unknown>) => log("debug", msg, ctx),
  info: (msg: string, ctx?: Record<string, unknown>) => log("info", msg, ctx),
  warn: (msg: string, ctx?: Record<string, unknown>) => log("warning", msg, ctx),
  error: (msg: string, ctx?: Record<string, unknown>) => log("error", msg, ctx),
};
