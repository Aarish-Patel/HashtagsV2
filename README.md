# Hashtags V2

Hashtags V2 is a cutting-edge, ML-powered, multi-node tactical surveillance system built for robust edge deployments. 

## Core Capabilities
- **Multi-Node Feed Aggregation:** Monitor live streams from distributed surveillance nodes simultaneously.
- **AI-Powered Threat Detection:** Employs a dual-prong analysis engine (YOLOv8 + Structural Discrepancy/Canny Edge) for high-accuracy, low-latency threat classification.
- **Instant Alerts & Polling:** Frontend automatically polls the backend to immediately alert operators upon detecting threats or structural changes.
- **Forensic Video Storage:** Automatically records, annotates, and catalogs video clips (incidents) triggered by threats.
- **Heatmap Analytics:** Provides a 30-day spatial distribution of active threats across your nodes for tactical review.

## System Components
### Backend (`src/`)
- Built on **Flask** with a sophisticated multi-threaded camera ingestion and ML analysis loop.
- **Engine**: Uses YOLO and traditional computer vision (OpenCV) to distinguish valid threats from benign movement.

### Frontend (`frontend/`)
- Built on **React + Vite + TailwindCSS**.
- Provides a comprehensive Dashboard containing Tactical Maps, Live Feeds, Storage Views, Alert Histories, and Admin Configuration Panels.

## Documentation
For detailed operational procedures, please refer to:
- [User Guide](User_Guide.md) - For surveillance operators monitoring live feeds and alerts.
- [Admin Guide](Admin_Guide.md) - For system administrators adding nodes and tuning detection thresholds.
- [Military Features Report](Military_Features_Report.md) - Analysis of the tactical and strategic benefits of this system for military deployments.
