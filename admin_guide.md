# Hashtags V2 - Admin Guide

## Overview
The Admin Dashboard allows you to manage node infrastructure, tune the dual-prong detection engine, and monitor system telemetry. Access this panel via the Gear icon in the sidebar (requires `COMMANDER` role privileges).

## Node Management
### Adding a Node
1. Click **+ ADD** in the Field Nodes panel.
2. Provide a unique **Node ID** (e.g. `HASH-6`).
3. Provide the **Stream URL** (e.g. `http://192.168.1.100/stream`).
4. (Optional) Provide GPS coordinates (Lat/Lng) to place the node accurately on the Tactical Map.
5. Select the **Trigger Type**:
   - `PIR`: Relies on an external motion sensor to trigger the camera stream and analysis.
   - `DETECTION`: The stream is always on, and the AI continuously looks for threats.

### Deleting a Node
Hover over the node card, click the Trash icon, and confirm. This will archive the node's clips but immediately stop all processing and remove it from the active map.

## Sensitivity Tuning (Dual-Prong Engine Parameters)
The system validates threats using two prongs: Prong A (Structural/Physical Movement) and Prong B (YOLO AI Classification). The intersection of these two prongs prevents false alarms. You can tune these parameters on a per-node basis using the sliders in the Admin panel.

### 1. Edge Threshold (Prong A)
- **Meaning**: Controls the sensitivity of the Canny Edge Detection algorithm. It determines how stark a contrast must be for the system to consider it an "edge" of a physical object.
- **How to Use**: 
  - **Decrease** this if the camera is in low contrast/fog/darkness and is missing moving objects.
  - **Increase** this if the camera is picking up too much noise, shadows, or minor lighting changes.

### 2. Min Blob Area (Prong A)
- **Meaning**: The minimum pixel size of a moving object required to trigger Prong A.
- **How to Use**:
  - **Decrease** if you need to detect very distant, small targets (e.g., people far away).
  - **Increase** if the camera is falsely triggering on small moving objects like insects, small birds, or rustling leaves near the lens.

### 3. Confidence (Prong B)
- **Meaning**: The YOLOv8 AI confidence threshold (0.0 to 1.0). The neural network must be this confident that what it sees is a human or weapon.
- **How to Use**:
  - **Decrease** (e.g., 0.25) if the AI is failing to detect camouflaged or partially obscured targets.
  - **Increase** (e.g., 0.60) if the AI is hallucinating threats (e.g., mistaking a tree trunk for a person).

### 4. Min IoU (Intersection over Union)
- **Meaning**: This measures how tightly the bounding box of the physical movement (Prong A) must overlap with the bounding box of the AI classification (Prong B). 
- **How to Use**:
  - **Increase** (e.g., 0.5) for extremely strict verification. The AI target and the physical movement must overlap almost perfectly. Use this in highly dynamic environments (trees blowing in the wind) to completely eliminate ghosting.
  - **Decrease** (e.g., 0.0) to completely disable the spatial intersection check. This means if *any* movement happens anywhere in the frame, and a person is detected *anywhere* in the frame, an alarm triggers. Use this in static, sterile environments (like an empty hallway) where any movement is a threat.

## Background Operations
- **Capture Background**: For nodes with heavy static backgrounds, use this button to capture a baseline frame.
- **Revert to MOG2**: If the background changes frequently, revert to dynamic MOG2 background subtraction.

*Note: Always remember to click **SAVE TUNING TO DISK** after making changes.*
