# canadarm-capture

A MuJoCo simulation of a space station arm capturing a free-floating cargo vehicle, built to study how much error the capture tolerates and which physical parameters decide it.

**Status:** early. The scene and the snare mechanism work: a pin placed inside the end effector is centred, pulled in, and held. The arm does not yet approach a moving vehicle. See the [plan](docs/PLAN.md) and the [build log](docs/DEVLOG.md).

![Project plan](docs/media/plan.svg)

![Grapple sequence](docs/media/snare_capture.gif)

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/python scripts/render_capture.py
```

Runs on CPU. Developed on an Apple Silicon Mac with MuJoCo 3.15.

## Scope

Simulation only. Dimensions and masses are approximations of Canadarm2 and a Cygnus-class vehicle, not engineering data, and nothing here is validated against flight data.

## How this was built

I directed the project and made the design decisions; the code was written with Claude Code. The [build log](docs/DEVLOG.md) records each step, including the approaches that failed.
