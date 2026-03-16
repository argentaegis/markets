import { useState, useEffect } from 'react'
import {
  Box,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Paper,
  CircularProgress,
} from '@mui/material'

interface ConfigEntry {
  name: string
  path: string
  label: string
}

interface RunResult {
  ok: boolean
  config_path?: string
  run_dir?: string
  report_path?: string
  summary_path?: string
  detail?: string
}

function BacktesterPane() {
  const [configs, setConfigs] = useState<ConfigEntry[]>([])
  const [selectedPath, setSelectedPath] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RunResult | null>(null)
  const [configError, setConfigError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/backtester/configs')
      .then((r) => r.json())
      .then((data) => {
        setConfigs(data.configs || [])
        if (data.configs?.length && !selectedPath) {
          setSelectedPath(data.configs[0].path)
        }
      })
      .catch((e) => setConfigError(String(e)))
  }, [selectedPath])

  const handleRun = () => {
    if (!selectedPath) return
    setLoading(true)
    setResult(null)
    fetch('/api/backtester/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config_path: selectedPath }),
    })
      .then(async (r) => {
        const data = await r.json().catch(() => ({}))
        if (!r.ok) {
          throw new Error(data.detail || r.statusText)
        }
        setResult(data)
      })
      .catch((e) => setResult({ ok: false, detail: String(e) }))
      .finally(() => setLoading(false))
  }

  return (
    <Box sx={{ p: 2, maxWidth: 640 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Backtester
      </Typography>

      {configError && (
        <Typography color="error" sx={{ mb: 2 }}>
          Could not load configs: {configError}
        </Typography>
      )}

      <FormControl fullWidth sx={{ mb: 2 }}>
        <InputLabel>Config</InputLabel>
        <Select
          value={selectedPath}
          label="Config"
          onChange={(e) => setSelectedPath(e.target.value)}
        >
          {configs.map((c) => (
            <MenuItem key={c.path} value={c.path}>
              {c.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Button
        variant="contained"
        onClick={handleRun}
        disabled={loading || !selectedPath}
        sx={{ mb: 2 }}
        startIcon={loading ? <CircularProgress size={18} color="inherit" /> : undefined}
      >
        {loading ? 'Running…' : 'Run'}
      </Button>

      {result && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          {result.ok ? (
            <>
              <Typography color="success.main" sx={{ mb: 1 }}>
                Run completed
              </Typography>
              <Typography variant="body2">Config: {result.config_path}</Typography>
              <Typography variant="body2">Output: {result.run_dir}</Typography>
              {result.report_path && (
                <Typography variant="body2" sx={{ mt: 1 }}>
                  <a
                    href={`/${result.report_path}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open report
                  </a>
                </Typography>
              )}
            </>
          ) : (
            <Typography color="error">{result.detail || 'Run failed'}</Typography>
          )}
        </Paper>
      )}
    </Box>
  )
}

export default BacktesterPane
