# canadarm-capture

A MuJoCo case study of a spacecraft capture. A simplified model of a space station arm catches a free-drifting cargo vehicle; the project looks at how that model succeeds and fails, and how much the answers depend on its own assumptions.

Inspired by Canadarm2 capturing Cygnus, which the real arm does routinely. This project does not reproduce that system's flight limits, and a failure here is a failure of this model.

**Status:** in progress. The arm approaches a drifting, tumbling vehicle from the 10 m capture point, snares its grapple pin, pulls it in, and latches, with delayed and noisy sensing. A batch runner records how each attempt ends and at which stage it failed. The systematic experiments have not been run yet. See the [research notes](docs/RESEARCH.md), the [plan](docs/PLAN.md), and the [build log](docs/DEVLOG.md).

![Project plan](docs/media/plan.svg)

![Station, arm, and Cygnus](docs/media/scene_station.png)

![Arm on the forward node](docs/media/scene_wide.png)

![Approach and capture, sped up](docs/media/approach_capture.gif)

![Grapple sequence inside the end effector](docs/media/snare_capture.gif)

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/python scripts/render_approach.py
```

That runs with plain stand-in shapes. To use the real 3D models, fetch them once (about 10 MB, from the Canadian Space Agency and NASA):

```bash
.venv/bin/pip install -e ".[assets]"
.venv/bin/python scripts/fetch_assets.py
```

To watch a capture interactively on macOS:

```bash
.venv/bin/mjpython scripts/view.py
```

Runs on CPU. Developed on an Apple Silicon Mac with MuJoCo 3.15.

## Scope

Simulation only, and deliberately simplified. Not modelled: the snare's cables (three rigid bars stand in), the grapple fixture's cams, the end effector's latches, arm flexibility, orbital mechanics, collisions with the station, and the astronaut who flies the real arm. Nothing here is validated against flight data. The [plan](docs/PLAN.md) lists every assumption and the [research notes](docs/RESEARCH.md) say where each number comes from.

## Credits

3D models of Canadarm2 and Cygnus: Canadian Space Agency. 3D model of the International Space Station: NASA. They are downloaded from the agencies' own sites, not stored here, and used for non-commercial purposes. This project is not associated with or endorsed by the Canadian Space Agency or NASA.

## How this was built

I directed the project and made the design decisions; the code was written with Claude Code. The [build log](docs/DEVLOG.md) records each step, including the approaches that failed.
