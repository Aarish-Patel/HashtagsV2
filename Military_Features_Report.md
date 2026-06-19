# Hashtags V2 - Military & Tactical Features Report

## Executive Summary
Hashtags V2 is engineered for austere, highly-distributed tactical environments. It addresses the core problem of operator fatigue ("staring at screens") by employing an edge-capable, dual-verification AI engine that only alerts operators when a verified threat is present.

## Key Tactical Advantages

### 1. Zero-Fatigue Monitoring (Standby Mode)
In traditional surveillance, operators must constantly scan a grid of monitors. Hashtags V2 operates in "Standby Mode," meaning the interface remains quiet and non-distracting. When a node detects movement, the system buffers the footage and evaluates it. The operator is only alerted *after* the ML model confirms a target. 

### 2. Dual-Pronged Verification (Low False Positives)
To prevent operators from suffering "alarm fatigue" due to false alarms (e.g., rustling leaves, wildlife), the backend uses a sophisticated Intersection Engine:
- **Prong A (Structural)**: Uses Canny Edge Detection and MOG2 to detect physical pixel disruptions in the environment.
- **Prong B (YOLOv8)**: Uses deep learning to classify if the disruption is a Human or Weapon.
An alarm is *only* escalated if Prong B finds a target *exactly where* Prong A detected physical movement. This virtually eliminates ghosting.

### 3. Asymmetric Bandwidth Handling (PIR Triggering)
In contested environments, maintaining 24/7 video streams across dozens of nodes is impossible. Hashtags V2 supports **PIR Triggering**. Nodes remain completely offline (saving battery and RF emissions). When physical movement triggers the PIR sensor, the node instantly wakes up, blasts a 30-second video clip over the network, and the backend captures it.

### 4. Forensic Intelligence Generation
Every threat generates an immutable forensic artifact. The system doesn't just save a video clip; it saves a `_report.json` containing:
- The exact bounding boxes of the enemy.
- Confidence scores.
- Millisecond-accurate timestamps of when the weapon/person entered the frame.
- The GPS coordinates of the node that detected them.

### 5. Multi-Theater Heatmap
The Tactical Map includes a 30-day Threat Heatmap. It visually overlays the frequency of incursions on specific nodes, allowing commanders to objectively identify the most active infiltration routes and dynamically re-allocate patrols to the hottest zones.
