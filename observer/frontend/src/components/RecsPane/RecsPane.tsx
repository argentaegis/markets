import { Paper, Typography } from '@mui/material';
import type { TradeCandidate } from '../../types/candidate.ts';
import CandidateTable from './CandidateTable.tsx';
import CandidateDetail from './CandidateDetail.tsx';

interface RecsPaneProps {
  candidates: TradeCandidate[];
  selectedId: string | null;
  selectedCandidate: TradeCandidate | null;
  onSelect: (id: string | null) => void;
}

export default function RecsPane({ candidates, selectedId, selectedCandidate, onSelect }: RecsPaneProps) {
  return (
    <Paper sx={{ p: 1.5, height: '100%', display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
      <Typography variant="subtitle2" sx={{ mb: 1, px: 0.5, color: 'text.secondary' }}>
        Recommendations
      </Typography>

      {candidates.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
          No active candidates
        </Typography>
      ) : (
        <>
          <CandidateTable
            candidates={candidates}
            selectedId={selectedId}
            onSelect={onSelect}
          />
          {selectedCandidate && (
            <CandidateDetail candidate={selectedCandidate} />
          )}
        </>
      )}
    </Paper>
  );
}
