# CoppeliaSim ZMQ Control Experiments – Franka Panda

This repository presents a set of incremental experiments implementing a custom joint-space kinematic controller for a Franka Emika Panda robot in CoppeliaSim, using the ZMQ Remote API and Python.

The personal project aims to control joint movements from outside the simulator, watch how the robot moves in a physics-based simulation, and study how well the controller tracks the desired paths and where it falls short. Instead of using built-in motion planners or inverse kinematics solvers, all control logic is written in Python and runs outside the simulator.

## Overview

CoppeliaSim is a robot simulation platform that simulates and visualise robots using physics. With the ZMQ Remote API, you can connect external programs to CoppeliaSim over a network to control and monitor robots in real time.

This project focuses on learning robot joint control via Python, specifically:
- Establishing reliable communication with CoppeliaSim
- Retrieving joint handles and reading joint states
- Commanding joint target positions
- Observing the relationship between commanded and actual joint positions

## Project Structure

The project consists of three phase scripts, each building on the previous:

- phase1_connect.py: Establishes ZMQ connection and verifies basic simulator communication
- phase2_move_joint.py: Commands a single joint to move by a fixed offset and verifies motion
- phase3_sine_joint.py: Implements continuous sine-wave joint control with tracking error analysis

All scripts include automatic detection of the CoppeliaSim ZMQ Remote API client library on macOS, with fallback support for both the new (`coppeliasim_zmqremoteapi_client`) and deprecated (`zmqRemoteApi`) import names.

## Phases breakdown

### Phase 1 – Simulator connection

File: `phase1_connect.py`

Establishes ZMQ connection to CoppeliaSim running on `localhost:23000`. The script:
- Auto-detects the CoppeliaSim ZMQ Remote API client library path
- Connects to the simulator and retrieves the `sim` object
- Prints scene information, simulation state, and available objects
- Starts and stops the simulation to verify control capability

Outcome: Confirms that Python can communicate with CoppeliaSim and that simulation control commands are accepted.

### Phase 2 – Single Joint Position Control

File: `phase2_move_joint.py`

Commands `panda_joint1` to move by a fixed offset and verifies the motion. The script:
- Searches for joint handles by scanning all joints in the scene and matching object names
- Reads the initial joint position before starting simulation
- Commands the joint to move by 0.2 radians using `sim.setJointTargetPosition()`
- Waits for 1 second of simulation time (not wall-clock time)
- Reads the updated joint position and computes the tracking error

Outcome: Verifies that joint handle lookup works correctly, target position commands are accepted, and basic joint actuation occurs. The script reports whether the joint reached the commanded target within a tolerance, which depends on the joint's control mode and dynamics.

### Phase 3 – Continuous sine wave joint control

File: `phase3_sine_joint.py`

Implements a continuous control loop that commands `panda_joint1` to follow a sine-wave trajectory. The script:
- Commands the joint to follow: `q_des = q0 + 0.3 * sin(2π * 0.2 * t)` for 8 seconds of simulation time
- Runs a control loop at approximately 20 Hz (50 ms sleep between commands)
- Reads actual joint position at each iteration and computes tracking error
- Logs desired vs actual positions every 0.5 seconds
- Computes average absolute tracking error and reports pass/fail based on a 0.05 rad threshold

Outcome: The control loop and communication work correctly. Tracking accuracy depends on:
- Joint control mode (position control vs velocity control vs torque control)
- PID gains configured in CoppeliaSim
- Joint dynamics (inertia, friction, damping)
- Control loop frequency relative to system dynamics

The observed tracking error is a realistic control issue that reflects the physics-based simulation and controller tuning, not a failure of the communication or command interface.

## Observations and learning outcomes (documentation updates)

- Joint Control Modes: The behavior of `setJointTargetPosition()` depends on the joint's control mode. Position control mode with appropriate PID tuning yields better tracking than velocity or torque control modes.

- PID Tuning: Tracking performance is sensitive to proportional, integral, and derivative gains. Default gains in CoppeliaSim may not be optimal for all trajectories.

- Control Loop Frequency: Running the control loop at 20 Hz provides reasonable performance for this application, but higher frequencies may improve tracking for faster trajectories.

- Simulation Time vs Wall-Clock Time: Using simulation time for timing ensures consistent behavior regardless of real-time performance, which is important for reproducible experiments.

- Command-Level vs Model-Level Control: This project operates at the command level (setting target positions). Model-level controllers such as inverse kinematics and trajectory planners would be implemented at a higher level and would use these command-level primitives.

- Joint Handle Lookup: Searching for joints by name is more robust than relying on path or alias resolution, which can fail if the scene structure changes.

## Future Work

- PID Gain Tuning: Experiment with different PID parameters to improve tracking accuracy for the sine-wave trajectory.

- Joint Control Mode Analysis: Compare tracking performance across different joint control modes (position, velocity, torque) to understand their trade-offs.

- Multi-Joint Control: Extend the control loop to command multiple joints simultaneously, potentially using inverse kinematics to compute joint targets from end-effector poses.

- Trajectory Generation: Implement more sophisticated trajectory generation (e.g., cubic splines, minimum-jerk trajectories) and compare tracking performance.

- Real-Time Performance: Analyse the relationship between control loop frequency, communication latency, and tracking accuracy.

- Error Analysis: Implement more detailed error metrics like RMS error, maximum error and  steady-state error and visualize tracking performance over time.

## Requirements

- CoppeliaSim 4.10 (or compatible version) installed on macOS
- Python 3 with standard library only (no external dependencies)
- ZMQ Remote API Server enabled in CoppeliaSim (modules to Connectivity to ZMQ remote API server)

The scripts automatically detect the CoppeliaSim ZMQ Remote API client library from the application bundle, so no manual installation or path configuration is required.

## Usage

Each phase script can be run independently:

```bash
python3 phase1_connect.py
python3 phase2_move_joint.py
python3 phase3_sine_joint.py
```

Ensure CoppeliaSim is running with a scene containing the Franka Panda robot, and that the ZMQ Remote API server is enabled on the default port (23000).

## Notes

- The scripts are designed for macOS. For Linux or Windows, update the `COPPELIA_APP_CANDIDATES` paths in each script.
- All scripts include error handling and will print helpful messages if the simulator is not running or if required objects are not found.
- The tracking performance observed in Phase 3 is expected behavior and reflects the physics-based simulation and controller configuration, not a bug in the code.


By Nagwa Houmid El Amrani