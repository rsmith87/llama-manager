# Quantization Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend quantization endpoints and wire the empty Quantization page to run llama.cpp quantize jobs on existing GGUF files.

**Architecture:** Add a dedicated `QuantizationManager` with the same subprocess/log pattern as `ConversionManager`. Mount a new `/quantizations` router and inject the manager through the existing app factory. Extend the static UI to fetch, render, start, and show logs for quantization jobs.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, subprocess, pytest, static HTML/CSS/JavaScript.

---

### Task 1: Backend Quantization Manager

**Files:**
- Create: `llama_manager/core/quantization_manager.py`
- Test: `tests/test_quantizations.py`

- [ ] Write failing tests that create temporary GGUF files, fake a `llama-quantize` binary, assert list payloads, start command construction, output naming, and log tailing.
- [ ] Run `uv run pytest tests/test_quantizations.py -v` and verify it fails because `llama_manager.core.quantization_manager` does not exist.
- [ ] Implement `QuantizationManager` with `list_files`, `status`, `start`, `tail_logs`, binary discovery, file-id lookup, safe quantization type validation, and output naming.
- [ ] Re-run `uv run pytest tests/test_quantizations.py -v` and verify it passes.

### Task 2: API Router and App Wiring

**Files:**
- Create: `llama_manager/api/routes_quantizations.py`
- Modify: `llama_manager/api/dependencies.py`
- Modify: `llama_manager/main.py`
- Test: `tests/test_api.py`

- [ ] Add failing API tests for `GET /quantizations/files`, `POST /quantizations/{id}/start`, `GET /quantizations/{id}`, and `GET /quantizations/{id}/logs`.
- [ ] Run `uv run pytest tests/test_api.py::test_quantization_routes -v` and verify it fails because routes are not mounted.
- [ ] Add `get_quantization_manager`, route handlers, app state wiring, and app factory injection.
- [ ] Re-run `uv run pytest tests/test_api.py::test_quantization_routes -v` and verify it passes.

### Task 3: Quantization UI

**Files:**
- Modify: `llama_manager/ui/index.html`
- Modify: `llama_manager/ui/app.js`
- Modify: `llama_manager/ui/styles.css`

- [ ] Add a quantization table body in `index.html`.
- [ ] Extend state and refresh flow to load `/quantizations/files`.
- [ ] Render rows with quant type select, output path, status, Quantize and Logs buttons.
- [ ] Add button handlers that POST `{ "type": selectedType }` and load logs into the shared log panel.
- [ ] Remove empty-only quantization CSS and keep responsive table behavior aligned with existing pages.

### Task 4: Verification

**Files:**
- Existing test suite

- [ ] Run `uv run pytest tests/test_quantizations.py tests/test_api.py -v`.
- [ ] Run `uv run pytest -v` if focused tests pass.
- [ ] Start the local server if needed and verify the Quantization page loads without console-visible markup errors.
