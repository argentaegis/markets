import { useState } from 'react'
import { Box, Grid, Tab, Tabs } from '@mui/material'
import StatusBar from './components/StatusBar/StatusBar.tsx'
import MarketPane from './components/MarketPane/MarketPane.tsx'
import RecsPane from './components/RecsPane/RecsPane.tsx'
import BacktesterPane from './components/BacktesterPane/BacktesterPane.tsx'
import { useWebSocket } from './hooks/useWebSocket.ts'
import { useMarketData } from './hooks/useMarketData.ts'
import { useCandidates } from './hooks/useCandidates.ts'

function ObserverTab() {
  const { status, reconnectCount, lastMessageAt, subscribe } = useWebSocket()
  const { quotes } = useMarketData(subscribe, reconnectCount)
  const { candidates, selectedId, selectedCandidate, select } = useCandidates(subscribe, reconnectCount)

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
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

function App() {
  const [tab, setTab] = useState(0)

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tab label="Backtester" />
        <Tab label="Observer" />
      </Tabs>
      <Box sx={{ flex: 1, overflow: 'hidden' }}>
        {tab === 0 && <BacktesterPane />}
        {tab === 1 && <ObserverTab />}
      </Box>
    </Box>
  )
}

export default App
