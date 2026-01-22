#!/usr/bin/env python3
"""
Phase 4: Kinematic Jacobian controller for Franka Panda end-effector control.
Uses numerical Jacobian computation and damped least squares to move the end-effector
in a circular pattern in the x-y plane.
"""

import sys
import time
import math
from pathlib import Path

# --- CoppeliaSim ZMQ Remote API (macOS) ------------------------------------
# The ZMQ python client lives inside the CoppeliaSim app bundle.
# I add that folder to PYTHONPATH so `import coppeliasim_zmqremoteapi_client` works.
# (Note: `import zmqRemoteApi` is deprecated but still works)
# NOTE (CoppeliaSim 4.1+ layout):
# The ZMQ Remote API Python client is typically located at:
#   <CoppeliaSim.app>/Contents/Resources/programming/zmqRemoteApi/clients/python
# That folder should contain:
#   - zmqRemoteApi/   (package)
#   - src/            (package)
# Some builds also ship a minimal `Contents/Resources/python` folder WITHOUT zmqRemoteApi.
# so i search multiple candidate folders inside the .app.
COPPELIA_APP_CANDIDATES = [
    # Common macOS install locations / app names:
    "/Applications/coppeliaSim.app",
    "/Applications/CoppeliaSimEdu.app",
    "/Applications/CoppeliaSim.app",
    "/Applications/CoppeliaSimEdu_V4_10_0_rev0.app",

    # If you run the app directly from Downloads:
    str(Path.home() / "Downloads" / "coppeliaSim.app"),
    str(Path.home() / "Downloads" / "CoppeliaSimEdu.app"),
    str(Path.home() / "Downloads" / "CoppeliaSim.app"),
    str(Path.home() / "Downloads" / "CoppeliaSimEdu_V4_10_0_rev0.app"),
]

# Candidate internal folders within the .app that may contain the ZMQ Remote API python client
COPPELIA_INTERNAL_PY_CANDIDATES = [
    "Contents/Resources/programming/zmqRemoteApi/clients/python",  # common
    "Contents/Resources/programming/zmqRemoteApi/clients/python/zmqRemoteApi",  # fallback (some zips)
    "Contents/Resources/python",  # older/alternate
]


def find_coppelia_python_folder() -> str:
    """Return an app-bundled folder I can add to sys.path so `import zmqRemoteApi` works."""

    def is_valid_zmq_client(py_path: Path) -> bool:
        # Accept either
        #   py_path/zmqRemoteApi + py_path/src
        # or
        #   py_path/zmqRemoteApi/src  (src nested)
        if (py_path / "zmqRemoteApi").is_dir():
            if (py_path / "src").is_dir():
                return True
            if (py_path / "zmqRemoteApi" / "src").is_dir():
                return True
        return False

    def normalize(py_path: Path) -> Path:
        # If the user points me at .../python/zmqRemoteApi, go one level up
        if py_path.name == "zmqRemoteApi":
            return py_path.parent
        return py_path

    # 1) Try the explicit app candidates first
    for app_path in COPPELIA_APP_CANDIDATES:
        app = Path(app_path)
        for internal in COPPELIA_INTERNAL_PY_CANDIDATES:
            py_path = normalize(app / internal)
            if py_path.exists() and is_valid_zmq_client(py_path):
                return str(py_path)

    # 2) Fallback: try to find any likely CoppeliaSim*.app in /Applications or Downloads
    for base in [Path("/Applications"), Path.home() / "Downloads"]:
        if not base.exists():
            continue
        for app in base.glob("*.app"):
            name = app.name.lower()
            if "coppelia" in name or "coppeliasim" in name:
                for internal in COPPELIA_INTERNAL_PY_CANDIDATES:
                    py_path = normalize(app / internal)
                    if py_path.exists() and is_valid_zmq_client(py_path):
                        return str(py_path)

    raise FileNotFoundError(
        "Could not find CoppeliaSim's ZMQ Remote API python client inside the .app.\n"
        "Fix: confirm your CoppeliaSim app is in /Applications, then locate this folder:\n"
        "  <CoppeliaSim.app>/Contents/Resources/programming/zmqRemoteApi/clients/python\n"
        "That folder should contain a 'zmqRemoteApi' directory and a 'src' directory (or src nested under zmqRemoteApi).\n"
        "If your app name/path differs, update COPPELIA_APP_CANDIDATES."
    )


COPPELIA_PY_PATH = find_coppelia_python_folder()


def mat_mult(A, B):
    """Matrix multiplication: A @ B"""
    rows_A, cols_A = len(A), len(A[0])
    rows_B, cols_B = len(B), len(B[0])
    if cols_A != rows_B:
        raise ValueError("Matrix dimensions incompatible")
    result = [[0.0] * cols_B for _ in range(rows_A)]
    for i in range(rows_A):
        for j in range(cols_B):
            for k in range(cols_A):
                result[i][j] += A[i][k] * B[k][j]
    return result


def mat_transpose(A):
    """Matrix transpose: A^T"""
    return [[A[j][i] for j in range(len(A))] for i in range(len(A[0]))]


def mat_add(A, B):
    """Matrix addition: A + B"""
    return [[A[i][j] + B[i][j] for j in range(len(A[0]))] for i in range(len(A))]


def mat_scale(A, scalar):
    """Matrix scaling: scalar * A"""
    return [[scalar * A[i][j] for j in range(len(A[0]))] for i in range(len(A))]


def mat_eye(n):
    """Identity matrix of size n x n"""
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def vec_norm(v):
    """Vector norm: ||v||"""
    return math.sqrt(sum(x * x for x in v))


def solve_3x3(A, b):
    """Solve 3x3 linear system Ax = b using Cramer's rule"""
    det = (A[0][0] * (A[1][1] * A[2][2] - A[1][2] * A[2][1]) -
           A[0][1] * (A[1][0] * A[2][2] - A[1][2] * A[2][0]) +
           A[0][2] * (A[1][0] * A[2][1] - A[1][1] * A[2][0]))
    
    if abs(det) < 1e-10:
        raise ValueError("Matrix is singular")
    
    det_x = (b[0] * (A[1][1] * A[2][2] - A[1][2] * A[2][1]) -
             A[0][1] * (b[1] * A[2][2] - A[1][2] * b[2]) +
             A[0][2] * (b[1] * A[2][1] - A[1][1] * b[2]))
    
    det_y = (A[0][0] * (b[1] * A[2][2] - A[1][2] * b[2]) -
             b[0] * (A[1][0] * A[2][2] - A[1][2] * A[2][0]) +
             A[0][2] * (A[1][0] * b[2] - b[1] * A[2][0]))
    
    det_z = (A[0][0] * (A[1][1] * b[2] - b[1] * A[2][1]) -
             A[0][1] * (A[1][0] * b[2] - b[1] * A[2][0]) +
             b[0] * (A[1][0] * A[2][1] - A[1][1] * A[2][0]))
    
    return [det_x / det, det_y / det, det_z / det]


def ensure_coppelia_python_path() -> None:
    """Make sure I import the *bundled* zmqRemoteApi, not a local folder."""
    script_dir = Path(__file__).resolve().parent

    # COPPELIA_PY_PATH is auto-detected at import time
    coppelia_path = Path(COPPELIA_PY_PATH)
    if not coppelia_path.exists():
        raise FileNotFoundError(
            f"CoppeliaSim python folder not found at: {COPPELIA_PY_PATH}\n"
            "Fix: move the .app into /Applications, or update COPPELIA_APP_CANDIDATES."
        )

    # Quick sanity: show what Python will see
    # (helps if you're accidentally running a different file)
    print("[INFO] Running:", Path(__file__).resolve())
    print("[INFO] Using COPPELIA_PY_PATH:", COPPELIA_PY_PATH)

    # If you copied a `zmqRemoteApi/` folder into this project, it can shadow the real one.
    # This is exactly what causes: ModuleNotFoundError: No module named 'src'
    local_pkg = script_dir / "zmqRemoteApi"
    if local_pkg.exists() and local_pkg.is_dir():
        print("[WARN] Found local folder:", local_pkg)
        print("[WARN] This can shadow CoppeliaSim's bundled zmqRemoteApi and break imports.")
        print("[WARN] Recommended fix: rename/delete that local folder (e.g., zmqRemoteApi_old).")

    if not (coppelia_path / "src").exists() and not (coppelia_path / "zmqRemoteApi" / "src").exists():
        print("[WARN] Could not find a 'src' package next to zmqRemoteApi.")
        print("[WARN] Expected either:")
        print("       - COPPELIA_PY_PATH/src")
        print("       - COPPELIA_PY_PATH/zmqRemoteApi/src")
        print("[WARN] Open Finder at COPPELIA_PY_PATH and confirm the folder contents.")

    # Put Coppelia's python folder FIRST so it wins the import resolution.
    if COPPELIA_PY_PATH in sys.path:
        sys.path.remove(COPPELIA_PY_PATH)
    sys.path.insert(0, COPPELIA_PY_PATH)
    
    # Also add src folder for new module name (coppeliasim_zmqremoteapi_client)
    src_path = Path(COPPELIA_PY_PATH) / "src"
    if src_path.exists():
        src_path_str = str(src_path)
        if src_path_str not in sys.path:
            sys.path.insert(0, src_path_str)

    # Also, if script_dir is first (it usually is), and contains a shadowing folder,
    # temporarily move script_dir behind COPPELIA_PY_PATH.
    try:
        if str(script_dir) in sys.path:
            sys.path.remove(str(script_dir))
            sys.path.insert(1, str(script_dir))
    except Exception:
        pass


def main() -> None:
    # --- user-tweakable settings ---
    JOINT_PATHS = [
        "/Franka/panda_joint1",
        "/Franka/panda_joint2",
        "/Franka/panda_joint3",
        "/Franka/panda_joint4",
        "/Franka/panda_joint5",
        "/Franka/panda_joint6",
        "/Franka/panda_joint7",
    ]
    TIP_PATHS_TO_TRY = [
        "/Franka/panda_tip",
        "/Franka/panda_hand",
        "/Franka/panda_link7",
        "/Franka/panda_link8",
        # Some Franka models use these names instead:
        "/Franka/Franka_link8",
        "/Franka/Franka_link7",
        "/Franka/Franka_link8_resp",
        "/Franka/Franka_link7_resp",
    ]
    USE_STEPPING = True
    DT = 0.05
    DURATION = 8.0
    EPS = 1e-4  # Finite difference perturbation for numerical Jacobian
    LAMBDA = 0.1  # Damping parameter for damped least squares
    MAX_DQ = 0.05  # Maximum joint velocity per step (rad)
    STEP_SIZE = 0.002  # Desired end-effector motion per step (meters)
    JACOBIAN_UPDATE_PERIOD = 5  # recompute Jacobian every N control steps

    # IMPORTANT:
    # - In CoppeliaSim: Modules to Connectivity to ZMQ remote API server (running)
    # - Default port is usually 23000
    ensure_coppelia_python_path()

    # Show the first few search paths so I can debug import resolution
    print("[INFO] sys.path[0:5]=", sys.path[0:5])

    # Import AFTER path setup
    # Try new module name first (no warning), fallback to deprecated zmqRemoteApi
    try:
        from coppeliasim_zmqremoteapi_client import RemoteAPIClient
    except ImportError:
        try:
            # Fallback to deprecated but still working import
            from zmqRemoteApi import RemoteAPIClient
        except Exception as e:
            print("[ERROR] Failed to import coppeliasim_zmqremoteapi_client or zmqRemoteApi.")
            print("[ERROR] This usually means either:")
            print("  1) COPPELIA_PY_PATH is wrong, OR")
            print("  2) a local folder named 'zmqRemoteApi' is shadowing the real one, OR")
            print("  3) COPPELIA_PY_PATH is missing the 'src' folder.")
            raise

    # Connect to CoppeliaSim
    print("\n[STEP 1] Connecting to CoppeliaSim...")
    try:
        client = RemoteAPIClient(host="localhost", port=23000)
        sim = client.getObject("sim")
        if USE_STEPPING:
            client.setStepping(True)
        print("Connected to CoppeliaSim (Phase 4)")
    except Exception as e:
        print(f"[ERROR] Failed to connect to CoppeliaSim: {e}")
        raise

    # Resolve joint handles
    print("\n[STEP 2] Resolving joint handles...")
    joint_handles = []
    for i, path in enumerate(JOINT_PATHS, 1):
        try:
            handle = sim.getObject(path)
            joint_handles.append(handle)
            name = sim.getObjectName(handle)
            print(f"  Joint {i}: {name} (handle={handle})")
        except Exception as e:
            print(f"[ERROR] Could not find joint at path '{path}': {e}")
            raise

    if len(joint_handles) != 7:
        print(f"[ERROR] Expected 7 joints, found {len(joint_handles)}")
        sys.exit(1)

    # Resolve tip handle
    print("\n[STEP 3] Resolving end-effector tip handle...")
    tip_handle = None
    for path in TIP_PATHS_TO_TRY:
        try:
            tip_handle = sim.getObject(path)
            if tip_handle is not None:
                name = sim.getObjectName(tip_handle)
                print(f"Found tip via path {path}: {name} (handle={tip_handle})")
                break
        except Exception:
            pass

    if tip_handle is None:
        print("[WARN] Could not find tip handle via paths. Searching scene...")
        try:
            # Search for objects containing "tip", "hand", "link7", or "link8" in name
            all_objects = sim.getObjectsInTree(sim.handle_scene, sim.handle_all, 0)
            candidates = []
            for obj in all_objects:
                try:
                    name = sim.getObjectName(obj)
                    name_lower = name.lower()
                    if any(keyword in name_lower for keyword in ["tip", "hand", "link7", "link8"]):
                        candidates.append((name, obj))
                except Exception:
                    pass
            
            if candidates:
                print("Found candidate objects:")
                for name, handle in candidates:
                    print(f"  - {name} (handle={handle})")
                
                # Auto-select best candidate: prefer non-_resp link8, then link8, then link7, then others
                best_candidate = None
                best_priority = -1
                
                for name, handle in candidates:
                    name_lower = name.lower()
                    priority = 0
                    # Prefer link8 over link7
                    if "link8" in name_lower:
                        priority += 10
                    elif "link7" in name_lower:
                        priority += 5
                    # Prefer non-_resp versions
                    if "_resp" not in name_lower:
                        priority += 20
                    # Prefer "tip" or "hand" keywords
                    if "tip" in name_lower or "hand" in name_lower:
                        priority += 2
                    
                    if priority > best_priority:
                        best_priority = priority
                        best_candidate = (name, handle)
                
                if best_candidate:
                    tip_handle = best_candidate[1]
                    print(f"Auto-selected: {best_candidate[0]} (handle={tip_handle})")
                else:
                    # Fallback to first candidate
                    tip_handle = candidates[0][1]
                    print(f"Using first candidate: {candidates[0][0]} (handle={tip_handle})")
            else:
                print("[ERROR] No candidate objects found.")
                sys.exit(1)
        except Exception as e:
            print(f"[ERROR] Could not search scene: {e}")
            sys.exit(1)

    # Start simulation
    print("\n[STEP 4] Starting simulation...")
    try:
        sim.startSimulation()
        print("Simulation started.")
    except Exception as e:
        print(f"[ERROR] Failed to start simulation: {e}")
        raise

    # Control loop
    print("\n[STEP 5] Running Jacobian control loop...")
    print("[CHECK] Format: t=..., |dx|=..., p=[x,y,z], |dq|=...")
    
    last_check_time = -1.0
    loop_start_time = sim.getSimulationTime()
    dq_norms = []
    J = None  # Cache Jacobian
    step_counter = 0
    actual_duration = 0.0  # Initialize in case of early exit

    try:
        while (sim.getSimulationTime() - loop_start_time) < DURATION:
            t_sim = sim.getSimulationTime()
            t = t_sim - loop_start_time
            step_counter += 1

            # Read current joint positions
            q = [sim.getJointPosition(h) for h in joint_handles]

            # Read current tip position (in world frame, -1 means absolute position)
            p = list(sim.getObjectPosition(tip_handle, -1))

            # Define desired motion: circle in x-y plane
            # The Jacobian relates joint velocities to end-effector velocity:
            #   dp/dt = J @ dq/dt
            # i want to move the end-effector in a circle, so i compute a desired
            # velocity dx per step, then solve for the corresponding joint velocities dq.
            dx = [
                STEP_SIZE * math.cos(2 * math.pi * 0.1 * t),
                STEP_SIZE * math.sin(2 * math.pi * 0.1 * t),
                0.0
            ]

            # Compute numerical Jacobian J (3x7) - only when needed
            # The Jacobian J[i,j] = dp[i]/dq[j] tells me how the i-th Cartesian coordinate
            # changes when I move the j-th joint. I compute it numerically by perturbing
            # each joint and measuring the resulting change in end-effector position.
            if J is None or step_counter % JACOBIAN_UPDATE_PERIOD == 0:
                J = [[0.0] * 7 for _ in range(3)]
                for i in range(7):
                    # Perturb joint i
                    q_pert = q[:]  # copy list
                    q_pert[i] += EPS

                    # Set all joints to perturbed configuration
                    for j, h in enumerate(joint_handles):
                        sim.setJointPosition(h, q_pert[j])
                    
                    if USE_STEPPING:
                        client.step()

                    # Read perturbed tip position
                    p_pert = list(sim.getObjectPosition(tip_handle, -1))

                    # Compute Jacobian column: J[:,i] = (p_pert - p) / EPS
                    for k in range(3):
                        J[k][i] = (p_pert[k] - p[k]) / EPS

                    # Restore original joint configuration
                    for j, h in enumerate(joint_handles):
                        sim.setJointPosition(h, q[j])
                    
                    if USE_STEPPING:
                        client.step()

            # Solve for joint velocities using damped least squares
            # Standard least squares: dq = J^T @ (J @ J^T)^(-1) @ dx
            # Damped least squares adds regularization: dq = J^T @ (J @ J^T + lambda^2*I)^(-1) @ dx
            # The damping parameter lambda prevents singularities when J is near-singular
            # (e.g., when the robot is in a singular configuration).
            J_T = mat_transpose(J)
            JJT = mat_mult(J, J_T)
            I = mat_eye(3)
            JJT_damped = mat_add(JJT, mat_scale(I, LAMBDA**2))
            dx_solved = solve_3x3(JJT_damped, dx)
            dq = mat_mult(J_T, [[x] for x in dx_solved])
            dq = [dq[i][0] for i in range(7)]  # flatten to list

            # Clip joint velocities to prevent instability (per-joint)
            dq = [max(-MAX_DQ, min(MAX_DQ, dq_i)) for dq_i in dq]

            # Additional global norm clamp to prevent large |dq| spikes
            dq_norm = vec_norm(dq)
            if dq_norm > MAX_DQ:
                scale = MAX_DQ / dq_norm
                dq = [scale * x for x in dq]
                dq_norm = vec_norm(dq)  # Update norm after scaling

            # Track dq norms for statistics
            dq_norms.append(dq_norm)

            # Apply joint update: q_new = q + dq
            q_new = [q[i] + dq[i] for i in range(7)]
            for j, h in enumerate(joint_handles):
                sim.setJointPosition(h, q_new[j])

            # Log periodically
            if last_check_time < 0 or (t - last_check_time) >= 0.5:
                dx_norm = vec_norm(dx)
                print(f"[CHECK] t={t:.3f}, |dx|={dx_norm:.6f}, p=[{p[0]:.4f},{p[1]:.4f},{p[2]:.4f}], |dq|={dq_norm:.6f}")
                last_check_time = t

            # Step simulation
            if USE_STEPPING:
                client.step()
            else:
                time.sleep(DT)

        # Compute actual duration before stopping simulation
        actual_duration = sim.getSimulationTime() - loop_start_time

    finally:
        # Stop simulation safely
        print("\n[STEP 6] Stopping simulation...")
        try:
            if USE_STEPPING:
                for _ in range(5):
                    try:
                        client.step()
                    except Exception:
                        break
            sim.stopSimulation()
            print("Simulation stopped.")
        except Exception as e:
            print(f"[WARN] Error stopping simulation: {e}")

    # Summary
    print("\n[SUMMARY] Phase 4 complete: Jacobian controller executed.")
    print(f"  - Actual simulation duration: {actual_duration:.3f} seconds")
    if dq_norms:
        avg_dq_norm = sum(dq_norms) / len(dq_norms)
        min_dq_norm = min(dq_norms)
        max_dq_norm = max(dq_norms)
        print(f"  - Average |dq|: {avg_dq_norm:.6f} rad")
        print(f"  - Min |dq|: {min_dq_norm:.6f} rad")
        print(f"  - Max |dq|: {max_dq_norm:.6f} rad")
    print(f"  - Jacobian update period: every {JACOBIAN_UPDATE_PERIOD} control steps")
    print(f"  - Damping parameter (LAMBDA): {LAMBDA}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
