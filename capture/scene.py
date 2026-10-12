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

# Free-flying vehicles are captured about 10 m from the station. Here that is the
# distance from the surface the arm stands on to the tip of the grapple pin.
CAPTURE_DISTANCE = 10.0
# How far the end effector waits from the pin before it starts. Not sourced.
HOVER_DISTANCE = 2.0

# End-effector mouth at the hover point, pointing straight away from the station.
# Found by inverse kinematics from the best-conditioned of 29 solutions.
READY_POSE = np.array([1.039915, -1.514656, -0.644822, 0.795967, 2.990447, 0.056141, 2.985896])
READY_MOUTH = np.array([1.5, 1.0, CAPTURE_DISTANCE - HOVER_DISTANCE])

# End-effector cavity, in the `lee` body frame (z is the approach axis).
CAVITY_Z0, CAVITY_Z1 = 0.5, 1.0
CAVITY_RADIUS = 0.20
WALL_THICKNESS = 0.04
WALL_SEGMENTS = 16
WALL_MASS = 40.0
# The rim the fixture plate seats on: a ring of spheres whose tops lie in the mouth plane.
RIM_SPHERES = 32
RIM_BIT = 4  # collision bit shared only by the rim spheres and the fixture plate

# Snare actuator travel [m]. The bars start 0.1 m from the axis; commanding past the
# pin surface makes them press on it. The carriage pulls the closed snare inward.
SNARE_TRAVEL = 0.08
CARRIAGE_TRAVEL = 0.1

# Canadarm2's end effector has four latches that clamp the interface after pull-in,
# with 64,054 N in total (Walker and Vandersluis, 1995). Modelled as four forces
# pressing the fixture plate onto the rim, at this radius from the approach axis.
LATCH_FORCE = 64054.0
LATCH_RADIUS = 0.2

# Stiffest fixture mount the 2 ms timestep can integrate stably [N m/rad].
MAX_FIXTURE_STIFFNESS = 5.0e4


def _add_cavity_wall(spec: mujoco.MjSpec, segments: int = WALL_SEGMENTS) -> None:
    """Approximate a hollow cylinder with a ring of boxes.

    MuJoCo collides convex shapes, so one mesh cannot represent a cavity.
    """
    lee = spec.body("lee_tool")
    r_mid = CAVITY_RADIUS + WALL_THICKNESS / 2
    # Half-width chosen so neighbouring boxes overlap at the inner radius.
    half_w = (CAVITY_RADIUS + WALL_THICKNESS) * np.tan(np.pi / segments)
    half_len = (CAVITY_Z1 - CAVITY_Z0) / 2
    for i in range(segments):
        phi = 2 * np.pi * i / segments
        theta = phi + np.pi / 2  # box x axis is tangential
        lee.add_geom(
            name=f"lee_wall_{i}",
            type=mujoco.mjtGeom.mjGEOM_BOX,
            size=[half_w, WALL_THICKNESS / 2, half_len],
            pos=[r_mid * np.cos(phi), r_mid * np.sin(phi), (CAVITY_Z0 + CAVITY_Z1) / 2],
            quat=[np.cos(theta / 2), 0, 0, np.sin(theta / 2)],
            mass=WALL_MASS / segments,
            rgba=[0.85, 0.72, 0.3, 0.35],  # see-through, so the snare is visible
        )


def _add_rim(spec: mujoco.MjSpec, spheres: int = RIM_SPHERES) -> None:
    """Give the fixture plate its own surface to seat on: a ring of spheres on the rim.

    The wall boxes overlap at their edges, so a tilted plate touched two of them at the
    same place, and the solver returned forces of up to 2 MN that threw the vehicle off
    (build log, 2026-10-11). Each sphere gives the plate one contact with one normal.
    The plate then collides with the spheres only, and nothing else collides with them.
    """
    lee = spec.body("lee_tool")
    r = WALL_THICKNESS / 2
    r_mid = CAVITY_RADIUS + r
    for i in range(spheres):
        phi = 2 * np.pi * i / spheres
        lee.add_geom(
            name=f"lee_rim_{i}",
            type=mujoco.mjtGeom.mjGEOM_SPHERE,
            size=[r, 0, 0],
            pos=[r_mid * np.cos(phi), r_mid * np.sin(phi), CAVITY_Z1 - r],
            contype=RIM_BIT,
            conaffinity=0,
            density=0,
            rgba=[0.85, 0.72, 0.3, 0.35],
        )
    plate = spec.geom("gf_plate")
    plate.contype, plate.conaffinity = 0, RIM_BIT


SKY = MESH_DIR / "sky.png"  # painted by scripts/make_sky.py


def _use_sky(spec: mujoco.MjSpec) -> None:
    """Replace the flat black background with the painted starry sky. Appearance only."""
    sky = next(t for t in spec.textures if t.type == mujoco.mjtTexture.mjTEXTURE_SKYBOX)
    sky.builtin = mujoco.mjtBuiltin.mjBUILTIN_NONE
    sky.file = str(SKY)
    sky.gridsize = [6, 1]
    sky.gridlayout = "RLUDFB"
    sky.width = sky.height = 0


SKY_RADIUS = 400.0  # [m]; far beyond everything else, inside the camera's far limit
ORBIT_RATE = 2 * np.pi / (92.7 * 60)  # [rad/s]; one turn per orbit of about 92.7 minutes


def _use_moving_sky(spec: mujoco.MjSpec, like: mujoco.MjModel) -> None:
    """Paint the sky on the inside of a huge sphere that can be turned. Appearance only.

    MuJoCo's own background cannot move. The sphere hangs on a body that physics ignores
    (a "mocap" body), so turning it costs nothing and touches nothing. `like` is the same
    model built without the sphere: its sense of the scene's size is kept, so that the
    camera's near and far limits do not change.
    """
    spec.stat.extent = like.stat.extent
    spec.stat.center = like.stat.center
    spec.visual.map.zfar = 2.5 * SKY_RADIUS / like.stat.extent

    # A sphere of triangles wound so that their faces point inward.
    rings, sectors = 24, 48
    lat = np.linspace(0, np.pi, rings + 1)
    lon = np.linspace(0, 2 * np.pi, sectors, endpoint=False)
    vertices = np.array([[np.sin(a) * np.cos(b), np.sin(a) * np.sin(b), np.cos(a)] for a in lat for b in lon])
    faces = []
    for i in range(rings):
        for j in range(sectors):
            a, b = i * sectors + j, i * sectors + (j + 1) % sectors
            c, d = a + sectors, b + sectors
            faces += [[a, b, c], [b, d, c]]
    spec.add_mesh(
        name="sky_sphere",
        uservert=(SKY_RADIUS * vertices).flatten(),
        userface=np.array(faces).flatten(),
        inertia=mujoco.mjtMeshInertia.mjMESH_INERTIA_SHELL,
    )
    texture = spec.add_texture(
        name="sky_cube", type=mujoco.mjtTexture.mjTEXTURE_CUBE, file=str(SKY), gridsize=[6, 1], gridlayout="RLUDFB......"
    )
    material = spec.add_material(name="sky", specular=0, shininess=0)
    material.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = texture.name
    body = spec.worldbody.add_body(name="sky", mocap=True)
    body.add_geom(
        name="sky", type=mujoco.mjtGeom.mjGEOM_MESH, meshname="sky_sphere", material="sky",
        contype=0, conaffinity=0, density=0,
    )  # fmt: skip


def turn_sky(model: mujoco.MjModel, data: mujoco.MjData, angle: float) -> None:
    """Turn the moving sky to `angle` [rad] about the station's orbit axis (world y here).

    A station that keeps one side toward the Earth turns once per orbit, so from on board
    the stars wheel past at that rate.
    """
    if model.nmocap:
        data.mocap_quat[model.body("sky").mocapid[0]] = [np.cos(angle / 2), 0.0, np.sin(angle / 2), 0.0]


def meshes_available() -> bool:
    names = [*geometry.ARM_MESHES.values(), *geometry.VEHICLE_MESHES, *geometry.STATION_MESHES]
    return all((MESH_DIR / f"{n}.stl").exists() for n in names)


def _use_meshes(spec: mujoco.MjSpec) -> None:
    """Show the downloaded models in place of the stand-in shapes.

    Appearance only: collisions still use the simple shapes, now hidden,
    and masses are unchanged.
    """
    visual = dict(type=mujoco.mjtGeom.mjGEOM_MESH, contype=0, conaffinity=0, density=0)
    for geom in spec.geoms:
        # arm stand-ins, the end-effector shell, the vehicle hull, and the station box
        if geom.name.startswith(("v_", "lee_", "hull_", "truss")):
            geom.rgba[3] = 0.0
    for body, mesh in geometry.ARM_MESHES.items():
        spec.add_mesh(name=mesh, file=str(MESH_DIR / f"{mesh}.stl"))
        spec.body(body).add_geom(name=f"mesh_{mesh}", meshname=mesh, rgba=[0.93, 0.93, 0.91, 1], **visual)
    for mesh, rgba in geometry.VEHICLE_MESHES.items():
        spec.add_mesh(name=mesh, file=str(MESH_DIR / f"{mesh}.stl"))
        spec.body("vehicle").add_geom(name=f"mesh_{mesh}", meshname=mesh, rgba=list(rgba), **visual)
    for mesh, rgba in geometry.STATION_MESHES.items():
        spec.add_mesh(name=mesh, file=str(MESH_DIR / f"{mesh}.stl"))
        spec.worldbody.add_geom(name=f"mesh_{mesh}", meshname=mesh, rgba=list(rgba), **visual)


def _set_friction(spec: mujoco.MjSpec, friction: float) -> None:
    for geom in spec.geoms:
        if geom.contype or geom.conaffinity:
            geom.friction[0] = friction


def _pin_geoms(spec: mujoco.MjSpec) -> list:
    """The shapes that meet where the snare holds the pin: the pin, its tip, and the three bars."""
    bars = [g for i in range(3) for g in spec.body(f"snare_{i}").geoms]
    return [spec.geom("gf_pin"), spec.geom("gf_tip"), *bars]


def _rim_geoms(spec: mujoco.MjSpec) -> list:
    """The shapes that meet where the fixture seats: the plate and the rim spheres."""
    return [spec.geom("gf_plate"), *(g for g in spec.geoms if g.name.startswith("lee_rim_"))]


def _mount_fixture_on_spring(spec: mujoco.MjSpec, stiffness: float) -> None:
    """Let the grapple fixture rock on its base against a rotational spring."""
    if not 0 < stiffness <= MAX_FIXTURE_STIFFNESS:
        raise ValueError(f"fixture stiffness must be in (0, {MAX_FIXTURE_STIFFNESS:g}] N m/rad")
    inertia = 0.25  # fixture about its base, roughly [kg m^2]
    spec.body("fixture").add_joint(
        name="fixture_mount",
        type=mujoco.mjtJoint.mjJNT_BALL,
        pos=[1.42, -0.41, -2.085],  # centre of the plate's base
        stiffness=stiffness,
        damping=2 * 0.05 * np.sqrt(stiffness * inertia),  # 5% of critical
    )


def build_model(
    meshes: bool | None = None,
    friction: float | None = None,
    fixture_stiffness: float | None = None,
    snare_force: float | None = None,
    rim: str = "spheres",
    rim_spheres: int = RIM_SPHERES,
    wall_segments: int = WALL_SEGMENTS,
    timestep: float | None = None,
    contact_time: float | None = None,
    friction_pin: float | None = None,
    friction_rim: float | None = None,
    pull_in_force: float | None = None,
    backdrive: float | None = None,
    vehicle_mass: float | None = None,
    moving_sky: bool = False,
) -> mujoco.MjModel:
    """Build the scene.

    meshes:   show the downloaded 3D models. Defaults to using them when they have
              been fetched (scripts/fetch_assets.py). The physics is the same either way.
    friction: sliding friction for every contact. Defaults to the model file's 0.3.
    fixture_stiffness: mount the grapple fixture on a rotational spring of this
              stiffness [N m/rad] instead of rigidly. Honda et al. (2014) found the
              fixture base's stiffness strongly affects early capture.
    snare_force: force limit of the drive that closes the snare bars [N]. Defaults
              to the model file's 1,500 N, which is not sourced.
    moving_sky: paint the sky on a sphere that scene.turn_sky can turn, for the viewer.
              Needs the painted sky (scripts/make_sky.py); ignored without it.
    rim:      what the fixture plate seats on. "spheres" is a ring of spheres on the rim.
              "boxes" is the tops of the wall boxes, as before 2026-10-11; kept only to
              reproduce the contact failure that led to the change.

    Options that change how the same objects are represented:
    rim_spheres:   how many spheres make the rim.
    wall_segments: how many boxes make the cavity wall.
    timestep:      simulation step [s]. Defaults to the model file's 2 ms.
    contact_time:  time constant of every contact's stiffness [s]; smaller is stiffer.
                   Defaults to MuJoCo's 0.02.

    Options that change a physical number:
    friction_pin:  friction where the snare holds the pin (pin, tip, and bars), set after `friction`.
    friction_rim:  friction where the fixture seats (plate and rim), set after `friction`.
    pull_in_force: force limit of the carriage drive [N]. Defaults to 4,893.
    backdrive:     torque needed to back-drive each arm joint [N m]. Defaults to 200.
    vehicle_mass:  mass of the vehicle's hull [kg], split between its two modules as in the
                   model file. Defaults to 7,000.
    """
    if rim not in ("spheres", "boxes"):
        raise ValueError(f"unknown rim: {rim}")
    spec = mujoco.MjSpec.from_file(str(BASE_XML))
    _add_cavity_wall(spec, wall_segments)
    if rim == "spheres":
        _add_rim(spec, rim_spheres)
    if friction is not None:
        _set_friction(spec, friction)
    if fixture_stiffness is not None:
        _mount_fixture_on_spring(spec, fixture_stiffness)
    if snare_force is not None:
        spec.actuator("a_snare").forcerange = [-snare_force, snare_force]
    if friction_pin is not None:
        for geom in _pin_geoms(spec):
            geom.friction[0] = friction_pin
    if friction_rim is not None:
        for geom in _rim_geoms(spec):
            geom.friction[0] = friction_rim
    if pull_in_force is not None:
        spec.actuator("a_carriage").forcerange = [-pull_in_force, pull_in_force]
    if backdrive is not None:
        for name in ARM_JOINTS:
            spec.joint(name).frictionloss = backdrive
    if vehicle_mass is not None:
        hull = [spec.geom("hull_cargo"), spec.geom("hull_service")]
        scale = vehicle_mass / sum(g.mass for g in hull)
        for g in hull:
            g.mass *= scale
    if timestep is not None:
        spec.option.timestep = timestep
    if contact_time is not None:
        for geom in spec.geoms:
            if geom.contype or geom.conaffinity:
                geom.solref = [contact_time, 1.0]
    if meshes is None:
        meshes = meshes_available()
    if meshes:
        _use_meshes(spec)
    if meshes and SKY.exists():
        if moving_sky:
            _use_moving_sky(spec, like=spec.compile())
        else:
            _use_sky(spec)
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


def apply_latch(model: mujoco.MjModel, data: mujoco.MjData, fraction: float) -> None:
    """Add the latches' clamping force to data.qfrc_applied.

    fraction runs from 0 (released) to 1 (full force). Four equal forces pull the
    vehicle onto the end effector, and the end effector onto the vehicle, at points
    spaced around the rim. The caller clears data.qfrc_applied each step.
    """
    if fraction <= 0:
        return
    mouth = data.site("lee_mouth")
    R_l = mouth.xmat.reshape(3, 3)
    pull = 0.25 * fraction * LATCH_FORCE * R_l[:, 2]
    vehicle, tool = model.body("vehicle").id, model.body("lee_tool").id
    zero = np.zeros(3)
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        point = mouth.xpos + LATCH_RADIUS * (dx * R_l[:, 0] + dy * R_l[:, 1])
        mujoco.mj_applyFT(model, data, -pull, zero, point, vehicle, data.qfrc_applied)
        mujoco.mj_applyFT(model, data, pull, zero, point, tool, data.qfrc_applied)


def relative_speed(model: mujoco.MjModel, data: mujoco.MjData) -> float:
    """Speed of the pin tip relative to the end-effector mouth [m/s]."""
    v_tip, v_mouth = np.empty(6), np.empty(6)
    mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_SITE, model.site("pin_tip").id, v_tip, 0)
    mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_SITE, model.site("lee_mouth").id, v_mouth, 0)
    return float(np.linalg.norm(v_tip[3:] - v_mouth[3:]))


def pin_axis(data: mujoco.MjData) -> np.ndarray:
    """Unit vector along the grapple pin, base to tip, in the world frame."""
    return data.body("fixture").xmat.reshape(3, 3)[:, 0]


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
    standoff: float = HOVER_DISTANCE,
    lateral: tuple[float, float] = (0.0, 0.0),
    tilt: tuple[float, float] = (0.0, 0.0),
    roll: float = 0.0,
) -> None:
    """Place the vehicle so its grapple pin faces the end-effector mouth.

    standoff: distance from the mouth to the pin tip along the approach axis [m].
              Negative puts the tip inside the cavity.
    lateral:  pin offset from the approach axis, in the end-effector x/y [m].
    tilt:     pin axis rotation about the end-effector x and y axes [rad],
              pivoting about the pin tip.
    roll:     rotation of the vehicle about its own pin axis [rad]. The pin is
              symmetric, so this moves the hull and its mass around the pin
              without changing where the pin points.

    Uses the arm's current pose. Vehicle velocity is left unchanged.
    """
    mujoco.mj_kinematics(model, data)
    mouth = data.site("lee_mouth")
    R_l = mouth.xmat.reshape(3, 3)
    x_l, y_l, z_l = R_l[:, 0], R_l[:, 1], R_l[:, 2]

    # The pin runs along vehicle +x and must point into the cavity, i.e. along -z_l.
    R_v = R_l @ _rot_x(tilt[0]) @ _rot_y(tilt[1]) @ R_l.T @ np.column_stack([-z_l, y_l, x_l]) @ _rot_x(roll)
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
    com = data.subtree_com[model.body("vehicle").id]  # hull and fixture together
    w_world = R_l @ np.asarray(tumble, dtype=float)
    v_com = R_l @ np.asarray(drift, dtype=float)
    # Free-joint velocities are the body origin's linear velocity (world frame)
    # and the angular velocity in the body frame.
    v_origin = v_com + np.cross(w_world, body.xpos - com)
    dof = model.joint("vehicle_free").dofadr[0]
    data.qvel[dof : dof + 3] = v_origin
    data.qvel[dof + 3 : dof + 6] = body.xmat.reshape(3, 3).T @ w_world


def pin_axis_error(model: mujoco.MjModel, data: mujoco.MjData) -> float:
    """Angle between the pin axis and the approach axis [rad]. Zero when aligned."""
    z_l = data.site("lee_mouth").xmat.reshape(3, 3)[:, 2]
    return float(np.arccos(np.clip(-pin_axis(data) @ z_l, -1.0, 1.0)))


def reset(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    standoff: float = HOVER_DISTANCE,
    lateral: tuple[float, float] = (0.0, 0.0),
    tilt: tuple[float, float] = (0.0, 0.0),
    roll: float = 0.0,
) -> None:
    """Arm at the ready pose, vehicle at rest in front of the end effector.

    With the defaults the grapple pin's tip is at the capture point, CAPTURE_DISTANCE
    from the station.
    """
    mujoco.mj_resetData(model, data)
    set_arm(model, data, READY_POSE)
    place_vehicle(model, data, standoff, lateral, tilt, roll)
    mujoco.mj_forward(model, data)
