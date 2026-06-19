# Hashtag V2 Admin Guide

Welcome to the Hashtag V2 Admin Dashboard. This guide explains the core configuration parameters available in the dashboard and how they affect the detection pipeline.

## 1. Detection Modes

The Hashtag system uses a hybrid detection engine combining two distinct 'prongs' to achieve high accuracy and eliminate false positives.
- **Prong A (Structural Discrepancy Filter)**: Analyzes low-level pixel differences and structural changes between the live camera feed and a pre-captured 'permanent background' image.
- **Prong B (AI Object Detection)**: Uses YOLO (You Only Look Once) to identify the semantic classes of objects within those changed areas.

### How they work together:
The system defaults to a **Combined Mode** where an alarm is *only* triggered if **Prong A** detects a physical change in the environment AND **Prong B** confirms that the object causing the change is a person or weapon, AND they physically overlap (Intersection Gate). If a camera has no saved background, it falls back to standard MOG2 motion detection.

## 2. Tuning Parameters (Node Config)

The Admin panel allows you to fine-tune the sensitivity of these detection prongs for each camera independently.

### Prong B — YOLO
- **Confidence (`person_conf`)**: The minimum confidence score required for the AI to confirm an object is a person. Ranges from 0.0 to 1.0. Increase this to reduce AI false positives.
- **YOLO Weight (`prong_b_weight`)**: How much the AI's confidence contributes to the final calculated Threat Score. Higher means you trust the AI more than the physical motion.

### Prong A — Structural
- **Edge Threshold (`prong_a_threshold`)**: The intensity difference required for a pixel to be considered "changed" when comparing edges. Increase this if noisy lighting triggers motion.
- **Prong A Weight (`prong_a_weight`)**: How much the structural/motion severity contributes to the final calculated Threat Score. Higher means you trust physical disruption more than the AI.
- **Min Blob (px²) (`min_contour_area`)**: The minimum size a changed area must be before the system pays attention to it. Increase to ignore bugs or small animals. Decrease to detect distant intruders.

### Intersection Gate
These parameters ensure that the AI detection bounding box physically overlaps with the physical motion blob. This prevents the AI from falsely identifying a static object (like a statue) when a bird flies by.
- **Min IoU (`intersection_iou`)**: Minimum Intersection over Union. Checks how much the motion blob and AI box overlap relative to their combined size.
- **Min Containment (`intersection_containment`)**: Minimum containment. Checks how much of the motion blob is entirely contained within the AI bounding box.

### Canny Edge Detection
- **Canny Low (`canny_low`)**: Determines how weak edges can be connected to strong edges in the background capturing process.
- **Canny High (`canny_high`)**: Determines the initial threshold for strong edges in the background capturing process.

### Display Mode (Diagnostic)
These modes only affect the visual overlay on the camera feed to help you tune the system, they do not affect the detection logic:
- **COMBINED**: Standard view showing both motion contours and AI bounding boxes.
- **PRONG_A**: Shows only the physical motion blobs/contours.
- **PRONG_B**: Shows only the AI bounding boxes.
- **RAW**: Shows the raw camera feed with no overlays.

## 3. Threat States & Actions

- **Trigger Type**: The condition required to set off the main siren. 
  - `PIR` mode is used for battery-powered cameras that only wake up and send a video stream when their built-in motion sensor triggers. It instantly alarms when a stream connects.
  - `DETECTION` mode is used for continuous video feeds. It only alarms when a verified threat is actively detected in the frame.
- **Acknowledge**: Stops the siren and clears the flashing alert from the UI for a specific threat.
- **Report False Positive**: Marks a detection as incorrect. The system will automatically tune its parameters (such as `person_conf` or `min_contour_area`) to ignore similar false positives in the future, and will recapture a new clean background automatically.
- **Set Permanent Background**: Captures the current camera view and uses it as the baseline for Prong A. Ensure no people are in the frame when you click this.
- **Clear Background**: Reverts the node to standard MOG2 motion detection.
- **Clear All Clips**: Permanently deletes all forensic video recordings from the disk.
