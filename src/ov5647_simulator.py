"""
ov5647_simulator.py — OV5647 Field Node Simulator via Webcam

Simulates the real field deployment where:
1. mmWave RADAR detects movement → wakes up ESP32-P4
2. OV5647 camera captures at 800x640, JPEG Q15, 5fps
3. 30-second clip is streamed via MJPEG to base station

For development, your webcam is degraded to match OV5647 output.
Press SPACEBAR to simulate RADAR trigger (starts 30s clip).
Press 'N' to toggle night/IR mode simulation.
Press 'Q' to quit.

Supports up to 3 simulated nodes from one or more webcam sources.
"""

import cv2
import numpy as np
import time
import threading
from collections import deque
from typing import Optional, List, Callable

from augmentation_pipeline import OV5647Degrader


class SimulatedNode:
    """
    Represents one field-deployed Hashtag sensor node.
    In simulation, each node reads from a webcam and applies OV5647 degradation.
    In deployment, this would read from the ESP32-P4 HTTP MJPEG stream.
    """

    def __init__(
        self,
        node_id: int,
        source: int = 0,
        degrader: Optional[OV5647Degrader] = None,
        target_fps: float = 5.0,
        clip_duration_sec: float = 30.0,
    ):
        self.node_id = node_id
        self.source = source
        self.degrader = degrader or OV5647Degrader()
        self.target_fps = target_fps
        self.clip_duration_sec = clip_duration_sec
        self.frame_interval = 1.0 / target_fps

        # State
        self.online = False
        self.night_mode = False
        self.streaming = False          # True during an active "clip" session
        self.stream_start_time = 0.0
        self.stream_remaining_sec = 0.0

        # Frame buffer
        self._raw_frame: Optional[np.ndarray] = None
        self._degraded_frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._stopped = False
        self._fps = 0.0
        self._ts_ring = deque(maxlen=20)

        # Capture
        self._cap: Optional[cv2.VideoCapture] = None

    def start(self) -> "SimulatedNode":
        """Open the webcam and start the capture thread."""
        self._cap = cv2.VideoCapture(self.source)
        if self._cap.isOpened():
            self.online = True
            print(f"[NODE-{self.node_id}] ONLINE — Source: {'Webcam' if isinstance(self.source, int) else self.source}")
        else:
            print(f"[NODE-{self.node_id}] OFFLINE — Could not open source {self.source}")
            return self

        threading.Thread(target=self._capture_loop, daemon=True).start()
        return self

    def _capture_loop(self):
        """Continuously captures and degrades frames at target FPS."""
        last_frame_time = 0.0

        while not self._stopped:
            if not self._cap or not self._cap.isOpened():
                self.online = False
                time.sleep(1.0)
                continue

            ret, raw = self._cap.read()
            if not ret:
                self.online = False
                time.sleep(0.5)
                continue

            self.online = True
            now = time.time()

            # FPS throttle — match OV5647's 5fps HTTP stream rate
            if now - last_frame_time < self.frame_interval:
                continue
            last_frame_time = now

            # FPS tracking
            self._ts_ring.append(now)
            if len(self._ts_ring) >= 2:
                span = self._ts_ring[-1] - self._ts_ring[0]
                if span > 0:
                    self._fps = (len(self._ts_ring) - 1) / span

            # Apply OV5647 degradation
            degraded = self.degrader.degrade_full(raw, night_mode=self.night_mode)

            # Update stream timing
            if self.streaming:
                elapsed = now - self.stream_start_time
                self.stream_remaining_sec = max(0, self.clip_duration_sec - elapsed)
                if elapsed >= self.clip_duration_sec:
                    self.streaming = False
                    print(f"[NODE-{self.node_id}] CLIP COMPLETE — {self.clip_duration_sec}s captured")

            with self._lock:
                self._raw_frame = raw
                self._degraded_frame = degraded

    def trigger_motion(self):
        """Simulate RADAR motion detection — start a 30s clip."""
        if self.streaming:
            print(f"[NODE-{self.node_id}] Already streaming — ignoring trigger")
            return

        self.streaming = True
        self.stream_start_time = time.time()
        self.stream_remaining_sec = self.clip_duration_sec
        print(f"[NODE-{self.node_id}] === MOTION DETECTED — STREAMING {self.clip_duration_sec}s CLIP ===")

    def toggle_night_mode(self):
        """Toggle between day and night/IR mode."""
        self.night_mode = not self.night_mode
        mode = "NIGHT (IR)" if self.night_mode else "DAY"
        print(f"[NODE-{self.node_id}] Mode: {mode}")

    def read(self) -> Optional[np.ndarray]:
        """Read the latest degraded frame. Returns None if offline."""
        with self._lock:
            if self._degraded_frame is not None:
                return self._degraded_frame.copy()
            return None

    def read_raw(self) -> Optional[np.ndarray]:
        """Read the latest raw (undegraded) frame."""
        with self._lock:
            if self._raw_frame is not None:
                return self._raw_frame.copy()
            return None

    @property
    def fps(self) -> float:
        return self._fps

    def stop(self):
        """Release resources."""
        self._stopped = True
        if self._cap:
            self._cap.release()
        self.online = False


class NodeManager:
    """
    Manages multiple simulated field nodes.
    Handles keyboard triggers, feed switching, and status reporting.
    """

    def __init__(self, webcam_sources: Optional[List[int]] = None, num_nodes: int = 3):
        """
        Args:
            webcam_sources: List of webcam indices. If fewer than num_nodes,
                           remaining nodes share the first webcam source.
            num_nodes: Number of simulated Hashtag nodes (default 3).
        """
        if webcam_sources is None:
            webcam_sources = [0]

        self.degrader = OV5647Degrader()
        self.nodes: List[SimulatedNode] = []

        for i in range(num_nodes):
            src = webcam_sources[i] if i < len(webcam_sources) else webcam_sources[0]
            node = SimulatedNode(
                node_id=i + 1,
                source=src,
                degrader=self.degrader,
                target_fps=5.0,
                clip_duration_sec=30.0,
            )
            self.nodes.append(node)

    def start_all(self):
        """Start all nodes."""
        for node in self.nodes:
            node.start()

    def stop_all(self):
        """Stop all nodes."""
        for node in self.nodes:
            node.stop()

    def trigger_all(self):
        """Trigger motion detection on all nodes."""
        for node in self.nodes:
            node.trigger_motion()

    def trigger_node(self, node_id: int):
        """Trigger motion detection on a specific node (1-indexed)."""
        if 0 < node_id <= len(self.nodes):
            self.nodes[node_id - 1].trigger_motion()

    def toggle_night_all(self):
        """Toggle night mode on all nodes."""
        for node in self.nodes:
            node.toggle_night_mode()

    def get_active_nodes(self) -> List[SimulatedNode]:
        """Returns list of currently online nodes."""
        return [n for n in self.nodes if n.online]

    def get_streaming_nodes(self) -> List[SimulatedNode]:
        """Returns list of nodes currently in an active clip session."""
        return [n for n in self.nodes if n.streaming and n.online]


# ============================================================
# Standalone test: Run the simulator directly to verify webcam
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  HASHTAG V2 — OV5647 FIELD NODE SIMULATOR")
    print("  SPACE = Trigger motion | N = Night mode | Q = Quit")
    print("=" * 60)

    manager = NodeManager(webcam_sources=[0], num_nodes=1)
    manager.start_all()

    # Auto-trigger for testing
    manager.trigger_all()

    while True:
        node = manager.nodes[0]
        frame = node.read()

        if frame is not None:
            # Draw status overlay
            status = "STREAMING" if node.streaming else "IDLE"
            mode = "IR/NIGHT" if node.night_mode else "DAY"
            remain = f"{node.stream_remaining_sec:.1f}s" if node.streaming else "--"

            cv2.putText(frame, f"NODE-{node.node_id} | {status} | {mode} | {remain} | {node.fps:.1f}fps",
                        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(frame, "OV5647 SIMULATED FEED", (10, frame.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 255), 1)

            cv2.imshow("OV5647 Simulator", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord(' '):
            manager.trigger_all()
        elif key == ord('n'):
            manager.toggle_night_all()

    manager.stop_all()
    cv2.destroyAllWindows()
