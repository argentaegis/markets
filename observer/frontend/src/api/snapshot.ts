import type { SnapshotResponse } from '../types/snapshot.ts';

export async function fetchSnapshot(): Promise<SnapshotResponse> {
  const resp = await fetch('/api/snapshot');
  if (!resp.ok) {
    throw new Error(`GET /api/snapshot failed: ${resp.status}`);
  }
  return resp.json() as Promise<SnapshotResponse>;
}
