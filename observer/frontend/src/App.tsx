import { Box, Grid } from '@mui/material'
import StatusBar from './components/StatusBar/StatusBar.tsx'
import MarketPane from './components/MarketPane/MarketPane.tsx'
import RecsPane from './components/RecsPane/RecsPane.tsx'
import { useWebSocket } from './hooks/useWebSocket.ts'
import { useMarketData } from './hooks/useMarketData.ts'
import { useCandidates } from './hooks/useCandidates.ts'

function App() {
  const { status, reconnectCount, lastMessageAt, subscribe } = useWebSocket()
  const { quotes } = useMarketData(subscribe, reconnectCount)
  const { candidates, selectedId, selectedCandidate, select } = useCandidates(subscribe, reconnectCount)

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <StatusBar status={status} lastMessageAt={lastMessageAt} />
      <Grid container sx={{ flex: 1, overflow: 'hidden' }}>
        <Grid size={{ xs: 12, md: 5 }} sx={{ height: '100%', overflow: 'auto', p: 1 }}>
          <MarketPane quotes={quotes} />
        </Grid>
        <Grid size={{ xs: 12, md: 7 }} sx={{ height: '100%', overflow: 'auto', p: 1 }}>
          <RecsPane
            candidates={candidates}
            selectedId={selectedId}
            selectedCandidate={selectedCandidate}
            onSelect={select}
          />
        </Grid>
      </Grid>
    </Box>
  )
}

export default App
