# Cosmos 3 Reasoner communication contract

GreenhouseBot talks to Cosmos 3 through the OpenAI-compatible chat-completions
API exposed by NVIDIA NIM or vLLM.

## Input

`POST /v1/chat/completions` with `Content-Type: application/json` and an
optional bearer token. The user content is ordered as NVIDIA requires: media
first, then the text prompt.

```json
{
  "model": "nvidia/cosmos3-nano-reasoner",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful physical-AI assistant for a robot-assisted greenhouse."
    },
    {
      "role": "user",
      "content": [
        {
          "type": "image_url",
          "image_url": {"url": "data:image/jpeg;base64,<camera-frame>"}
        },
        {
          "type": "text",
          "text": "Context (JSON): <sensor, device, zone and alert snapshot> ..."
        }
      ]
    }
  ],
  "max_tokens": 4096,
  "temperature": 0.6,
  "top_p": 0.95,
  "presence_penalty": 0.0,
  "seed": 0
}
```

For video, Cosmos 3 uses a `video_url` content item. Frame sampling can be sent
through the server-specific multimodal processor options described in NVIDIA's
cookbook. The first extension milestone sends a single Isaac Sim camera frame.

## Model output

The transport response is a standard chat completion. Cosmos-generated text is
read from `choices[0].message.content`:

```json
{
  "model": "nvidia/cosmos3-nano-reasoner",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "<think>...</think>\n{\"explanation\":\"...\",\"recommendations\":[]}"
      }
    }
  ]
}
```

Reasoning mode is enabled by the prompt format recommended by NVIDIA. The
client removes the `<think>...</think>` trace, parses the following JSON, and
validates supported actions before anything reaches USD. The raw server
response is retained in the run log for diagnostics.

The model output is a **proposal**, never a direct actuator command. The future
Isaac Sim extension will convert validated recommendations into the versioned
Cosmos decision contract, show them for operator approval, and only then write
approved commands to `usd/runtime/live_state.usda`.

## Application-level JSON

```json
{
  "explanation": "Zone B03-C is visibly stressed and its soil telemetry is low.",
  "recommendations": [
    {
      "action": "set_valve",
      "value": 1.0,
      "why": "Irrigate dry zone B03-C.",
      "confidence": 0.91
    }
  ]
}
```

Supported actions are `set_fan`, `set_vent`, `set_valve`, `send_alert`, and
`no_action`. Values outside the device contract will be rejected at the
extension/command boundary.
