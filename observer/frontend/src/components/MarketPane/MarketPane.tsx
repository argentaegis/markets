import { Paper, Typography } from '@mui/material';
import type { Quote } from '../../types/market.ts';
import WatchlistTable from './WatchlistTable.tsx';

interface MarketPaneProps {
  quotes: Record<string, Quote>;
}

export default function MarketPane({ quotes }: MarketPaneProps) {
  return (
    <Paper sx={{ p: 1.5, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Typography variant="subtitle2" sx={{ mb: 1, px: 0.5, color: 'text.secondary' }}>
        Watchlist
      </Typography>
      {Object.keys(quotes).length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
          Waiting for market data...
        </Typography>
      ) : (
        <WatchlistTable quotes={quotes} />
      )}
    </Paper>
  );
}
