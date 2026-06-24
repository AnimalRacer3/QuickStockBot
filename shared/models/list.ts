export type ListType = 'whitelist' | 'blacklist';

export interface ListEntry {
  id?: number;
  symbol: string;
  listType: ListType;
  reason?: string | null;
  active: boolean;
  addedAt: number;
}
