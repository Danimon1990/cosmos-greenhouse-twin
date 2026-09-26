# Autonomous Greenhouse · OpenUSD Digital Twin

A Physical AI project exploring greenhouse simulation, plant perception, and assisted control with OpenUSD, NVIDIA Isaac Sim, Python, and Cosmos.

**[Explore the full project on my website →](https://humannaturetech.com/greenhouse/)**

The website presents the project story, visuals, and progress. This repository focuses on the core implementation: the greenhouse scene, simulation controls, reasoning interface, and data contracts.

## Watch the demos

- [Greenhouse simulation — YouTube](https://youtu.be/uKu13Ew1HAc)
- [Remote operation with WebRTC — LinkedIn](https://lnkd.in/p/gM3YXhXF)
- [Procedural plants and perception experiments — YouTube](https://youtu.be/5GVQu2DDJLk)

## Explore the code

- **[OpenUSD architecture](docs/USD_ARCHITECTURE_PLAN.md):** scene composition, assets, layouts, materials, cameras, and runtime state.
- **[Isaac Sim gantry extension](exts/com.greenhouse.gantry/README.md):** inspection-camera movement and capture, manual greenhouse controls, and approval of supported recommendations.
- **[Reasoning client](src/agent/):** image and telemetry inputs, a configurable Cosmos HTTP interface, and an offline mock mode.
- **[Data contracts](contracts/README.md):** schemas and examples for telemetry, device identity, and commands.
- **[Streaming client](web/greenhouse-local-stream/):** WebRTC access to a GPU-hosted Kit application.

## Try the offline demo

Use Python 3.10+; the demo was checked with Python 3.12. No GPU, model weights, or USD installation is required for this command.

```bash
git clone https://github.com/Danimon1990/cosmos-greenhouse-twin.git
cd cosmos-greenhouse-twin
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

COSMOS_API_URL= COSMOS_API_KEY= python src/agent/cosmos_agent.py \
  --image demo/frame.png \
  --context-file demo/scenario_1_dry_zone.json
```

This explicitly selects the rule-based mock, prints recommendations, and writes a local log. It does not inspect image pixels or actuate the scene. See [endpoint setup](docs/COSMOS_ENDPOINT.md) for live inference configuration.

For the simulation, open `usd/scenes/greenhouse_main.usda` in Isaac Sim and follow the [extension setup guide](exts/com.greenhouse.gantry/README.md).

## Project status and scope

This is an ongoing research prototype. The broader work includes procedural crop generation and synthetic-data perception experiments, shown on the website and in the videos. Synthetic validation results do not establish real-world plant-health accuracy; physical deployment and autonomous manipulation remain future work.

Videos, datasets, training checkpoints, generated captures, and local environments are kept outside the published source. The small demo input and core scene textures remain because the implementation uses them. Ignore rules prevent new generated artifacts from being added; they do not remove files from existing Git history.
