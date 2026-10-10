"""Geometry read off the Canadian Space Agency's 1:100 models, at full scale [m].

The arm's assembly frame is boom A's bounding-box centre, with x along the boom.
In this frame the arm is folded: both booms lie side by side with the elbow at -x.
Positions were measured from the bounding boxes of the models' separate parts,
so they are good to a few centimetres at best.
"""

import numpy as np

# Translation that puts boom B's elbow axis on boom A's, with B on boom A's -y side.
# Which side B sits on is a guess; the models do not say how the halves mate.
BOOM_B_OFFSET = np.array([0.03, -1.87, 0.48])

# Rotation from the Cygnus model's axes to the vehicle body frame used here:
# hull axis along z, grapple fixture pointing along +x.
CYGNUS_MESH_TO_BODY = np.array([[-1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]])

# Meshes written by scripts/fetch_assets.py, by the body they are attached to.
ARM_MESHES = {
    "arm_root": "lee_a",
    "sr": "sr",
    "sy": "sy",
    "sp": "sp",
    "ep": "ep",
    "wp": "wp",
    "wy": "wy",
    "lee": "lee_b",
}
VEHICLE_MESHES = {"cygnus_body": (0.82, 0.82, 0.84, 1.0), "cygnus_arrays": (0.12, 0.16, 0.38, 1.0)}
