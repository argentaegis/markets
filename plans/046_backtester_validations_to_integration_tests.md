---
name: 046 Validations to Integration Tests
overview: Convert validation scripts to pytest integration tests. Complete.
todos: []
isProject: false
---

# 046: Validations to Project-Level Integration Tests

Converted the four validation scripts into pytest integration tests. Validations are now in `tests/integration/`.

---

## Result

| Former validation | Integration test |
|-------------------|------------------|
| validation.run | tests/integration/test_dataprovider.py |
| validation.domain_clock | tests/integration/test_domain_clock.py |
| validation.underlying | tests/integration/test_underlying.py |
| validation.options | tests/integration/test_options.py |

---

## Run

```bash
pytest tests/integration              # All integration tests
pytest tests/integration -m "not network"   # CI-safe (skips underlying, options)
pytest tests/integration -m network    # Only network tests
```

---

## Custom data validation

Set `VALIDATION_DATA_PATH` to a folder with `underlying/` and `options/` subdirs, then:

```bash
pytest tests/integration/test_dataprovider.py
```
