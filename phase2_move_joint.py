#!/usr/bin/env python3
"""
Phase 2: Move a joint in CoppeliaSim using ZMQ Remote API.
Moves panda_joint1 by a small safe delta.
"""

import sys
import time
from pathlib import Path

# --- CoppeliaSim ZMQ Remote API (macOS) ------------------------------------
# The ZMQ python client lives inside the CoppeliaSim app bundle.
# We add that folder to PYTHONPATH so `import coppeliasim_zmqremoteapi_client` works.
# (Note: `import zmqRemoteApi` is deprecated but still works)
# NOTE (CoppeliaSim 4.1+ layout):
# The ZMQ Remote API Python client is typically located at:
#   <CoppeliaSim.app>/Contents/Resources/programming/zmqRemoteApi/clients/python
# That folder should contain:
#   - zmqRemoteApi/   (package)
#   - src/            (package)
# Some builds also ship a minimal `Contents/Resources/python` folder WITHOUT zmqRemoteApi.
# So we search multiple candidate folders inside the .app.
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

# Candidate *internal* folders within the .app that may contain the ZMQ Remote API python client
COPPELIA_INTERNAL_PY_CANDIDATES = [
    "Contents/Resources/programming/zmqRemoteApi/clients/python",  # common
    "Contents/Resources/programming/zmqRemoteApi/clients/python/zmqRemoteApi",  # fallback (some zips)
    "Contents/Resources/python",  # older/alternate
]


def find_coppelia_python_folder() -> str:
    """Return an app-bundled folder we can add to sys.path so `import zmqRemoteApi` works."""

    def is_valid_zmq_client(py_path: Path) -> bool:
        # Accept either:
        #   py_path/zmqRemoteApi + py_path/src
        # or:
        #   py_path/zmqRemoteApi/src  (src nested)
        if (py_path / "zmqRemoteApi").is_dir():
            if (py_path / "src").is_dir():
                return True
            if (py_path / "zmqRemoteApi" / "src").is_dir():
                return True
        return False

    def normalize(py_path: Path) -> Path:
        # If user points us at .../python/zmqRemoteApi, go one level up
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


def ensure_coppelia_python_path() -> None:
    """Make sure we import the *bundled* zmqRemoteApi, not a local folder."""
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


def find_joint_handle_by_object_name(sim, wanted_name: str):
    """Find a joint handle by searching through all joints in the scene by name."""
    joints = sim.getObjectsInTree(sim.handle_scene, sim.object_joint_type, 0)
    for h in joints:
        if sim.getObjectName(h) == wanted_name:
            return h
    return None


def main() -> None:
    # IMPORTANT:
    # - In CoppeliaSim: Modules -> Connectivity -> ZMQ remote API server (running)
    # - Default port is usually 23000
    ensure_coppelia_python_path()

    # Show the first few search paths so we can debug import resolution
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
        print("Connected to CoppeliaSim (Phase 2)")
    except Exception as e:
        print(f"[ERROR] Failed to connect to CoppeliaSim: {e}")
        raise

    # Find joint handle by name
    print("\n[STEP 2] Searching for joint 'panda_joint1'...")
    wanted_name = "panda_joint1"
    joint_handle = find_joint_handle_by_object_name(sim, wanted_name)
    
    if joint_handle is None:
        print(f"[ERROR] Could not find joint '{wanted_name}'")
        print("\nAvailable joints in scene:")
        try:
            joints = sim.getObjectsInTree(sim.handle_scene, sim.object_joint_type, 0)
            for h in joints:
                name = sim.getObjectName(h)
                print(f"  - {name}")
        except Exception as e:
            print(f"[WARN] Could not list joints: {e}")
        sys.exit(1)
    
    print(f"Found joint handle: {joint_handle}")
    
    # Get current joint position
    print("\n[STEP 3] Reading current joint position...")
    try:
        current = sim.getJointPosition(joint_handle)
        print(f"Current joint position: {current:.6f} radians")
    except Exception as e:
        print(f"[ERROR] Could not read joint position: {e}")
        raise

    # Start simulation
    print("\n[STEP 4] Starting simulation...")
    try:
        sim.startSimulation()
        print("Simulation started.")
    except Exception as e:
        print(f"[ERROR] Failed to start simulation: {e}")
        raise

    # Move joint by small delta
    print("\n[STEP 5] Moving joint by 0.2 radians...")
    try:
        sim.setJointTargetPosition(joint_handle, current + 0.2)
        print(f"Target position set to: {current + 0.2:.6f} radians")
    except Exception as e:
        print(f"[ERROR] Failed to set joint target position: {e}")
        sim.stopSimulation()
        raise

    # Wait for motion to be visible (use simulation time, not wall-clock)
    print("\n[STEP 6] Waiting ~1.0s of SIMULATION time for motion...")
    try:
        t0 = sim.getSimulationTime()
        # Wait until simulation advances by 1 second
        while sim.getSimulationTime() < t0 + 1.0:
            time.sleep(0.05)
    except Exception as e:
        print(f"[WARN] Could not wait on sim time, falling back to wall-clock sleep: {e}")
        time.sleep(1.0)

    # Read back joint position to verify motion
    print("\n[STEP 6.1] Reading joint position after motion...")
    try:
        new_pos = sim.getJointPosition(joint_handle)
        print(f"[CHECK] Joint position after motion: {new_pos:.6f} radians")
        print(f"[CHECK] Delta moved: {new_pos - current:.6f} radians")
        # Soft pass/fail message
        if abs(new_pos - (current + 0.2)) < 0.02:
            print("[PASS] Joint reached near the commanded target (within 0.02 rad).")
        else:
            print("[WARN] Joint did not reach expected target. This can happen if the joint is not in position control mode.")
    except Exception as e:
        print(f"[WARN] Could not read joint position after motion: {e}")

    # Stop simulation
    print("\n[STEP 7] Stopping simulation...")
    try:
        sim.stopSimulation()
        print("Simulation stopped.")
    except Exception as e:
        print(f"[WARN] Error stopping simulation: {e}")

    print("\nPhase 2 complete: Command sent and motion check performed (see [CHECK]/[PASS]/[WARN]).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
