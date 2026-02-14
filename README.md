# GreenhouseBot: Spatial Reasoning Digital Twin

**A physical AI prototype that treats a greenhouse as a robot** — with eyes (vision), memory (OpenUSD digital twin), and a brain (Cosmos Reason 2).

Built for the [NVIDIA Cosmos Cookoff](https://www.nvidia.com/en-us/ai-data-science/cosmos-cookoff/) competition.

---

## The Problem

Traditional greenhouse automation uses simple thresholds: "if humidity > 80%, turn on fan." But real greenhouses have **spatial variation** — one corner may be dry while another is overwatered. Existing systems can't reason about *where* problems occur, only *what* the sensor values are.

## Our Solution: Spatial Reasoning

GreenhouseBot uses **Cosmos Reason 2** to perform **zone-level spatial reasoning** over a digital twin greenhouse:

1. **See**: Camera images of the greenhouse
2. **Remember**: OpenUSD digital twin with 24 spatial zones (8 beds × 3 zones each)
3. **Think**: Cosmos Reason 2 analyzes image + zone telemetry to identify *where* problems are
4. **Act**: Targeted interventions (e.g., "irrigate zone B03-C" not just "turn on water")

**Key Differentiator**: Instead of global automation, we demonstrate **explainable, zone-aware decision making** — Cosmos can say "Zone B03-C in the middle-left of the greenhouse appears dry based on the image and telemetry data."

---

## Quick Start

```bash
# 1. Clone and navigate
git clone https://github.com/your-repo/cosmos-greenhouse-twin.git
cd cosmos-greenhouse-twin

# 2. Set up environment (requires USD Python bindings)
# Option A: Use Omniverse Python
# Option B: pip install usd-core

# 3. Simulate a problem
python src/usd_tools/update_state.py --zone B03-C --zone-moisture 22 --zone-status dry

# 4. Run the spatial reasoning agent (mock mode)
python src/agent/cosmos_agent.py --image demo/frame.png --actuate

# 5. Open in USD Composer to see the result
# Plants in zone B03-C are now brownish (UnhealthyPlantMat)
# Valve is open (device:flow = 1.0)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GreenhouseBot Architecture                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   Camera     │    │  USD Stage   │    │   Cosmos     │                  │
│  │   Image      │───▶│  (24 zones)  │───▶│  Reason 2    │                  │
│  │  demo/*.png  │    │  telemetry   │    │  (or mock)   │                  │
│  └──────────────┘    └──────────────┘    └──────┬───────┘                  │
│                                                  │                          │
│                                                  ▼                          │
│                                    ┌─────────────────────────┐              │
│                                    │  Spatial Reasoning      │              │
│                                    │  "Zone B03-C is dry,    │              │
│                                    │   open valve for        │              │
│                                    │   targeted irrigation"  │              │
│                                    └───────────┬─────────────┘              │
│                                                │                            │
│                          ┌─────────────────────┼─────────────────────┐      │
│                          ▼                     ▼                     ▼      │
│                   ┌────────────┐        ┌────────────┐        ┌──────────┐ │
│                   │ Actuators  │        │ live_state │        │ Visual   │ │
│                   │ Fan, Vent, │        │   .usda    │        │ Feedback │ │
│                   │ Valve      │        │ (updated)  │        │ (plants) │ │
│                   └────────────┘        └────────────┘        └──────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Demo Flow (for Video)

### Step 1: Show Healthy Greenhouse
Open `usd/root/greenhouse.usda` in USD Composer. All plants are green.

### Step 2: Simulate a Problem
```bash
python src/usd_tools/update_state.py --zone B03-C --zone-moisture 22 --zone-status dry
```

### Step 3: Capture Screenshot
In USD Composer: File → Export Screenshot → save to `demo/frame.png`

### Step 4: Run Cosmos Agent with Actuation
```bash
# With Cosmos API:
export COSMOS_API_URL="https://your-endpoint/v1/chat/completions"
export COSMOS_API_KEY="your-key"
python src/agent/cosmos_agent.py --image demo/frame.png --actuate

# Without API (mock mode for testing):
python src/agent/cosmos_agent.py --image demo/frame.png --actuate
```

**Output:**
```
--- Summary ---
[SPATIAL REASONING] Detected dry zones at B03-C. These zones show soil
moisture below 30%, indicating water stress. The affected areas are
visible in the greenhouse image as potentially wilted plants.

Recommendations (2):
  - set_valve = 1.0  // Irrigate dry zones: B03-C. Soil moisture critically low.
  - set_fan = 0.0    // Humidity at 50% is within optimal range.

--- Actuation (Day 7) ---
  ✓ Valve_01 device:flow = 1.0
  ✓ B03-C: 24 plants → UnhealthyPlantMat (status=dry)
  ✓ Saved: live_state.usda
```

### Step 5: See Visual Feedback
Reload in USD Composer — plants in zone B03-C are now **brownish/yellow** (`UnhealthyPlantMat`), visually showing the problem area.

### Step 6: Recovery (Optional)
```bash
python src/usd_tools/update_state.py --zone B03-C --zone-moisture 45 --zone-status ok
python src/usd_tools/update_plant_health.py --sync
```
Plants return to green.

---

## Features

### Spatial Zoning (24 Zones)
Each of the 8 beds is divided into 3 zones (A=north, B=center, C=south):

| Zone ID | Location | Description |
|---------|----------|-------------|
| B01-A | Bed 1, North | Z ∈ [-8, -2.67] |
| B01-B | Bed 1, Center | Z ∈ [-2.67, +2.67] |
| B01-C | Bed 1, South | Z ∈ [+2.67, +8] |
| ... | ... | ... |
| B08-C | Bed 8, South | Last zone |

**Zone Attributes** (in `live_state.usda`):
- `zone:soilMoisturePct` — Soil moisture (0-100%)
- `zone:lightPct` — Light level (0-100%)
- `zone:healthScore` — Plant health (0-1)
- `zone:status` — `ok` | `dry` | `wet` | `shaded` | `stressed`

### Visual Feedback System
Plants visually reflect zone health:

| Zone Status | Material | Color |
|-------------|----------|-------|
| `ok` | PlantMat | Green (0.15, 0.55, 0.20) |
| `dry`, `stressed`, etc. | UnhealthyPlantMat | Brownish-yellow (0.72, 0.58, 0.20) |

This creates an **immediate visual correlation** between telemetry data and the 3D scene.

### Cosmos Integration
The agent sends to Cosmos Reason 2:
- **Image**: Screenshot of the greenhouse
- **Context**: JSON with sensors, devices, and all 24 zones
- **Spatial Alerts**: Pre-computed list of dry/shaded zones

Cosmos returns:
- **Explanation**: Natural language spatial reasoning
- **Recommendations**: Structured actions with zone references

---

## Project Structure

```
cosmos-greenhouse-twin/
├── README.md
├── demo/
│   ├── frame.png              # Screenshot for Cosmos
│   └── test_context.json      # Test context with dry zone
├── logs/
│   └── run_*.json             # Timestamped agent logs
│
├── src/
│   ├── agent/
│   │   ├── cosmos_agent.py    # Day 6 & 7: Vision + reasoning + actuation
│   │   ├── cosmos_client.py   # Cosmos API client (with zone-aware mock)
│   │   ├── simple_agent.py    # Rule-based agent (no Cosmos)
│   │   └── schema.py          # Type definitions
│   │
│   └── usd_tools/
│       ├── inspect_stage.py         # Print layer stack, zones, devices
│       ├── update_state.py          # Update telemetry/actuators
│       ├── update_plant_health.py   # Sync plant materials to zone status
│       ├── generate_tunnel_greenhouse.py
│       ├── assign_greenhouse_materials.py
│       └── populate_bed_plants.py
│
└── usd/
    ├── root/
    │   ├── greenhouse.usda          # Root stage (open this)
    │   ├── greenhouse_tunnel.usda   # Tunnel mesh
    │   └── greenhouse_looks.usda    # Materials
    ├── components/
    │   ├── structure.usda           # Floor + tunnel
    │   ├── devices.usda             # Fan, vent, valve, sensor
    │   └── plants.usda              # 8 beds, ~560 plants
    ├── layers/
    │   └── live_state.usda          # Dynamic state (strongest layer)
    ├── variants/
    │   └── plant_states.usda        # plantHealth variant
    └── assets/
        └── plant_sprout/            # Plant mesh asset
```

---

## USD Layer Architecture

The scene uses **composition arcs** to separate static geometry from dynamic state:

```
greenhouse.usda (root)
    ├── sublayers:
    │   ├── plant_states.usda      (weakest)  — variant opinions
    │   ├── greenhouse_looks.usda  (medium)   — materials
    │   └── live_state.usda        (strongest) — telemetry overrides
    │
    ├── references:
    │   ├── structure.usda         — floor, tunnel
    │   └── devices.usda           — actuators, sensors
    │
    └── payload:
        └── plants.usda            — beds, walkways, plants
```

**Key Insight**: `live_state.usda` is the **strongest sublayer**, so any attribute it sets wins at runtime. This allows the agent to update telemetry without modifying base geometry.

---

## CLI Reference

### cosmos_agent.py (Main Agent)
```bash
# Dry run (log only)
python src/agent/cosmos_agent.py --image demo/frame.png

# Full actuation (apply to USD)
python src/agent/cosmos_agent.py --image demo/frame.png --actuate

# With custom context (e.g., on cloud without USD)
python src/agent/cosmos_agent.py --image demo/frame.png --context-file demo/test_context.json
```

### update_state.py (Telemetry)
```bash
# Update sensors
python src/usd_tools/update_state.py --temp 28 --humidity 90 --soil 25

# Update actuators
python src/usd_tools/update_state.py --fan 0.5 --vent 20 --valve 1

# Update zone
python src/usd_tools/update_state.py --zone B03-C --zone-moisture 22 --zone-status dry
```

### update_plant_health.py (Visual Feedback)
```bash
# Update single zone
python src/usd_tools/update_plant_health.py --zone B03-C --status dry

# Sync all zones based on current status
python src/usd_tools/update_plant_health.py --sync

# List plants in a zone
python src/usd_tools/update_plant_health.py --zone B03-C --list
```

### inspect_stage.py (Debugging)
```bash
python src/usd_tools/inspect_stage.py
```
Prints: layer stack, prim tree, device values, zone table.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `COSMOS_API_URL` | Cosmos Reason 2 endpoint | (none — uses mock) |
| `COSMOS_API_KEY` | API key | (none — uses mock) |
| `COSMOS_MODEL` | Model name | `cosmos-reason-2` |

**No secrets in code** — all credentials via environment variables.

---

## Competition Context

### Judging Criteria Alignment

| Criteria | How We Address It |
|----------|-------------------|
| **Quality of Ideas** | Spatial reasoning over 24 zones — Cosmos identifies *where* problems occur, not just *what* |
| **Technical Implementation** | Clean USD layering, typed schemas, modular agents, reproducible CLI |
| **Design** | Visual feedback (plants change color), clear separation of concerns |
| **Impact** | Precision agriculture reduces water waste, enables targeted interventions |

### Why This Matters

1. **Explainability**: Cosmos explains its reasoning in natural language with zone references
2. **Precision**: Zone-level control reduces resource waste (water, energy)
3. **Scalability**: Digital twin pattern works for any spatial environment (warehouses, factories, farms)
4. **Physical AI**: Demonstrates vision + spatial reasoning + actuation loop

---

## Greenhouse Specifications

| Property | Value |
|----------|-------|
| Footprint | 12m × 18m |
| Tunnel height | 4m |
| Beds | 8 (0.8m × 16m × 0.4m each) |
| Walkways | 7 (0.5m wide) |
| Zones | 24 (3 per bed) |
| Plants | ~560 (70 per bed, 2 staggered rows) |
| Coordinate system | Meters, Y-up |

---

## Development Timeline

| Day | Milestone |
|-----|-----------|
| Day 1-3 | USD scene structure, composition arcs |
| Day 4 | Python control bridge (`update_state.py`) |
| Day 5 | Rule-based agent (`simple_agent.py`) |
| Day 6 | Cosmos integration, zone-aware context |
| Day 7 | Actuation, visual feedback, demo polish |

---

## Requirements

- Python 3.10+
- USD Python bindings (`pxr`) — via Omniverse or `pip install usd-core`
- `requests` (for Cosmos API calls)
- NVIDIA USD Composer or usdview (for visualization)

---

## License

MIT License — see LICENSE file.

---

## Acknowledgments

- **NVIDIA Cosmos Team** for the Reason 2 model and competition
- **OpenUSD** for the composition architecture
- Built with Claude Code assistance

---

*GreenhouseBot: Teaching AI to see, think, and act in physical spaces.*
