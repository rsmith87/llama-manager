# Llama Manager MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single FastAPI app that can run as a llama.cpp agent or controller.

**Architecture:** Use typed YAML config, dependency-injected FastAPI state, a local process manager for agent mode, and an HTTP-backed node registry for controller mode.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, httpx, psutil, PyYAML, pytest.

---

### Task 1: Project Skeleton

- [x] Create package directories, `pyproject.toml`, sample config, README, and design docs.

### Task 2: Config And Command Model

- [ ] Add tests for YAML loading and `llama-server` command construction.
- [ ] Implement `core/config.py` and `providers/llama_cpp.py`.

### Task 3: Process Manager

- [ ] Add tests using a fake subprocess factory.
- [ ] Implement lifecycle, status, and log tailing.

### Task 4: FastAPI Routes

- [ ] Add route tests for health, models, logs, and nodes.
- [ ] Implement app factory and routers.

### Task 5: Verification

- [ ] Run the full test suite.
- [ ] Review README against implemented behavior.

