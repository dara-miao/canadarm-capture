"""Download the 3D models and convert them into per-link meshes.

The models are not stored in this repository. This script fetches them from the
agencies' own sites into assets/raw/ and writes processed meshes to
assets/processed/. The simulation runs without them, using plain shapes.

Sources and terms:
  Canadian Space Agency, 1:100 printable models of Canadarm2 and Cygnus.
    Credit: Canadian Space Agency. Non-commercial reproduction permitted with
    acknowledgement; no endorsement implied. https://www.asc-csa.gc.ca/eng/terms.asp

Needs the `assets` extra:  pip install -e ".[assets]"
"""

import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from capture import geometry as g  # noqa: E402

RAW = ROOT / "assets" / "raw"
OUT = ROOT / "assets" / "processed"
CSA = "https://www.asc-csa.gc.ca/stl/"
FILES = [
    "SSRMS_1-100_Boom A_v01.STL",
    "SSRMS_1-100_Boom B_v01.STL",
    "Cygnus_Enhanced_1-100_v01.STL",
    "Cygnus_Enhanced_1-100_SolarArray_v01.STL",
]
PRINT_SCALE = 0.1  # files are in millimetres at 1:100, so 1 mm is 0.1 m at full size


def download() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        path = RAW / name
        if path.exists():
            continue
        print("downloading", name)
        urllib.request.urlretrieve(CSA + urllib.parse.quote(name), path)


def load(name: str) -> trimesh.Trimesh:
    mesh = trimesh.load(RAW / name, force="mesh")
    mesh.apply_scale(PRINT_SCALE)
    return mesh


def split(mesh: trimesh.Trimesh) -> list[trimesh.Trimesh]:
    return [p for p in mesh.split(only_watertight=False) if len(p.vertices) >= 4]


def save(name: str, parts: list[trimesh.Trimesh]) -> None:
    mesh = trimesh.util.concatenate(parts)
    mesh.export(OUT / f"{name}.stl")
    print(f"  {name}.stl  {len(parts)} parts, {len(mesh.faces)} faces")


def boom_a() -> None:
    """Base half of the arm. Its centred frame is the arm's assembly frame."""
    mesh = load(FILES[0])
    mesh.apply_translation(-mesh.bounds.mean(axis=0))
    links = {"lee_a": [], "sr": [], "sy": [], "sp": []}
    for part in split(mesh):
        (cx, cy, _), y_min = part.bounds.mean(axis=0), part.bounds[0][1]
        if y_min >= 0.13:
            links["lee_a"].append(part)  # end effector, bolted to the station
        elif cx > 3.3:
            links["sr"].append(part)
        elif cx > 2.85 and cy > -0.71:
            links["sy"].append(part)
        else:
            links["sp"].append(part)  # boom, elbow housing, cameras
    for name, parts in links.items():
        save(name, parts)


def boom_b() -> None:
    """Tip half of the arm, moved so its elbow axis meets boom A's."""
    mesh = load(FILES[1])
    mesh.apply_translation(-mesh.bounds.mean(axis=0))
    links = {"lee_b": [], "wy": [], "wp": [], "ep": []}
    for part in split(mesh):
        (cx, cy, _), z_min = part.bounds.mean(axis=0), part.bounds[0][2]
        if cx > 3.3 and z_min > -0.35:
            links["lee_b"].append(part)
        elif cx > 3.27:
            links["wy"].append(part)
        elif cx > 2.8 and cy < 0.34:
            links["wp"].append(part)
        else:
            links["ep"].append(part)
    for name, parts in links.items():
        for part in parts:
            part.apply_translation(g.BOOM_B_OFFSET)
        save(name, parts)


def cygnus() -> None:
    body, array = load(FILES[2]), load(FILES[3])
    centre = body.bounds.mean(axis=0)
    to_body = np.eye(4)
    to_body[:3, :3] = g.CYGNUS_MESH_TO_BODY
    to_body[:3, 3] = -g.CYGNUS_MESH_TO_BODY @ centre
    # The printable model has one array; the second is its mirror image across the hull.
    mirror = np.eye(4)
    mirror[2, 2] = -1.0
    mirror[2, 3] = 2 * centre[2]
    other = array.copy()
    other.apply_transform(mirror)
    other.invert()
    for mesh in (body, array, other):
        mesh.apply_transform(to_body)
    save("cygnus_body", split(body))
    save("cygnus_arrays", [array, other])


def main() -> None:
    download()
    OUT.mkdir(parents=True, exist_ok=True)
    print("writing", OUT.relative_to(ROOT))
    boom_a()
    boom_b()
    cygnus()


if __name__ == "__main__":
    main()
