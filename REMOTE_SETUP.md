# Running on a GPU Remote (e.g. Cosmos2)

Use this when your project files are on a remote machine with GPU and you want to run the Cosmos agent (or full demo).

## 1. Environment

From the **project root** on the remote:

```bash
cd /path/to/cosmos-greenhouse-twin   # your remote repo path

python3 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows

pip install -r requirements.txt
```

Optional: if you need to read the USD stage from this machine (e.g. to build context from `greenhouse.usda`), install USD Python bindings:

```bash
pip install usd-core   # or use Omniverse Python on that host
```

## 2. Cosmos API (real model on GPU)

To use Cosmos Reason 2 instead of the built-in mock, set the **endpoint** (not the shareable URL). See **[docs/COSMOS_ENDPOINT.md](docs/COSMOS_ENDPOINT.md)** for where to get it.

**Same machine as the model (e.g. NIM or vLLM on port 8000):**
```bash
export COSMOS_API_URL="http://127.0.0.1:8000/v1/chat/completions"
export COSMOS_API_KEY=""   # optional for localhost
```

**Remote/tunnel URL:**
```bash
export COSMOS_API_URL="https://your-tunnel-or-host/v1/chat/completions"
export COSMOS_API_KEY="your-api-key"
```

If `COSMOS_API_URL` is not set, the agent runs in **mock mode** (no API calls).

## 3. Run the agent

You need an **image path** (e.g. a greenhouse screenshot). If you don’t have `demo/frame.png` on the remote, copy one over or use any PNG path.

**Dry run (log only, no USD writes):**

```bash
python src/agent/cosmos_agent.py --image demo/frame.png
```

**With context from a file (no USD/pxr needed):**

```bash
python src/agent/cosmos_agent.py --image demo/frame.png --context-file demo/test_context.json
```

**Full actuation (writes to `usd/layers/live_state.usda`):**

```bash
python src/agent/cosmos_agent.py --image demo/frame.png --actuate
```

For actuation, the script must be able to resolve the project root and `usd/` (run from repo root). If you only have an image and JSON context (no USD on the remote), use `--context-file` and omit `--actuate`, or run actuation later from a machine that has the USD tree.

## 4. Quick test without an image file

If `demo/frame.png` is missing, create a tiny placeholder and run in mock mode:

```bash
python -c "
from PIL import Image
img = Image.new('RGB', (100, 100), color=(100, 150, 100))
img.save('demo/frame.png')
"
pip install Pillow   # if needed
python src/agent/cosmos_agent.py --image demo/frame.png --context-file demo/test_context.json
```

## 5. Full demo flow (when USD is available on remote)

```bash
# Simulate a dry zone
python src/usd_tools/update_state.py --zone B03-C --zone-moisture 22 --zone-status dry

# Run agent with actuation (updates live_state.usda and plant materials)
python src/agent/cosmos_agent.py --image demo/frame.png --actuate
```

Logs are written under `logs/` with timestamps.

## Summary

| Goal                         | Command / step |
|-----------------------------|----------------|
| Install deps                | `pip install -r requirements.txt` |
| Use real Cosmos (GPU)       | Set `COSMOS_API_URL` and `COSMOS_API_KEY` |
| Test without API            | Run `cosmos_agent.py` without env vars (mock) |
| Test without USD            | Use `--context-file demo/test_context.json` |
| Apply actions to USD        | Run from repo root with `--actuate` and USD/pxr available |
