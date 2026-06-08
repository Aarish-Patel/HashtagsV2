"""
train_pipeline.py — YOLOv8 Training Pipeline for OV5647-Degraded Data

Trains a YOLOv8s model on OV5647-degraded imagery for maximum person
detection accuracy on real field camera output.

Designed for NVIDIA 4060 GPU. Training takes several hours depending
on dataset size.

Usage:
    python train_pipeline.py --data path/to/dataset.yaml
    python train_pipeline.py --data path/to/dataset.yaml --epochs 50 --batch 16
"""

import os
import sys
import argparse
import torch
from ultralytics import YOLO


def train_person_detector(data_yaml: str, epochs: int = 30, batch: int = 16,
                           imgsz: int = 640, model_base: str = "yolov8s.pt",
                           project: str = "runs/hashtag_v2", name: str = "person_detect"):
    """
    Train YOLOv8s person detector on OV5647-degraded imagery.

    Uses YOLOv8s (small) as base — provides good balance between
    accuracy and inference speed for 800x640 degraded imagery.
    """
    print("=" * 60)
    print("  HASHTAG V2 — PERSON DETECTION TRAINING")
    print("=" * 60)
    print(f"  CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  GPU:  {torch.cuda.get_device_name(0)}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    print(f"  Base: {model_base}")
    print(f"  Data: {data_yaml}")
    print(f"  Epochs: {epochs}")
    print(f"  Batch:  {batch}")
    print(f"  ImgSz:  {imgsz}")
    print("=" * 60)

    device = '0' if torch.cuda.is_available() else 'cpu'

    model = YOLO(model_base)

    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        amp=True,               # Mixed precision for 4060
        cache=False,             # Don't cache to RAM (large datasets)
        project=project,
        name=name,
        exist_ok=True,
        workers=4,
        optimizer='auto',
        patience=10,             # Early stopping after 10 epochs without improvement
        save=True,
        save_period=5,           # Checkpoint every 5 epochs
        plots=True,              # Generate training plots

        # Augmentation — minimal since we pre-degraded the dataset
        # But we add some geometric augmentation for robustness
        hsv_h=0.01,             # Minimal hue shift (pre-degraded handles color)
        hsv_s=0.3,              # Some saturation variation
        hsv_v=0.3,              # Some value/brightness variation
        degrees=5.0,            # Small rotation (camera tilt)
        translate=0.1,          # Small translation
        scale=0.3,              # Scale variation (distance simulation)
        shear=2.0,              # Small shear
        perspective=0.0005,     # Slight perspective change
        flipud=0.01,            # Rare vertical flip (crawling)
        fliplr=0.5,             # Horizontal flip (direction invariance)
        mosaic=0.8,             # Mosaic augmentation (mix training samples)
        mixup=0.1,              # MixUp augmentation
        copy_paste=0.1,         # Copy-paste augmentation
    )

    # Export best model
    best_path = os.path.join(project, name, "weights", "best.pt")
    print(f"\n[+] Training complete!")
    print(f"    Best model: {best_path}")
    print(f"    Copy to src/models/ for deployment")

    return best_path


def train_pose_model(data_yaml: str, epochs: int = 20, batch: int = 12,
                      model_base: str = "yolov8s-pose.pt",
                      project: str = "runs/hashtag_v2", name: str = "pose_detect"):
    """
    Fine-tune YOLOv8s-pose on OV5647-degraded imagery.
    Requires COCO-format keypoint annotations.
    """
    print("\n[*] Fine-tuning Pose Model...")
    device = '0' if torch.cuda.is_available() else 'cpu'

    model = YOLO(model_base)
    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=640,
        batch=batch,
        device=device,
        amp=True,
        project=project,
        name=name,
        exist_ok=True,
        workers=4,
    )

    best_path = os.path.join(project, name, "weights", "best.pt")
    print(f"  Pose model: {best_path}")
    return best_path


def main():
    parser = argparse.ArgumentParser(description="HashtagV2 Training Pipeline")
    parser.add_argument("--data", required=True, help="Path to dataset YAML")
    parser.add_argument("--epochs", type=int, default=30, help="Training epochs")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=640, help="Training image size")
    parser.add_argument('--model', type=str, default='yolov8x.pt', help='Base model to fine-tune')
    parser.add_argument("--project", default="runs/hashtag_v2", help="Output project dir")
    parser.add_argument("--name", default="person_detect", help="Run name")
    parser.add_argument("--task", choices=["detect", "pose", "all"], default="detect",
                        help="What to train")
    args = parser.parse_args()

    if args.task in ("detect", "all"):
        train_person_detector(
            data_yaml=args.data,
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            model_base=args.model,
            project=args.project,
            name=args.name,
        )

    if args.task in ("pose", "all"):
        train_pose_model(
            data_yaml=args.data,
            epochs=max(args.epochs // 2, 10),
            batch=max(args.batch - 4, 8),
            project=args.project,
        )


if __name__ == "__main__":
    main()
