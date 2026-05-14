# Quantization Page Design

## Goal

Add a first version of GGUF quantization to the app. Users can select an existing `.gguf` file discovered under configured HF model roots, choose a quantization type, start a llama.cpp quantize job, and inspect logs from the existing log panel.

## Architecture

Use a dedicated `QuantizationManager` instead of extending conversion or library code. The manager owns GGUF source discovery, output naming, subprocess launch, in-memory job status, and log tailing. FastAPI exposes this through a new `/quantizations` router.

The UI replaces the empty Quantization page with a table that mirrors existing conversion and library patterns. It loads quantization rows during refresh, posts start requests, and routes log output to the existing shared log panel.

## Backend Contract

- `GET /quantizations/files` returns quantizable source GGUF files and job metadata.
- `GET /quantizations/{file_id}` returns one file's current status.
- `POST /quantizations/{file_id}/start` starts quantization with JSON body `{ "type": "Q4_K_M" }`.
- `GET /quantizations/{file_id}/logs?lines=200` returns `{ "id": "...", "text": "..." }`.

The manager searches for a quantize binary in `<llama_cpp_dir>/build/bin/llama-quantize`, `<llama_cpp_dir>/llama-quantize`, and the configured `llama_cpp_dir` equivalent binary location. The command is:

```text
llama-quantize <input.gguf> <output.gguf> <type>
```

## Output Naming

Quantized files are written next to the source file. If the selected type is `Q4_K_M`, `model.gguf` becomes `model-Q4_K_M.gguf`. Existing output files are reported and the first version may overwrite only when llama.cpp itself allows it; the UI simply shows the expected output path.

## UI Behavior

Rows show source model folder, source filename, size, selected quant type, expected output, status, and actions. Supported first-version types are `Q4_K_M`, `Q5_K_M`, `Q8_0`, `Q6_K`, `Q3_K_M`, and `Q2_K`.

## Error Handling

Unknown file IDs return 404. Missing source files or missing quantize binary return 409 on start. Starting a job that is already running returns the current running status instead of spawning a duplicate.

## Testing

Add manager tests for listing, command construction, status, unsupported start preconditions, and logs. Add API tests for list/start/status/logs. Run the focused quantization tests and existing API suite.
