# Cosmos 3 Reasoner endpoint

GreenhouseBot uses the Cosmos 3 **Reasoner-only** serving path. NVIDIA NIM and
vLLM expose the same OpenAI-compatible API on port 8000.

## Client configuration

```bash
export COSMOS_API_URL="http://127.0.0.1:8000/v1/chat/completions"
export COSMOS_API_KEY=""
export COSMOS_MODEL="nvidia/cosmos3-nano-reasoner"
```

Use `nvidia/cosmos3-super-reasoner` only when the server was launched with the
Super model. For a protected remote endpoint, set its bearer token in
`COSMOS_API_KEY`. If `COSMOS_API_URL` is unset, GreenhouseBot uses its local
mock reasoner.

Check a running server with:

```bash
curl -s http://127.0.0.1:8000/v1/models
curl -s http://127.0.0.1:8000/v1/health/ready
```

## Recommended deployment: NVIDIA NIM

The commands below follow NVIDIA's Cosmos 3 Reasoner cookbook. An NGC API key
is required.

```bash
export NGC_API_KEY="your-ngc-key"
export LOCAL_NIM_CACHE="$HOME/.cache/nim"
mkdir -p "$LOCAL_NIM_CACHE"

docker run -it --rm \
  --name=nvidia-cosmos3-reasoner \
  --runtime=nvidia \
  --gpus all \
  --shm-size=32GB \
  -e NGC_API_KEY="$NGC_API_KEY" \
  -e NIM_MODEL_SIZE=nano \
  -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
  -u "$(id -u)" \
  -p 8000:8000 \
  nvcr.io/nim/nvidia/cosmos3-reasoner:1.7.0
```

Set `NIM_MODEL_SIZE=super` for Super. The corresponding served model IDs are
`nvidia/cosmos3-nano-reasoner` and `nvidia/cosmos3-super-reasoner`.

## vLLM alternative

NVIDIA's Cosmos repository also supports a vLLM reasoner-only backend. Follow
the repository environment setup and launch instructions, then point
GreenhouseBot to the server's `/v1/chat/completions` endpoint. The client
resolves no local model weights; the configured server owns model loading.

## Request and response

See [COSMOS3_PROTOCOL.md](COSMOS3_PROTOCOL.md) for the exact multimodal request,
model response, and GreenhouseBot parsing boundary.

Official references:

- [NVIDIA Cosmos repository](https://github.com/NVIDIA/cosmos)
- [Cosmos 3 Reasoner cookbook](https://github.com/NVIDIA/cosmos/tree/main/cookbooks/cosmos3/reasoner)
- [Cosmos 3 Reasoner prompt guide](https://github.com/NVIDIA/cosmos/blob/main/cookbooks/cosmos3/reasoner/reasoner_prompt_guide.md)
