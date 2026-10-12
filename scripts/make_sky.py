"""Paint a starry sky for the scene's background and save it as assets/processed/sky.png.

    python scripts/make_sky.py [--size 2048] [--seed 7]

The sky is invented: random stars, a band of glow with dust lanes standing in for the
Milky Way, and a few faint smudges standing in for galaxies. It is not a map of the
real sky. It is appearance only and changes nothing in the physics.

The file is a cube map: six square faces stacked top to bottom in the order MuJoCo
expects (+x, -x, +y, -y, +z, -z). scene.build_model uses it when it exists.
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "assets" / "processed" / "sky.png"

# Direction of each pixel on a face, from its image coordinates s (right) and t (down),
# both running from -1 to 1. The OpenGL cube map convention.
FACES = [
    lambda s, t: (np.ones_like(s), -t, -s),  # +x
    lambda s, t: (-np.ones_like(s), -t, s),  # -x
    lambda s, t: (s, np.ones_like(s), t),  # +y
    lambda s, t: (s, -np.ones_like(s), -t),  # -y
    lambda s, t: (s, -t, np.ones_like(s)),  # +z
    lambda s, t: (-s, -t, -np.ones_like(s)),  # -z
]


def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


POLE = _unit([0.35, 0.45, 0.82])  # the bright band lies in the plane square to this


def _lattice(ix, iy, iz, seed: int) -> np.ndarray:
    """A repeatable pseudo-random number in [0, 1) for every integer lattice point."""
    h = (ix * 374761393 + iy * 668265263 + iz * 2147483647 + seed * 1274126177) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1103515245) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0x1000000)


def _noise(p: np.ndarray, seed: int) -> np.ndarray:
    """Smooth noise in 3D, so that it is continuous across the cube's edges."""
    i = np.floor(p).astype(np.int64)
    f = p - i
    f = f * f * (3 - 2 * f)
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[..., 0] if dx else 1 - f[..., 0]) * (f[..., 1] if dy else 1 - f[..., 1]) * (f[..., 2] if dz else 1 - f[..., 2])
                out = out + w * _lattice(i[..., 0] + dx, i[..., 1] + dy, i[..., 2] + dz, seed)
    return out


def _clouds(d: np.ndarray, scale: float, seed: int, octaves: int = 5) -> np.ndarray:
    """Layered noise in [0, 1]: big soft shapes with finer detail on top."""
    total, amp, norm = 0.0, 1.0, 0.0
    for k in range(octaves):
        total = total + amp * _noise(d * scale * 2**k + 17.0 * k, seed + k)
        norm += amp
        amp *= 0.55
    return total / norm


def _galaxies(rng: np.random.Generator) -> list[tuple]:
    """A few distant galaxies: where each is, how it is turned, its size, and its brightness."""
    out = []
    while len(out) < 4:
        c = _unit(rng.normal(size=3))
        if abs(c @ POLE) < 0.35:
            continue  # keep them out of the band, where they would not be seen
        a = _unit(np.cross(c, rng.normal(size=3)))
        out.append((c, a, np.cross(c, a), np.radians(rng.uniform(0.5, 1.6)), rng.uniform(0.25, 0.8), rng.uniform(0.10, 0.22)))
    return out


def _glow(d: np.ndarray, galaxies: list[tuple], seed: int) -> np.ndarray:
    """Colour of the diffuse sky in each direction d (unit vectors), before stars."""
    centre = _unit(np.cross(POLE, [0.0, 0.0, 1.0]))  # brightest part of the band
    lat = np.arcsin(np.clip(d @ POLE, -1, 1))
    toward = d @ centre
    lat = lat + np.radians(5.0) * (_clouds(d, 2.0, seed + 30, 3) - 0.5)  # a ragged edge
    width = np.radians(5.5) * (1.0 + 1.1 * np.clip(toward, 0, 1) ** 3)
    band = np.exp(-((lat / width) ** 2)) * (0.3 + 0.7 * np.clip(0.5 + 0.5 * toward, 0, 1) ** 2)
    texture = np.clip((_clouds(d, 5.0, seed) - 0.3) * 2.2, 0, 1) ** 1.5
    dust = np.clip((_clouds(d, 9.0, seed + 50) - 0.42) * 5.0, 0, 1) * np.exp(-((lat / np.radians(3.5)) ** 2))
    level = band * (0.12 + 1.1 * texture) * (1.0 - 0.9 * dust)
    warm = np.clip(toward, 0, 1)[..., None] ** 2  # yellower toward the centre, bluer away from it
    tint = (1 - warm) * np.array([0.62, 0.72, 1.0]) + warm * np.array([1.0, 0.86, 0.66])
    rgb = 0.2 * level[..., None] * tint
    # a faint uneven haze everywhere, so the dark is not perfectly flat
    rgb = rgb + 0.002 * _clouds(d, 1.5, seed + 90)[..., None] * np.array([0.6, 0.7, 1.0])

    for c, a, b, size, squash, brightness in galaxies:  # soft elliptical smudges
        r2 = ((d @ a) / size) ** 2 + ((d @ b) / (size * squash)) ** 2
        smudge = np.where(d @ c > 0, np.exp(-np.sqrt(r2) * 1.6) + 0.5 * np.exp(-r2 * 6.0), 0.0)
        rgb = rgb + brightness * smudge[..., None] * np.array([1.0, 0.92, 0.8])
    return rgb


def _add_stars(faces: np.ndarray, rng: np.random.Generator, n: int) -> None:
    """Scatter stars over the cube. Most are faint; a few are bright and slightly coloured."""
    size = faces.shape[1]
    d = _unit(rng.normal(size=(3 * n, 3)))
    # crowd more of them toward the band
    keep = rng.random(3 * n) < 0.25 + 0.75 * np.exp(-((np.arcsin(np.clip(d @ POLE, -1, 1)) / np.radians(14.0)) ** 2))
    d = d[keep][:n]
    brightness = np.clip(0.05 * rng.pareto(1.5, size=len(d)) + 0.03, 0, 6.0)
    temperature = rng.random(len(d))
    colour = np.stack([0.75 + 0.25 * temperature, 0.82 + 0.1 * np.sin(np.pi * temperature), 1.0 - 0.3 * temperature], axis=1)

    ax = np.argmax(np.abs(d), axis=1)
    sign = np.sign(d[np.arange(len(d)), ax])
    face = 2 * ax + (sign < 0)
    x, y, z = d[:, 0], d[:, 1], d[:, 2]
    m = np.abs(d[np.arange(len(d)), ax])
    # the inverse of FACES: image coordinates of each direction on its face
    s = np.choose(face, [-z, z, x, x, x, -x]) / m
    t = np.choose(face, [-y, -y, z, -z, -y, -y]) / m
    px, py = (s + 1) / 2 * size - 0.5, (t + 1) / 2 * size - 0.5
    for f, cx, cy, b, c in zip(face, px, py, brightness, colour):
        radius = 1 if b < 0.8 else (2 if b < 2.5 else 3)
        x0, y0 = int(round(cx)), int(round(cy))
        xs = np.arange(max(0, x0 - radius), min(size, x0 + radius + 1))
        ys = np.arange(max(0, y0 - radius), min(size, y0 + radius + 1))
        if not len(xs) or not len(ys):
            continue
        spread = 0.38 + 0.12 * radius
        spot = np.exp(-((xs[None, :] - cx) ** 2 + (ys[:, None] - cy) ** 2) / (2 * spread**2))
        faces[f, ys[:, None], xs[None, :]] += b * spot[..., None] * c


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--size", type=int, default=2048, help="pixels along each cube face")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--stars", type=int, default=40000)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    grid = (np.arange(args.size) + 0.5) / args.size * 2 - 1
    s, t = np.meshgrid(grid, grid)
    faces = np.empty((6, args.size, args.size, 3))
    galaxies = _galaxies(rng)
    for i, direction in enumerate(FACES):
        d = _unit(np.stack(direction(s, t), axis=-1))
        faces[i] = _glow(d, galaxies, args.seed)
    _add_stars(faces, rng, args.stars)

    image = np.clip(faces, 0, 1) ** (1 / 2.2)  # brightness to screen values
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((255 * image.reshape(6 * args.size, args.size, 3)).astype(np.uint8)).save(OUT, optimize=True)
    print("wrote", OUT.relative_to(OUT.parent.parent.parent), f"({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
