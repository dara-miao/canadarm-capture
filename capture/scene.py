"""Build the capture scene and place the vehicle relative to the end effector."""

from pathlib import Path

import mujoco
import numpy as np

from . import geometry

ROOT = Path(__file__).resolve().parent.parent
BASE_XML = ROOT / "models" / "capture_base.xml"
MESH_DIR = ROOT / "assets" / "processed"

ARM_JOINTS = (
    "shoulder_roll",
    "shoulder_yaw",
    "shoulder_pitch",
    "elbow_pitch",
    "wrist_pitch",
    "wrist_yaw",
    "wrist_roll",
)

# End-effector mouth 9 m above the arm's base, pointing straight away from the station.
# Found by inverse kinematics, choosing the best-conditioned of 29 solutions.
READY_POSE = np.array([1.036931, -1.523612, -0.684771, 0.951583, 2.874781, 0.047185, 2.982912])
READY_MOUTH = np.array([1.5, 1.0, 9.0])

# End-effector cavity, in the `lee` body frame (z is the approach axis).
CAVITY_Z0, CAVITY_Z1 = 0.5, 1.0
CAVITY_RADIUS = 0.20
WALL_THICKNESS = 0.04
WALL_SEGMENTS = 16
WALL_MASS = 40.0

# Snare actuator travel [m]. The bars start 0.1 m from the axis; commanding past the
# pin surface makes them press on it. The carriage pulls the closed snare inward.
SNARE_TRAVEL = 0.08
CARRIAGE_TRAVEL = 0.1


def _add_cavity_wall(spec: mujoco.MjSpec) -> None:
    """Approximate a hollow cylinder with a ring of boxes.

    MuJoCo collides convex shapes, so one mesh cannot represent a cavity.
    """
    lee = spec.body("lee_tool")
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
            rgba=[0.85, 0.72, 0.3, 0.35],  # see-through, so the snare is visible
        )


def meshes_available() -> bool:
    names = list(geometry.ARM_MESHES.values()) + list(geometry.VEHICLE_MESHES)
    return all((MESH_DIR / f"{n}.stl").exists() for n in names)


def _use_meshes(spec: mujoco.MjSpec) -> None:
    """Show the downloaded models in place of the stand-in shapes.

    Appearance only: collisions still use the simple shapes, now hidden,
    and masses are unchanged.
    """
    visual = dict(type=mujoco.mjtGeom.mjGEOM_MESH, contype=0, conaffinity=0, density=0)
    for geom in spec.geoms:
        # arm stand-ins, the end-effector shell, and the vehicle hull
        if geom.name.startswith(("v_", "lee_", "hull_")):
            geom.rgba[3] = 0.0
    for body, mesh in geometry.ARM_MESHES.items():
        spec.add_mesh(name=mesh, file=str(MESH_DIR / f"{mesh}.stl"))
        spec.body(body).add_geom(name=f"mesh_{mesh}", meshname=mesh, rgba=[0.93, 0.93, 0.91, 1], **visual)
    for mesh, rgba in geometry.VEHICLE_MESHES.items():
        spec.add_mesh(name=mesh, file=str(MESH_DIR / f"{mesh}.stl"))
        spec.body("vehicle").add_geom(name=f"mesh_{mesh}", meshname=mesh, rgba=list(rgba), **visual)


def build_model(meshes: bool | None = None) -> mujoco.MjModel:
    """Build the scene.

    meshes: show the downloaded 3D models. Defaults to using them when they have
            been fetched (scripts/fetch_assets.py). The physics is the same either way.
    """
    spec = mujoco.MjSpec.from_file(str(BASE_XML))
    _add_cavity_wall(spec)
    if meshes is None:
        meshes = meshes_available()
    if meshes:
        _use_meshes(spec)
    return spec.compile()


def arm_qpos_adr(model: mujoco.MjModel) -> np.ndarray:
    return np.array([model.joint(n).qposadr[0] for n in ARM_JOINTS])


def set_arm(model: mujoco.MjModel, data: mujoco.MjData, q: np.ndarray) -> None:
    """Put the arm at joint angles q and command the actuators to hold it there."""
    data.qpos[arm_qpos_adr(model)] = q
    data.ctrl[: len(ARM_JOINTS)] = q


def set_snare(model: mujoco.MjModel, data: mujoco.MjData, close: float, retract: float) -> None:
    """Command the snare. Both arguments run from 0 (open / extended) to 1 (closed / retracted)."""
    data.ctrl[model.actuator("a_snare").id] = close * SNARE_TRAVEL
    data.ctrl[model.actuator("a_carriage").id] = retract * CARRIAGE_TRAVEL


def pin_offset(model: mujoco.MjModel, data: mujoco.MjData) -> np.ndarray:
    """Pin tip position in the end-effector mouth frame: (x, y) lateral, z along the approach axis.

    z is positive outside the cavity and negative inside it.
    """
    mouth = data.site("lee_mouth")
    return mouth.xmat.reshape(3, 3).T @ (data.site("pin_tip").xpos - mouth.xpos)


def _rot_x(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _rot_y(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def place_vehicle(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    standoff: float = 0.5,
    lateral: tuple[float, float] = (0.0, 0.0),
    tilt: tuple[float, float] = (0.0, 0.0),
) -> None:
    """Place the vehicle so its grapple pin faces the end-effector mouth.

    standoff: distance from the mouth to the pin tip along the approach axis [m].
              Negative puts the tip inside the cavity.
    lateral:  pin offset from the approach axis, in the end-effector x/y [m].
    tilt:     pin axis rotation about the end-effector x and y axes [rad],
              pivoting about the pin tip.

    Uses the arm's current pose. Vehicle velocity is left unchanged.
    """
    mujoco.mj_kinematics(model, data)
    mouth = data.site("lee_mouth")
    R_l = mouth.xmat.reshape(3, 3)
    x_l, y_l, z_l = R_l[:, 0], R_l[:, 1], R_l[:, 2]

    # The pin runs along vehicle +x and must point into the cavity, i.e. along -z_l.
    R_v = R_l @ _rot_x(tilt[0]) @ _rot_y(tilt[1]) @ R_l.T @ np.column_stack([-z_l, y_l, x_l])
    tip_world = mouth.xpos + standoff * z_l + lateral[0] * x_l + lateral[1] * y_l
    tip_local = model.site("pin_tip").pos
    pos = tip_world - R_v @ tip_local

    quat = np.empty(4)
    mujoco.mju_mat2Quat(quat, R_v.flatten())
    adr = model.joint("vehicle_free").qposadr[0]
    data.qpos[adr : adr + 3] = pos
    data.qpos[adr + 3 : adr + 7] = quat


def set_vehicle_velocity(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    drift: tuple[float, float, float] = (0.0, 0.0, 0.0),
    tumble: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> None:
    """Give the vehicle a drift and a tumble, both expressed in the end-effector mouth frame.

    drift:  velocity of the vehicle's centre of mass [m/s].
    tumble: angular velocity [rad/s].
    """
    mujoco.mj_kinematics(model, data)
    mujoco.mj_comPos(model, data)
    R_l = data.site("lee_mouth").xmat.reshape(3, 3)
    body = data.body("vehicle")
    w_world = R_l @ np.asarray(tumble, dtype=float)
    v_com = R_l @ np.asarray(drift, dtype=float)
    # Free-joint velocities are the body origin's linear velocity (world frame)
    # and the angular velocity in the body frame.
    v_origin = v_com + np.cross(w_world, body.xpos - body.xipos)
    dof = model.joint("vehicle_free").dofadr[0]
    data.qvel[dof : dof + 3] = v_origin
    data.qvel[dof + 3 : dof + 6] = body.xmat.reshape(3, 3).T @ w_world


def pin_axis_error(model: mujoco.MjModel, data: mujoco.MjData) -> float:
    """Angle between the pin axis and the approach axis [rad]. Zero when aligned."""
    z_l = data.site("lee_mouth").xmat.reshape(3, 3)[:, 2]
    pin = data.body("vehicle").xmat.reshape(3, 3)[:, 0]
    return float(np.arccos(np.clip(-pin @ z_l, -1.0, 1.0)))


def reset(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    standoff: float = 0.5,
    lateral: tuple[float, float] = (0.0, 0.0),
    tilt: tuple[float, float] = (0.0, 0.0),
) -> None:
    """Arm at the ready pose, vehicle at rest in front of the end effector."""
    mujoco.mj_resetData(model, data)
    set_arm(model, data, READY_POSE)
    place_vehicle(model, data, standoff, lateral, tilt)
    mujoco.mj_forward(model, data)
