# Raspberry Pi Controller Topology

Snapshot date: 2026-05-18

This is the first known-good three-machine deployment:

| Role | Node name | URL | Notes |
| --- | --- | --- | --- |
| Controller | raspberry-pi-controller | `$LLAMA_MANAGER_CONTROLLER_URL` | Runs `mode: controller`; agents register and heartbeat here. |
| Agent | mac-mini | `$LLAMA_MANAGER_AGENT_URL` on the Mac mini; `$LLAMA_MANAGER_MAC_MINI_AGENT_URL` on the controller | Local Mac mini agent config points at the Raspberry Pi controller. |
| Agent | linux-2080ti | `$LLAMA_MANAGER_LINUX_2080TI_AGENT_URL` | 2080 Ti box agent; confirm the current value from the Pi controller `/nodes` output. |

The important topology rule is that every agent uses the Raspberry Pi URL as
`controller_url`, and the controller uses each agent's `agent_url` to proxy
health, model, log, and job operations.

## Mac Mini Agent Values

The Mac mini local config currently has:

```yaml
mode: agent
controller_url: ${LLAMA_MANAGER_CONTROLLER_URL}
node_name: mac-mini
agent_url: ${LLAMA_MANAGER_AGENT_URL}
heartbeat_interval_seconds: 30
```

Keep `LLAMA_MANAGER_AGENT_API_KEY` and
`LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND` in `.llama-manager.env`,
not in tracked docs or config examples.

The Mac mini `.llama-manager.env` should also include:

```bash
export LLAMA_MANAGER_CONTROLLER_URL=http://<raspberry-pi-lan-address>:9137
export LLAMA_MANAGER_AGENT_URL=http://<mac-mini-lan-address>:9137
```

## Smoke Checks

Run these from the Mac mini or any machine on the same network.

Controller health:

```bash
curl -s "$LLAMA_MANAGER_CONTROLLER_URL/health"
```

Expected shape:

```json
{
  "ok": true,
  "mode": "controller",
  "nodes_configured": 2
}
```

Mac mini agent health:

```bash
curl -s "$LLAMA_MANAGER_AGENT_URL/health"
```

Expected shape:

```json
{
  "ok": true,
  "mode": "agent"
}
```

Controller node inventory, with an admin/controller API key:

```bash
curl -s "$LLAMA_MANAGER_CONTROLLER_URL/nodes" \
  -H "X-Llama-Manager-Key: $LLAMA_MANAGER_CONTROLLER_API_KEY"
```

Expected checks:

- `mac-mini` is present.
- `linux-2080ti` is present.
- Both nodes have `heartbeat_fresh: true`.
- Each node's `url` matches the reachable agent URL on the LAN.

Linux 2080 Ti agent health, after confirming the current URL from `/nodes`:

```bash
curl -s "$LLAMA_MANAGER_LINUX_2080TI_AGENT_URL/health" \
  -H "X-Llama-Manager-Key: $LLAMA_MANAGER_LINUX_2080TI_AGENT_API_KEY"
```

## Agent Startup

Each agent should be started with its local config and listen on the LAN:

```bash
scripts/start_agent.sh
```

The agent config must include:

```yaml
mode: agent
controller_url: ${LLAMA_MANAGER_CONTROLLER_URL}
node_name: NODE_NAME
agent_url: ${LLAMA_MANAGER_AGENT_URL}
controller_registration_key_outbound: ${LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND}
```

## Controller Startup

The Raspberry Pi should run:

```bash
scripts/start_controller.sh
```

The controller config should include both agents under `nodes`:

```yaml
mode: controller
nodes:
  mac-mini:
    url: ${LLAMA_MANAGER_MAC_MINI_AGENT_URL}
    api_key: ${LLAMA_MANAGER_MAC_MINI_AGENT_API_KEY}
  linux-2080ti:
    url: ${LLAMA_MANAGER_LINUX_2080TI_AGENT_URL}
    api_key: ${LLAMA_MANAGER_LINUX_2080TI_AGENT_API_KEY}
```

## Troubleshooting

If controller health works but `/nodes` returns `Unauthorized`, export an admin
or controller API key and retry with `X-Llama-Manager-Key`.

If a node is listed but not fresh, check that the agent has:

- `controller_url: ${LLAMA_MANAGER_CONTROLLER_URL}` and the Pi URL in `.llama-manager.env`
- the correct `node_name`
- `agent_url: ${LLAMA_MANAGER_AGENT_URL}` and its LAN-reachable URL in `.llama-manager.env`
- the same registration key value the Pi expects
- a running `scripts/start_agent.sh` process
