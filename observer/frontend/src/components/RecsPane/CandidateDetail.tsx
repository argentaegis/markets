import {
  Box, Chip, Divider, List, ListItem, ListItemText,
  Paper, Typography,
} from '@mui/material';
import type { TradeCandidate } from '../../types/candidate.ts';

interface CandidateDetailProps {
  candidate: TradeCandidate;
}

export default function CandidateDetail({ candidate: c }: CandidateDetailProps) {
  const mono = { fontFamily: '"Roboto Mono", monospace' };

  return (
    <Paper variant="outlined" sx={{ mt: 1, p: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mb: 1 }}>
        <Typography variant="subtitle2">
          {c.symbol} — {c.strategy}
        </Typography>
        <Typography
          variant="body2"
          sx={{ color: c.direction === 'LONG' ? '#66bb6a' : '#ef5350', fontWeight: 700 }}
        >
          {c.direction} ({c.entry_type})
        </Typography>
      </Box>

      <Divider sx={{ mb: 1.5 }} />

      <Box sx={{ display: 'flex', gap: 4, mb: 1.5 }}>
        <Box>
          <Typography variant="caption" color="text.secondary">Entry</Typography>
          <Typography variant="body2" sx={mono}>{c.entry_price.toFixed(2)}</Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Stop</Typography>
          <Typography variant="body2" sx={{ ...mono, color: '#ef5350' }}>
            {c.stop_price.toFixed(2)}
          </Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Targets</Typography>
          <Typography variant="body2" sx={{ ...mono, color: '#66bb6a' }}>
            {c.targets.map(t => t.toFixed(2)).join(' / ')}
          </Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Score</Typography>
          <Typography variant="body2" sx={mono}>{c.score.toFixed(0)}</Typography>
        </Box>
      </Box>

      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
        Reasoning
      </Typography>
      <List dense disablePadding>
        {c.explain.map((line, i) => (
          <ListItem key={i} disableGutters sx={{ py: 0 }}>
            <ListItemText
              primary={`• ${line}`}
              primaryTypographyProps={{ variant: 'body2' }}
            />
          </ListItem>
        ))}
      </List>

      {Object.keys(c.tags).length > 0 && (
        <Box sx={{ mt: 1, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {Object.entries(c.tags).map(([k, v]) => (
            <Chip key={k} label={`${k}: ${v}`} size="small" variant="outlined" />
          ))}
        </Box>
      )}

      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
        Created: {new Date(c.created_at).toLocaleString()} · Valid until: {new Date(c.valid_until).toLocaleString()}
      </Typography>
    </Paper>
  );
}
