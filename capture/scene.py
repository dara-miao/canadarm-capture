"""Build the capture scene and place the vehicle relative to the end effector."""

from pathlib import Path

import mujoco
import numpy as np

BASE_XML = Path(__file__).resolve().parent.parent / "models" / "capture_base.xml"

ARM_JOINTS = (
    "shoulder_roll",
    "shoulder_yaw",
    "shoulder_pitch",
    "elbow_pitch",
    "wrist_pitch",
    "wrist_yaw",
    "wrist_roll",
)

# Arm bent at the elbow with the end effector pointing straight away from the station.
READY_POSE = np.array([0.0, 0.0, 0.7, -1.4, 0.7, 0.0, 0.0])

# End-effector cavity, in the `lee` body frame (z is the approach axis).
CAVITY_Z0, CAVITY_Z1 = 0.5, 1.0
CAVITY_RADIUS = 0.20
WALL_THICKNESS = 0.04
WALL_SEGMENTS = 16
WALL_MASS = 40.0


def _add_cavity_wall(spec: mujoco.MjSpec) -> None:
    """Approximate a hollow cylinder with a ring of boxes.

    MuJoCo collides convex shapes, so one mesh cannot represent a cavity.
    """
    lee = spec.body("lee")
    r_mid = CAVITY_RADIUS + WALL_THICKNESS / 2
    # Half-width chosen so neighbouring boxes overlap at the inner radius.
    half_w = (CAVITY_RADIUS + WALL_THICKNESS) * np.tan(np.pi / WALL_SEGMENTS)
    half_len = (CAVITY_Z1 - CAVITY_Z0) / 2
    for i in range(WALL_SEGMENTS):
        phi = 2 * np.pi * i / WALL_SEGMENTS
        theta = phi + np.pi / 2  # box x axis is tangential
        lee.add_geom(
            name=f"lee_wall_{i}",
            type=mujoco.mjtGeom.mjGEOM_BOX,
            size=[half_w, WALL_THICKNESS / 2, half_len],
            pos=[r_mid * np.cos(phi), r_mid * np.sin(phi), (CAVITY_Z0 + CAVITY_Z1) / 2],
            quat=[np.cos(theta / 2), 0, 0, np.sin(theta / 2)],
            mass=WALL_MASS / WALL_SEGMENTS,
        )


def build_model() -> mujoco.MjModel:
    spec = mujoco.MjSpec.from_file(str(BASE_XML))
    _add_cavity_wall(spec)
    return spec.compile()


def arm_qpos_adr(model: mujoco.MjModel) -> np.ndarray:
    return np.array([model.joint(n).qposadr[0] for n in ARM_JOINTS])


def set_arm(model: mujoco.MjModel, data: mujoco.MjData, q: np.ndarray) -> None:
    """Put the arm at joint angles q and command the actuators to hold it there."""
    data.qpos[arm_qpos_adr(model)] = q
    data.ctrl[:] = q


def place_vehicle(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    standoff: float = 0.5,
    lateral: tuple[float, float] = (0.0, 0.0),
) -> None:
    """Place the vehicle so its grapple pin faces the end-effector mouth.

    standoff: distance from the mouth to the pin tip along the approach axis [m].
    lateral:  pin offset from the approach axis, in the end-effector x/y [m].

    Uses the arm's current pose. Vehicle velocity is left unchanged.
    """
    mujoco.mj_kinematics(model, data)
    mouth = data.site("lee_mouth")
    R_l = mouth.xmat.reshape(3, 3)
    x_l, y_l, z_l = R_l[:, 0], R_l[:, 1], R_l[:, 2]

    # The pin runs along vehicle +x and must point into the cavity, i.e. along -z_l.
    R_v = np.column_stack([-z_l, y_l, x_l])
    tip_world = mouth.xpos + standoff * z_l + lateral[0] * x_l + lateral[1] * y_l
    tip_local = model.site("pin_tip").pos
    pos = tip_world - R_v @ tip_local

    quat = np.empty(4)
    mujoco.mju_mat2Quat(quat, R_v.flatten())
    adr = model.joint("vehicle_free").qposadr[0]
    data.qpos[adr : adr + 3] = pos
    data.qpos[adr + 3 : adr + 7] = quat


def reset(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    standoff: float = 0.5,
    lateral: tuple[float, float] = (0.0, 0.0),
) -> None:
    """Arm at the ready pose, vehicle at rest in front of the end effector."""
    mujoco.mj_resetData(model, data)
    set_arm(model, data, READY_POSE)
    place_vehicle(model, data, standoff, lateral)
    mujoco.mj_forward(model, data)
