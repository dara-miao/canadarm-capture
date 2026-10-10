# canadarm-capture

A MuJoCo simulation of a space station arm capturing a free-floating cargo vehicle, built to study how much error the capture tolerates and which physical parameters decide it.

**Status:** early. The zero-gravity scene exists and is checked; there is no capture mechanism or controller yet. See the [plan](docs/PLAN.md) and the [build log](docs/DEVLOG.md).

![Project plan](docs/media/plan.svg)

![End effector and grapple pin](docs/media/scene_closeup.png)

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/python scripts/render_scene.py
```

Runs on CPU. Developed on an Apple Silicon Mac with MuJoCo 3.15.

## Scope

Simulation only. Dimensions and masses are approximations of Canadarm2 and a Cygnus-class vehicle, not engineering data, and nothing here is validated against flight data.
