import { useEffect, useRef } from 'react';
import { AppBar, Toolbar, Typography, Box, LinearProgress } from '@mui/material';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected';

const statusConfig: Record<ConnectionStatus, { color: string; label: string }> = {
  connecting: { color: '#ffa726', label: 'Reconnecting...' },
  connected: { color: '#66bb6a', label: 'Connected' },
  disconnected: { color: '#ef5350', label: 'Disconnected' },
};

const DRAIN_SECONDS = 5;

interface StatusBarProps {
  status: ConnectionStatus;
  lastMessageAt: number;
}

export default function StatusBar({ status, lastMessageAt }: StatusBarProps) {
  const { color, label } = statusConfig[status];
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = barRef.current?.querySelector('.MuiLinearProgress-bar') as HTMLElement | null;
    if (!el || lastMessageAt === 0) return;

    el.style.transition = 'none';
    el.style.transform = 'translateX(0%)';

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.style.transition = `transform ${DRAIN_SECONDS}s linear`;
        el.style.transform = 'translateX(-100%)';
      });
    });
  }, [lastMessageAt]);

  return (
    <Box>
      <AppBar position="static" elevation={0} sx={{ bgcolor: 'background.paper' }}>
        <Toolbar variant="dense" sx={{ minHeight: 40 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, flexGrow: 1 }}>
            Market Observer
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <FiberManualRecordIcon sx={{ fontSize: 10, color }} />
            <Typography variant="caption" sx={{ color }}>
              {label}
            </Typography>
          </Box>
        </Toolbar>
      </AppBar>
      <LinearProgress
        ref={barRef}
        variant="determinate"
        value={100}
        sx={{
          height: 2,
          bgcolor: 'rgba(255,255,255,0.06)',
          '& .MuiLinearProgress-bar': {
            bgcolor: 'rgba(255,255,255,0.15)',
            transition: 'none',
          },
        }}
      />
    </Box>
  );
}
