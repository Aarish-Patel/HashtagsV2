# Hashtags V2 - User Guide

## Overview
Hashtags V2 is your primary interface for monitoring distributed edge surveillance nodes. The system continuously analyzes live feeds for threats using advanced ML and structural disruption algorithms, only alerting you when actionable intelligence is found.

## Dashboard Interface
The user interface is broken into several key tabs on the left sidebar:

### 1. Tactical Map
- **Purpose**: Provides a bird's-eye view of all nodes on a geographical map.
- **Features**:
  - Green nodes represent active nodes in standby.
  - Pulsing red nodes indicate an active, unacknowledged threat.
  - Clicking on a red node brings up the live replay loop of the threat.
  - **Heatmap**: You can toggle the "SHOW HEATMAP" button to view a 30-day geographical distribution of where threats happen most often.

### 2. Live Feeds
- **Purpose**: A grid wall displaying the live, unannotated video feed of all nodes.
- **Features**:
  - Ideal for secondary monitors.
  - The border of a feed turns red when an active alarm is triggered.

### 3. Entity Tracker
- **Purpose**: A breakdown of the raw intelligence currently being processed.
- **Features**:
  - Displays bounding boxes, confidence scores, and bounding box coordinates for identified objects (e.g., Person, Weapon).

### 4. Alert History & Storage View
- **Purpose**: Forensic replay and archival access.
- **Features**:
  - The **Alert History** on the left panel provides a quick list of recent incidents.
  - The **Storage View** provides a theater-mode experience to play back the exact 30-second clips saved when an alarm was triggered.
  - You can view the attached raw JSON intelligence report for each clip.

## Handling Alerts
When an alarm triggers:
1. An audible buzzer will sound and the UI will flash red.
2. The exact clip of what triggered the alarm will loop on your screen.
3. Once you evaluate the threat, press **ACKNOWLEDGE** to silence the alarm and return to standby mode.
4. If you determine the alarm was a false alarm, you can click **FALSE POSITIVE**. This logs the discrepancy so the Admin can tune the sensitivity later.



## Adding Nodes
To add a new surveillance node, hover over the left sidebar to expand it and click the **+ (Plus)** icon in the Node Manager section. You can enter various types of streams into the **Stream IP** field:

1. **Standard IP Camera (HTTP MJPEG/Web Stream)**
   - Simply enter the IP address (e.g., `192.168.1.50`). The system will automatically prepend `http://` and append `/stream`.
   - Or, you can explicitly type the full URL: `http://192.168.1.50/video`.

2. **Raspberry Pi (GStreamer TCP Stream)**
   - If your Raspberry Pi is streaming via a raw TCP h264 payload, you can use a raw GStreamer pipeline string.
   - For example, if your RPi is at `192.168.0.7`, paste the following exact string into the Stream IP field:
     `tcpclientsrc host=192.168.0.7 port=5000 ! gdpdepay ! rtph264depay ! avdec_h264 ! videoconvert ! appsink drop=1`
   - *(Note: Do not use `autovideosink` in the system input. The local testing command `gst-launch-1.0.exe ... autovideosink` is only for viewing the stream directly on your monitor outside of Hashtags).*

3. **RTSP Streams**
   - You can enter full RTSP URLs if your camera supports it: `rtsp://admin:password@192.168.1.64:554/stream1`.

Make sure to select the correct **TRIGGER** type (`PIR` for hardware-triggered setups, or `DETECTION` for software motion/ML triggers) when adding the node.
