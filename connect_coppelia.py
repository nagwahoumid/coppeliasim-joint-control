#!/usr/bin/env python3
"""
Minimal CoppeliaSim ZMQ Remote API connection test.
Connects to CoppeliaSim on localhost:23000 and prints simulation time.
"""

import sys
from pathlib import Path

# Add CoppeliaSim ZMQ Remote API path
coppelia_path = '/Applications/coppeliaSim.app/Contents/Resources/programming/zmqRemoteApi/clients/python'
sys.path.insert(0, coppelia_path)

# Also add src folder for new module name
src_path = Path(coppelia_path) / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

# Try new module name first (no warning), fallback to deprecated zmqRemoteApi
try:
    from coppeliasim_zmqremoteapi_client import RemoteAPIClient
except ImportError:
    from zmqRemoteApi import RemoteAPIClient

# Connect to CoppeliaSim
print("Connecting to CoppeliaSim on localhost:23000...")
client = RemoteAPIClient('localhost', 23000)
sim = client.getObject('sim')

# Confirm connection
print("✓ Connection successful!")

# Read and print simulation time
sim_time = sim.getSimulationTime()
print(f"Current simulation time: {sim_time:.6f} seconds")
