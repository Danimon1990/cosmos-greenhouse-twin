# Where to get your Cosmos Reason 2 endpoint

The **shareable URL** from Brev (or similar) is usually a **machine or tunnel URL**, not the API endpoint. The agent needs the **chat completions** URL.

**Important:** On Brev, port **8888** is typically **Jupyter Server**, not the model API. Use port **8000** for Cosmos Reason 2 (NIM/vLLM). You must **start** the model server yourself—it does not run by default.

---

## If the agent runs on the **same machine** as Cosmos (e.g. same Brev VM)

Cosmos Reason 2 (NIM or vLLM) listens on port **8000** by default. Use **localhost**:

```bash
export COSMOS_API_URL="http://127.0.0.1:8000/v1/chat/completions"
# No API key needed for localhost
export COSMOS_API_KEY=""
```

Or with a placeholder key (client accepts empty key for localhost):

```bash
export COSMOS_API_URL="http://127.0.0.1:8000/v1/chat/completions"
export COSMOS_API_KEY="none"
```

**Check that the model is actually running** on that machine:

```bash
curl -s http://127.0.0.1:8000/v1/models
# or
curl -s http://127.0.0.1:8000/v1/health/ready
```

If you get connection refused, start the NIM or vLLM server first (see below).

---

## If you use Brev’s **tunnel** (shareable URL)

Brev can expose port 8000 via a tunnel. That gives you a URL like `https://something.brev.dev`.

- **Endpoint to set:**  
  `https://<that-host>/v1/chat/completions`  
  Example: `https://abc123.brev.dev/v1/chat/completions`

- **API key:**  
  Depends on the tunnel. If Brev requires auth, use the key/token they give you for `COSMOS_API_KEY`. If the tunnel has no auth, you can try `COSMOS_API_KEY=""` or a placeholder.

Note: Brev’s docs say that for **direct API access without browser auth**, port forwarding may work better than the tunnel. If the tunnel does a browser redirect, scripted calls may fail.

---

## How to run Cosmos Reason 2 on the GPU machine

You need the model serving on port 8000 on that machine.

### Option A: NVIDIA NIM (Docker)

From [NVIDIA’s Brev + NIM guide](https://docs.nvidia.com/brev/latest/deploying-nims.html) and Cosmos Reason 2:

1. NGC API key: create at [ngc.nvidia.com](https://ngc.nvidia.com), then:
   ```bash
   echo "$NGC_CLI_API_KEY" | docker login nvcr.io --username '$oauthtoken' --password-stdin
   ```
2. Run the Cosmos Reason 2 NIM (image name may vary; check NGC for `cosmos-reason2`):
   ```bash
   export NGC_API_KEY="your-ngc-key"
   docker run -it --rm --name cosmos-reason2 --runtime=nvidia --gpus all \
     --shm-size=32GB -e NGC_API_KEY=$NGC_API_KEY \
     -v ~/.cache/nim:/opt/nim/.cache -p 8000:8000 \
     nvcr.io/nim/nvidia/cosmos-reason2-2b:1.6.0
   ```
3. When it’s up, use:
   ```bash
   export COSMOS_API_URL="http://127.0.0.1:8000/v1/chat/completions"
   export COSMOS_API_KEY=""
   ```

### Option B: vLLM (from cosmos-reason2 repo)

If you use the [nvidia-cosmos/cosmos-reason2](https://github.com/nvidia-cosmos/cosmos-reason2) repo and start the server with vLLM:

```bash
vllm serve nvidia/Cosmos-Reason2-2B \
  --allowed-local-media-path "$(pwd)" \
  --max-model-len 16384 \
  --port 8000
```

Then again:

```bash
export COSMOS_API_URL="http://127.0.0.1:8000/v1/chat/completions"
export COSMOS_API_KEY=""
```

---

## Summary

| Scenario | COSMOS_API_URL | COSMOS_API_KEY |
|----------|-----------------|-----------------|
| Agent and model on **same** machine | `http://127.0.0.1:8000/v1/chat/completions` | `""` or `none` |
| Model exposed via **Brev tunnel** | `https://<tunnel-host>/v1/chat/completions` | Whatever Brev/tunnel requires (or `""`) |

The **shareable URL** is the host (and maybe path) of the tunnel or VM; the **endpoint** is that host + **`/v1/chat/completions`**.
