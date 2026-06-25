export interface DailyEfficiency {
  date: string;          // YYYY-MM-DD
  tradesToGoal: number;
  goalReached: boolean;
  dailyPnlPct: number;
  recordedAt: number;
}
