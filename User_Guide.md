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


