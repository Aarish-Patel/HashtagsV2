import numpy as np
import time
from collections import deque
from typing import List, Tuple, Dict, Any, Optional

class GaitAnalyzer:
    """
    Biomechanical Gait Analysis Module.
    
    Instead of relying purely on visual appearance (which can be defeated by camouflage),
    this module analyzes the time-series kinematics of a tracked object.
    
    Human locomotion (walking, running, crawling) produces highly specific 
    rhythmic oscillations (gait). By applying a Fast Fourier Transform (FFT) 
    to the vertical and horizontal velocity of a moving blob, we can detect 
    the biomechanical "heartbeat" of human movement even if it looks like a bush.
    """
    
    def __init__(self, window_size: int = 30, fps: float = 5.0):
        self.window_size = window_size
        self.fps = max(fps, 1.0)
        
        # Human walking step frequency is typically 1.4 - 2.5 Hz
        # Running is 2.5 - 4.0 Hz
        # Crawling is 0.5 - 1.5 Hz
        self.human_freq_bands = {
            "CRAWLING_GAIT": (0.3, 1.3),
            "WALKING_GAIT": (1.4, 2.5),
            "RUNNING_GAIT": (2.6, 4.5)
        }
        
    def analyze_kinematics(self, history: deque, velocities: deque) -> Dict[str, Any]:
        """
        Analyzes the trajectory and velocity history of an entity using FFT.
        Requires a history of at least `window_size // 2` frames to be statistically significant.
        """
        if len(history) < 15 or len(velocities) < 15:
            return {"is_human_gait": False, "gait_type": "UNKNOWN", "confidence": 0.0, "freq": 0.0}
            
        # Extract Y-axis velocities (vertical bobbing is the strongest indicator of bipedal gait)
        # Extract X-axis velocities (forward progression)
        vy_signal = np.array([v[1] for v in velocities])
        vx_signal = np.array([v[0] for v in velocities])
        
        # Normalize the signals to zero mean
        vy_norm = vy_signal - np.mean(vy_signal)
        vx_norm = vx_signal - np.mean(vx_signal)
        
        # Apply Hanning window to reduce spectral leakage
        window = np.hanning(len(vy_norm))
        vy_windowed = vy_norm * window
        
        # Perform Fast Fourier Transform (FFT)
        fft_result = np.fft.rfft(vy_windowed)
        magnitudes = np.abs(fft_result)
        
        # Get corresponding frequencies in Hz
        freqs = np.fft.rfftfreq(len(vy_windowed), d=1.0/self.fps)
        
        # Ignore the DC component (0 Hz) and find the dominant frequency
        if len(magnitudes) > 1:
            magnitudes[0] = 0 
            peak_idx = np.argmax(magnitudes)
            dominant_freq = freqs[peak_idx]
            peak_magnitude = magnitudes[peak_idx]
            
            # Calculate Signal-to-Noise Ratio (SNR) of the gait frequency
            avg_magnitude = np.mean(magnitudes)
            snr = peak_magnitude / (avg_magnitude + 1e-6)
            
            # If the oscillation is strong (SNR > 3.0), classify the gait
            if snr > 3.0:
                for gait_name, (min_f, max_f) in self.human_freq_bands.items():
                    if min_f <= dominant_freq <= max_f:
                        # We found a human biomechanical rhythm!
                        confidence = min(1.0, snr / 10.0)
                        return {
                            "is_human_gait": True,
                            "gait_type": gait_name,
                            "confidence": round(float(confidence), 2),
                            "freq": round(float(dominant_freq), 2)
                        }
                        
        return {"is_human_gait": False, "gait_type": "NONE", "confidence": 0.0, "freq": 0.0}

    def analyze_pose_rhythm(self, posture_history: deque) -> bool:
        """
        Analyzes the sequence of discrete posture states over time.
        If someone rapidly oscillates between CROUCHING and STANDING, 
        or CRAWLING and PRONE, it indicates tactical movement (bounding overwatch).
        """
        if len(posture_history) < 10:
            return False
            
        transitions = 0
        prev = posture_history[0]
        for posture in list(posture_history)[1:]:
            if posture != prev and posture != 0: # 0 is UNKNOWN
                transitions += 1
            prev = posture
            
        # If they change posture more than 3 times in 10 frames, it's highly tactical/evasive
        return transitions >= 3
