import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#90caf9' },
    secondary: { main: '#ce93d8' },
    background: {
      default: '#0a0e14',
      paper: '#111820',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    body2: { fontFamily: '"Roboto Mono", monospace' },
  },
  components: {
    MuiTableCell: {
      styleOverrides: {
        root: {
          padding: '6px 12px',
          fontSize: '0.8125rem',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        },
        head: {
          fontWeight: 600,
          textTransform: 'uppercase',
          fontSize: '0.6875rem',
          letterSpacing: '0.05em',
          color: 'rgba(255,255,255,0.5)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: 'none' },
      },
    },
  },
});
