---
name: 120 Strategy Registry + Config
overview: "Implement dynamic strategy registry (auto-discover from strategies/ directory) and config.yaml for enabling/disabling strategies, per-strategy parameters, and watchlists. Wire specs from provider to MarketState. Test-first."
todos: []
isProject: false
---

# 120: Strategy Registry + Configuration

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) §strategies/ and §Strategy specification goals, M4 milestone.

---

## Project Practice: Test-First (Red-Green-Refactor)

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

---

## Objective

Make strategies pluggable without touching engine code:
1. **Dynamic registry** — auto-discover strategy classes from the `strategies/` directory via class-level `NAME` constant
2. **config.yaml** — enable/disable strategies, set per-strategy parameters, define watchlists (canonical symbols)
3. **Specs wiring** — pass provider contract specs to MarketState so strategies receive them via Context
4. A new strategy can be added by writing a Python file and enabling it in config

---

## Existing Foundation

- Step 050: BaseStrategy, Requirements, DummyStrategy
- Step 060: Engine accepts `list[BaseStrategy]`
- Step 110: ORB5mStrategy (accepts `symbols`, `min_range_ticks`, `max_range_ticks` kwargs)
- Step 110: Context/MarketState now support `specs: dict[str, ContractSpec]`

---

## Interface Contract

### Strategy NAME convention

Each concrete strategy must define a class-level `NAME` constant matching the key used in config.yaml. The existing `name` property returns `self.NAME`.

```python
class ORB5mStrategy(BaseStrategy):
    NAME = "orb_5m"

    @property
    def name(self) -> str:
        return self.NAME
```

The registry reads `cls.NAME` at discovery time — no instantiation needed to determine the config key.

### StrategyRegistry

```python
class StrategyRegistry:
    """Discovers and instantiates strategy classes from the strategies/ package.

    Reasoning: Strategies should be added by dropping a file in strategies/ and
    enabling in config.yaml. The engine should not need code changes to support
    new strategies.
    """

    def discover(self) -> dict[str, type[BaseStrategy]]:
        """Scan strategies/ for concrete BaseStrategy subclasses.

        Returns NAME -> class mapping. Ignores abstract classes, base.py, and
        __init__.py. Logs warnings for import errors.
        """

    def instantiate(
        self, config: AppConfig, discovered: dict[str, type[BaseStrategy]] | None = None,
    ) -> list[BaseStrategy]:
        """Create enabled strategy instances with configured params.

        For each enabled strategy in config:
        1. Look up class from discovered map (or call discover())
        2. Resolve watchlist name to symbol list
        3. Merge symbols into params dict
        4. Call constructor with **params unpacking

        Unknown strategy names in config produce warnings, not crashes.
        """
```

### config.yaml structure

```yaml
watchlists:
  futures_main:
    - ESH26
    - NQH26

strategies:
  orb_5m:
    enabled: true
    watchlist: futures_main
    params:
      min_range_ticks: 4
      max_range_ticks: 40

  dummy:
    enabled: false

engine:
  eval_timeframe: "5m"
  max_candidates_per_strategy: 10
```

Key design choices reflected:
- **No `provider:` key** — provider selection stays in `OBSERVER_PROVIDER` env var (deployment concern, not application config)
- **No `eval_timeframe` in strategy params** — strategies declare timeframes via `requirements().timeframes`; the engine owns the evaluation trigger
- **Watchlists use canonical symbols** (e.g., `ESH26` not `ES`) — contract roll resolution is out of scope for V1
- **`params` are unpacked as `**kwargs`** to strategy constructors — no need for strategies to accept a generic `params: dict`

### AppConfig

```python
@dataclass
class StrategyEntry:
    """Config for a single strategy."""
    enabled: bool = True
    watchlist: str | None = None
    params: dict[str, Any] = field(default_factory=dict)

@dataclass
class AppConfig:
    """Parsed application configuration."""
    engine: EngineConfig
    watchlists: dict[str, list[str]]
    strategies: dict[str, StrategyEntry]
```

### Defaults when config.yaml is absent

When no config file is found, `load_config()` returns sensible defaults that preserve current behavior:
- `engine`: `EngineConfig()` (eval_timeframe="5m", max_candidates_per_strategy=10)
- `watchlists`: `{"futures_main": ["ESH26"]}`
- `strategies`: `{"dummy": StrategyEntry(enabled=True)}` — DummyStrategy runs by default
- `ORB5mStrategy` is disabled by default (requires explicit enable in config)

---

## Module Layout

```
backend/src/strategies/
  __init__.py            # (existing, updated exports)
  base.py                # (existing, unchanged)
  dummy_strategy.py      # (existing, add NAME + optional symbols param)
  orb_5m.py              # (existing, add NAME)
  registry.py            # StrategyRegistry

backend/src/
  config.py              # load_config() -> AppConfig

backend/tests/unit/strategies/
  __init__.py            # (existing)
  conftest.py            # (existing)
  test_registry.py       # discovery + instantiation tests

backend/tests/unit/
  test_config.py         # config parsing tests

backend/
  config.yaml            # default config (gitignored)
  config.example.yaml    # documented example (committed)
```

---

## Implementation Phases

### Phase 0: Add NAME to existing strategies (prerequisite)

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: `DummyStrategy.NAME == "dummy"`, `ORB5mStrategy.NAME == "orb_5m"`. Test `DummyStrategy(symbols=["NQH26"])` uses configured symbols. |
| **Green** | Add `NAME = "dummy"` to DummyStrategy, `NAME = "orb_5m"` to ORB5mStrategy. Update `name` property to return `self.NAME`. Add optional `symbols` param to DummyStrategy constructor for watchlist support. |
| **Refactor** | Verify all existing strategy tests still pass (backward-compatible defaults). |

### Phase 1: Config loading

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_config.py`: load valid config.yaml -> typed AppConfig; missing file returns defaults; invalid YAML raises clear error; engine section maps to EngineConfig; strategy entries parse enabled/watchlist/params; watchlists parse to symbol lists; missing sections use defaults |
| **Green** | Implement `config.py`: `load_config(path: str | None = None) -> AppConfig`. Uses `OBSERVER_CONFIG` env var or `config.yaml` fallback. Parse YAML with pyyaml. Build typed AppConfig with EngineConfig, watchlists, strategy entries. |
| **Refactor** | Validation: unknown keys logged as warnings; missing required fields use defaults; empty strategies section returns empty dict |

### Phase 2: Strategy registry — discovery

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_registry.py`: `discover()` finds DummyStrategy and ORB5mStrategy; returns `{NAME: class}` mapping; ignores abstract BaseStrategy; ignores non-strategy Python files (`__init__.py`, `registry.py`); handles import errors gracefully (log, skip) |
| **Green** | Implement `registry.py`: scan `strategies` package for `.py` files using `importlib.import_module`; inspect each module for `BaseStrategy` subclasses with `NAME` attribute; skip abstract classes via `inspect.isabstract()` |
| **Refactor** | Handle edge cases: module with no strategy classes; module that imports but has no NAME attribute (log warning, skip) |

### Phase 3: Strategy registry — instantiation

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: `instantiate()` creates only enabled strategies; resolves watchlist to symbols and passes as `symbols` kwarg; merges watchlist-resolved symbols with other params; skips disabled strategies; unknown strategy name in config logs warning and is skipped; strategy with no watchlist gets no `symbols` kwarg (uses its own default) |
| **Green** | Implement `instantiate()`: for each enabled strategy in config, resolve watchlist, merge `symbols` into params, call `cls(**params)`. Catch `TypeError` on bad params and log warning. |
| **Refactor** | Clean separation: discovery is cacheable; instantiation is per-startup |

### Phase 4: Integration with app.py wiring

| Stage | Tasks |
|-------|-------|
| **Red** | Write integration test: load config -> discover -> instantiate -> pass to Engine with specs; verify only enabled strategies run; verify MarketState receives specs from provider |
| **Green** | Update `app.py` `_lifespan`: (1) call `load_config()`, (2) create registry and instantiate strategies, (3) build `EngineConfig` from config, (4) wire `MarketState(specs=provider.get_contract_specs())`, (5) pass strategies and config to Engine. Remove hardcoded `DummyStrategy()` import. Config file path from `OBSERVER_CONFIG` env var. |
| **Refactor** | Add `config.example.yaml` with documented sections. Add `config.yaml` to `.gitignore`. |

### Phase 5: Manual verification

| Stage | Tasks |
|-------|-------|
| **Green** | Create `config.yaml` enabling ORB5mStrategy. Start backend. Verify strategy runs (check logs for "ORB" messages). Toggle strategy disabled, restart, verify it does not run. |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Strategy name resolution | Class-level `NAME` constant | Readable at discovery without instantiation; explicit mapping to config keys |
| Discovery mechanism | importlib scan of strategies/ package | Simple; no plugin framework needed for V1 |
| Config format | YAML | Human-readable; pyyaml already a dependency |
| Param passing | `**params` unpacking to constructor | Preserves typed constructors; no boilerplate needed in strategies |
| Watchlist symbols | Canonical (ESH26, not ES) | Contract roll resolution is out of scope; avoids complex mapping layer |
| Provider selection | `OBSERVER_PROVIDER` env var only (not in config.yaml) | Deployment concern, not application config; avoids source-of-truth confusion |
| eval_timeframe location | Engine config only (not in strategy params) | Strategies declare needs via requirements(); engine owns the trigger |
| Unknown strategies in config | Log warning, skip | Don't crash on typos; user sees warning in logs |
| Config path | `OBSERVER_CONFIG` env var or `config.yaml` default | Flexible deployment |
| Missing config file | Return defaults (DummyStrategy enabled) | Preserves current behavior; zero-config development experience |
| Specs wiring | provider.get_contract_specs() -> MarketState(specs=...) | Strategies access specs via ctx.specs (established in step 110) |
| config.yaml | Gitignored (like .env) | User-specific config; config.example.yaml committed |

---

## Acceptance Criteria

- [ ] `DummyStrategy.NAME == "dummy"`, `ORB5mStrategy.NAME == "orb_5m"`
- [ ] `DummyStrategy` accepts optional `symbols` parameter
- [ ] All existing strategy tests pass unchanged
- [ ] `config.example.yaml` defines strategies, watchlists, engine config
- [ ] `config.yaml` added to `.gitignore`
- [ ] `load_config()` parses YAML into typed `AppConfig`
- [ ] `load_config()` returns sensible defaults when file is missing
- [ ] Invalid YAML raises clear error
- [ ] `StrategyRegistry.discover()` finds all concrete BaseStrategy subclasses via `NAME`
- [ ] `StrategyRegistry.discover()` ignores abstract base, __init__, registry module
- [ ] `StrategyRegistry.instantiate()` creates only enabled strategies with correct `**params`
- [ ] Watchlist name resolved to canonical symbol list and passed as `symbols` kwarg
- [ ] Unknown strategy names in config produce warnings, not crashes
- [ ] `app.py` uses registry + config instead of hardcoded strategy list
- [ ] `MarketState` initialized with `specs=provider.get_contract_specs()`
- [ ] Engine uses `EngineConfig` from parsed config
- [ ] Unit tests pass for config parsing, discovery, and instantiation
- [ ] Integration test: config -> registry -> engine pipeline

---

## Manual Verification

1. Create `backend/config.yaml` (copy from `config.example.yaml`):
   ```yaml
   watchlists:
     futures_main:
       - ESH26

   strategies:
     orb_5m:
       enabled: true
       watchlist: futures_main
       params:
         min_range_ticks: 4
         max_range_ticks: 40

     dummy:
       enabled: false

   engine:
     eval_timeframe: "5m"
     max_candidates_per_strategy: 10
   ```
2. Start backend:
   ```bash
   cd /Users/ajones/Code/observer/backend
   PYTHONPATH=src uvicorn api.app:create_app --factory --port 8000
   ```
3. Check logs: should see "Discovered strategies: dummy, orb_5m" and "Enabled: orb_5m"
4. Open frontend, verify ORB candidates appear (not Dummy candidates)
5. Edit config.yaml: set `dummy.enabled: true`, restart. Verify both strategies run.
6. Edit config.yaml: add `nonexistent_strategy: {enabled: true}`. Restart. Verify warning in logs, no crash.

---

## Data Flow

```
Startup:
  load_config(OBSERVER_CONFIG or "config.yaml")
    -> AppConfig {engine, watchlists, strategies}

  StrategyRegistry.discover()
    -> {"dummy": DummyStrategy, "orb_5m": ORB5mStrategy}

  StrategyRegistry.instantiate(config, discovered)
    -> resolve watchlists to symbols
    -> ORB5mStrategy(symbols=["ESH26"], min_range_ticks=4, max_range_ticks=40)
    -> [ORB5mStrategy instance]

  provider.get_contract_specs()
    -> {"ESH26": ContractSpec(...)}

  MarketState(specs=specs)
  Engine(strategies=strategies, state=state, config=engine_config)

Runtime (unchanged):
  Provider -> Engine.on_bar() -> Strategy.evaluate(ctx) -> candidates
```

---

## Out of Scope

- Hot-reload without restart (v2 — file watcher + dynamic reimport)
- YAML/DSL strategy definitions (000 explicitly defers to v2)
- Strategy versioning
- Per-strategy isolated logging
- Contract roll resolution (watchlists use canonical symbols)
- Provider selection in config.yaml (stays as env var)
