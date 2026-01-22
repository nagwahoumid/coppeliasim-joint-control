import sys
import time
from pathlib import Path

print("[DEBUG] phase1_connect.py loaded (updated)")
print("[DEBUG] __file__ =", Path(__file__).resolve())

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


def safe_get_handle(sim, name: str):
    """Safely get an object handle by name/path. Returns None if not found."""
    try:
        h = sim.getObject(name)
        return h
    except Exception as e:
        print(f"[WARN] Could not find object '{name}'. Error: {e}")
        return None


def list_some_objects(sim, limit=30):
    """List a handful of objects in the scene (names + handles)."""
    try:
        # Try getting from sim.handle_scene first, else use sim.handle_world
        root_handle = None
        try:
            root_handle = sim.handle_scene
        except AttributeError:
            try:
                root_handle = sim.handle_world
            except AttributeError:
                print("[WARN] Could not find handle_scene or handle_world")
                return
        
        # Get objects in tree (first level depth)
        try:
            objects = sim.getObjectsInTree(root_handle, sim.handle_all, 1)
            print(f"\nFound {len(objects)} objects in scene (showing first {min(limit, len(objects))}):")
            for i, handle in enumerate(objects[:limit]):
                try:
                    name = sim.getObjectName(handle)
                    print(f"  [{i+1}] Handle: {handle}, Name: {name}")
                except Exception as e:
                    print(f"  [{i+1}] Handle: {handle}, Name: <error: {e}>")
        except Exception as e:
            print(f"[WARN] Could not list objects: {e}")
    except Exception as e:
        print(f"[WARN] Error listing objects: {e}")


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

    client = RemoteAPIClient(host="localhost", port=23000)
    sim = client.getObject("sim")

    print("Connected to CoppeliaSim.")
    
    # Print useful debugging info
    try:
        scene_name = sim.getStringParam(sim.stringparam_scene_name)
        print("Scene name:", scene_name)
    except Exception as e:
        print(f"[WARN] Could not get scene name: {e}")
    
    print("Simulation state:", sim.getSimulationState())   # 0/1/2… depends on Coppelia
    print("Simulation time:", sim.getSimulationTime())
    
    # List objects in the scene
    list_some_objects(sim)

    # Start sim, wait a bit, then check time again
    print("\nStarting simulation...")
    sim.startSimulation()
    time.sleep(1.0)
    print("Simulation time after 1s:", sim.getSimulationTime())
    sim.stopSimulation()
    print("Simulation stopped.")
    
    print("\nPhase 1 complete: Connection and simulation control verified.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)