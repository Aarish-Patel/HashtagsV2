# Hashtag V2 — Border Surveillance System

Hashtag V2 is a tactical border surveillance system that aggregates video feeds from multiple nodes (IP cameras, ESP32-CAMs, Raspberry Pis) and runs AI-based object detection (YOLOv8) and thermal motion analysis to detect unauthorized intrusions or weapons in real-time. 

It provides a modern React frontend dashboard with a tactical map and live video analytics.

## Prerequisites & Downloads

To run this system, you must install the following software. Please ensure you check the box that says **"Add to PATH"** during installation for each of these!

1. **Python 3.10 or higher**
   - Download: [python.org/downloads](https://www.python.org/downloads/)
   - *Crucial: Check "Add Python to PATH" at the bottom of the installer!*

2. **Node.js 18 or higher**
   - Download: [nodejs.org](https://nodejs.org/en/download/)
   - *Installs `npm` which is required for the React dashboard.*

3. **GStreamer 1.0+ (MSVC 64-bit)** *(Optional but recommended)*
   - Download: [gstreamer.freedesktop.org](https://gstreamer.freedesktop.org/download/)
   - Required ONLY if you are using TCP raw GStreamer pipelines (like `rawgst:...` in your `nodes.json`).
   - You must add the `\bin` folder of GStreamer to your Windows environment PATH variables so the `gst-launch-1.0` command works.

## Quick Start (Instantly Run)

Simply double-click the **`start_hashtag.bat`** file on Windows.

The startup script will automatically:
1. Create an isolated Python virtual environment.
2. Install all required AI and backend dependencies.
3. Install all React frontend dependencies.
4. Launch the AI processing server on port 5000.
5. Launch the React dashboard on port 5173.
6. Open your browser automatically to the Tactical Dashboard.

*Note: The first launch will take a few minutes as it downloads PyTorch, OpenCV, and Node packages. Subsequent launches will be near-instant.*

## Adding New Camera Nodes

To add new IP cameras or streaming nodes to the network:
1. Open `src/nodes.json` in a text editor.
2. Add a new node object with an ID, name, stream URL, and coordinates.

Example for an ESP32-CAM:
```json
{
  "id": "HASH-4",
  "name": "Field Node 4",
  "stream_url": "http://192.168.0.201:81/stream",
  "lat": 24.172,
  "lng": 94.258
}
```
3. Restart the system using `start_hashtag.bat`.

## System Architecture

- **Frontend**: React + Vite + Leaflet (Offline Maps)
- **Backend**: Python + Flask
- **AI Core**: YOLOv8 Object Detection + OpenCV Background Subtraction & Edge Detection
- **Streaming**: Multi-threaded buffered MJPEG processing pipeline
