import { memo, useEffect, useRef } from 'react';
import {
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
} from '@mui/material';
import type { Quote } from '../../types/market.ts';

const FLASH_MS = 400;

interface WatchlistRowProps {
  quote: Quote;
}

const WatchlistRow = memo(function WatchlistRow({ quote }: WatchlistRowProps) {
  const prevLastRef = useRef<number | null>(null);
  const rowRef = useRef<HTMLTableRowElement>(null);

  useEffect(() => {
    const prev = prevLastRef.current;
    prevLastRef.current = quote.last;

    if (prev === null || prev === quote.last || !rowRef.current) return;

    const color = quote.last > prev ? 'rgba(102,187,106,0.18)' : 'rgba(239,83,80,0.18)';
    const el = rowRef.current;
    el.style.backgroundColor = color;
    const timer = setTimeout(() => { el.style.backgroundColor = 'transparent'; }, FLASH_MS);
    return () => clearTimeout(timer);
  }, [quote.last]);

  return (
    <TableRow
      ref={rowRef}
      sx={{ transition: `background-color ${FLASH_MS}ms ease-out` }}
    >
      <TableCell sx={{ fontWeight: 600 }}>{quote.symbol}</TableCell>
      <TableCell align="right" sx={{ fontFamily: '"Roboto Mono", monospace' }}>
        {quote.last.toFixed(2)}
      </TableCell>
      <TableCell align="right" sx={{ fontFamily: '"Roboto Mono", monospace' }}>
        {quote.bid.toFixed(2)}
      </TableCell>
      <TableCell align="right" sx={{ fontFamily: '"Roboto Mono", monospace' }}>
        {quote.ask.toFixed(2)}
      </TableCell>
      <TableCell align="right" sx={{ fontFamily: '"Roboto Mono", monospace' }}>
        {quote.volume.toLocaleString()}
      </TableCell>
    </TableRow>
  );
});

interface WatchlistTableProps {
  quotes: Record<string, Quote>;
}

export default function WatchlistTable({ quotes }: WatchlistTableProps) {
  const symbols = Object.keys(quotes).sort();

  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Symbol</TableCell>
            <TableCell align="right">Last</TableCell>
            <TableCell align="right">Bid</TableCell>
            <TableCell align="right">Ask</TableCell>
            <TableCell align="right">Volume</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {symbols.map(sym => (
            <WatchlistRow key={sym} quote={quotes[sym]} />
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
