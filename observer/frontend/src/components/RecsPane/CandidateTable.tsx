import { useState } from 'react';
import {
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  TableSortLabel, Tooltip, Typography,
} from '@mui/material';
import type { TradeCandidate } from '../../types/candidate.ts';

type SortDir = 'asc' | 'desc';

interface CandidateTableProps {
  candidates: TradeCandidate[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export default function CandidateTable({ candidates, selectedId, onSelect }: CandidateTableProps) {
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const sorted = [...candidates].sort((a, b) =>
    sortDir === 'desc' ? b.score - a.score : a.score - b.score
  );

  const toggleSort = () => setSortDir(prev => prev === 'desc' ? 'asc' : 'desc');

  const mono = { fontFamily: '"Roboto Mono", monospace' };

  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Symbol</TableCell>
            <TableCell>Strategy</TableCell>
            <TableCell>Dir</TableCell>
            <TableCell align="right">Entry</TableCell>
            <TableCell align="right">Stop</TableCell>
            <TableCell align="right">Target</TableCell>
            <TableCell align="right" sortDirection={sortDir}>
              <TableSortLabel active direction={sortDir} onClick={toggleSort}>
                Score
              </TableSortLabel>
            </TableCell>
            <TableCell>Valid Until</TableCell>
            <TableCell>Why</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {sorted.map(c => {
            const isSelected = c.id === selectedId;
            const whyPreview = c.explain.slice(0, 2).join('; ');
            const validTime = new Date(c.valid_until).toLocaleTimeString();

            return (
              <TableRow
                key={c.id}
                hover
                selected={isSelected}
                onClick={() => onSelect(c.id)}
                sx={{ cursor: 'pointer' }}
              >
                <TableCell sx={{ fontWeight: 600 }}>{c.symbol}</TableCell>
                <TableCell>{c.strategy}</TableCell>
                <TableCell>
                  <Typography
                    variant="body2"
                    component="span"
                    sx={{
                      color: c.direction === 'LONG' ? '#66bb6a' : '#ef5350',
                      fontWeight: 600,
                      fontSize: 'inherit',
                    }}
                  >
                    {c.direction}
                  </Typography>
                </TableCell>
                <TableCell align="right" sx={mono}>{c.entry_price.toFixed(2)}</TableCell>
                <TableCell align="right" sx={mono}>{c.stop_price.toFixed(2)}</TableCell>
                <TableCell align="right" sx={mono}>
                  {c.targets.length > 0 ? c.targets[0].toFixed(2) : '—'}
                </TableCell>
                <TableCell align="right" sx={mono}>{c.score.toFixed(0)}</TableCell>
                <TableCell sx={{ fontSize: '0.75rem' }}>{validTime}</TableCell>
                <TableCell sx={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  <Tooltip title={c.explain.join(' • ')}>
                    <span>{whyPreview}</span>
                  </Tooltip>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
