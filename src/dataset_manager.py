"""
dataset_manager.py — Dataset Preparation Pipeline for OV5647 Training

Prepares training data by:
1. Converting various dataset formats to YOLO format
2. Applying OV5647 camera degradation to all training images
3. Creating stratified train/val/test splits
4. Generating the dataset YAML configuration

This is the KEY difference from HashtagV1: instead of training on clean
images and hoping inference works on degraded feeds, we DEGRADE the training
data to match OV5647 output quality BEFORE training.

Supported input datasets:
- COCO (JSON annotations)
- VisDrone (text annotations)
- TinyPerson (COCO-format JSON)
- LLVIP (already available from V1)
- Any dataset in YOLO format (images/ + labels/ folders)

Usage:
    python dataset_manager.py --source /path/to/dataset --format coco --output /path/to/output
"""

import cv2
import numpy as np
import os
import json
import shutil
import random
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from augmentation_pipeline import OV5647Degrader, TrainingAugmentor


class DatasetConverter:
    """Converts various annotation formats to YOLO format."""

    @staticmethod
    def coco_to_yolo(coco_json_path: str, images_dir: str, output_dir: str,
                      target_classes: Optional[List[str]] = None):
        """
        Convert COCO format JSON annotations to YOLO format.
        Only extracts specified classes (default: person only).
        """
        if target_classes is None:
            target_classes = ["person"]

        with open(coco_json_path, 'r') as f:
            coco = json.load(f)

        # Build category mapping
        cat_map = {}
        for cat in coco.get("categories", []):
            if cat["name"].lower() in [c.lower() for c in target_classes]:
                cat_map[cat["id"]] = 0  # Map all target classes to class 0

        if not cat_map:
            print(f"[!] No target classes found in {coco_json_path}")
            return 0

        # Build image ID → filename mapping
        img_map = {img["id"]: img for img in coco.get("images", [])}

        # Create output directories
        img_out = os.path.join(output_dir, "images")
        lbl_out = os.path.join(output_dir, "labels")
        os.makedirs(img_out, exist_ok=True)
        os.makedirs(lbl_out, exist_ok=True)

        # Group annotations by image
        ann_by_img: Dict[int, List] = {}
        for ann in coco.get("annotations", []):
            if ann["category_id"] in cat_map:
                img_id = ann["image_id"]
                if img_id not in ann_by_img:
                    ann_by_img[img_id] = []
                ann_by_img[img_id].append(ann)

        count = 0
        for img_id, anns in ann_by_img.items():
            if img_id not in img_map:
                continue

            img_info = img_map[img_id]
            img_w = img_info["width"]
            img_h = img_info["height"]
            img_filename = img_info["file_name"]

            # Copy image
            src_path = os.path.join(images_dir, img_filename)
            if not os.path.exists(src_path):
                # Try without subdirectory
                src_path = os.path.join(images_dir, os.path.basename(img_filename))
            if not os.path.exists(src_path):
                continue

            dst_img = os.path.join(img_out, os.path.basename(img_filename))
            if not os.path.exists(dst_img):
                shutil.copy2(src_path, dst_img)

            # Write YOLO labels
            label_filename = os.path.splitext(os.path.basename(img_filename))[0] + ".txt"
            label_path = os.path.join(lbl_out, label_filename)

            with open(label_path, 'w') as f:
                for ann in anns:
                    bbox = ann["bbox"]  # [x, y, width, height] in COCO format
                    if bbox[2] < 1 or bbox[3] < 1:
                        continue

                    # Convert to YOLO format: center_x, center_y, width, height (normalized)
                    cx = (bbox[0] + bbox[2] / 2) / img_w
                    cy = (bbox[1] + bbox[3] / 2) / img_h
                    w = bbox[2] / img_w
                    h = bbox[3] / img_h

                    # Clamp to [0, 1]
                    cx = max(0, min(1, cx))
                    cy = max(0, min(1, cy))
                    w = max(0, min(1, w))
                    h = max(0, min(1, h))

                    cls_id = cat_map[ann["category_id"]]
                    f.write(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

            count += 1

        print(f"  Converted {count} images from COCO format")
        return count

    @staticmethod
    def visdrone_to_yolo(visdrone_ann_dir: str, images_dir: str, output_dir: str):
        """
        Convert VisDrone format to YOLO format.
        VisDrone format: <bbox_left>,<bbox_top>,<bbox_width>,<bbox_height>,
                         <score>,<object_category>,<truncation>,<occlusion>
        Category 1 = pedestrian, 2 = person (we want both)
        """
        img_out = os.path.join(output_dir, "images")
        lbl_out = os.path.join(output_dir, "labels")
        os.makedirs(img_out, exist_ok=True)
        os.makedirs(lbl_out, exist_ok=True)

        count = 0
        for ann_file in os.listdir(visdrone_ann_dir):
            if not ann_file.endswith('.txt'):
                continue

            base_name = os.path.splitext(ann_file)[0]
            img_path = None
            for ext in ['.jpg', '.png', '.jpeg']:
                candidate = os.path.join(images_dir, base_name + ext)
                if os.path.exists(candidate):
                    img_path = candidate
                    break

            if img_path is None:
                continue

            img = cv2.imread(img_path)
            if img is None:
                continue
            img_h, img_w = img.shape[:2]

            # Copy image
            dst_img = os.path.join(img_out, os.path.basename(img_path))
            if not os.path.exists(dst_img):
                shutil.copy2(img_path, dst_img)

            # Parse VisDrone annotations
            yolo_lines = []
            with open(os.path.join(visdrone_ann_dir, ann_file), 'r') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) < 8:
                        continue

                    x, y, w, h = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                    category = int(parts[5])

                    # Category 1=pedestrian, 2=person
                    if category not in (1, 2):
                        continue
                    if w < 1 or h < 1:
                        continue

                    cx = (x + w / 2) / img_w
                    cy = (y + h / 2) / img_h
                    nw = w / img_w
                    nh = h / img_h

                    yolo_lines.append(f"0 {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

            if yolo_lines:
                label_path = os.path.join(lbl_out, base_name + ".txt")
                with open(label_path, 'w') as f:
                    f.write('\n'.join(yolo_lines) + '\n')
                count += 1

        print(f"  Converted {count} images from VisDrone format")
        return count


class DatasetPreparator:
    """
    Prepares the final training dataset by applying OV5647 degradation
    to all images and organizing into train/val/test splits.
    """

    def __init__(self, output_base: str):
        self.output_base = output_base
        self.degrader = OV5647Degrader()
        self.augmentor = TrainingAugmentor(self.degrader)

    def degrade_dataset(self, source_dir: str, output_dir: str, num_augmented: int = 2):
        """
        Apply OV5647 degradation to all images in a YOLO-format dataset.
        Creates 'num_augmented' degraded copies of each image with random
        variation in degradation parameters.
        """
        dst_images = os.path.join(output_dir, "images")
        dst_labels = os.path.join(output_dir, "labels")
        os.makedirs(dst_images, exist_ok=True)
        os.makedirs(dst_labels, exist_ok=True)

        # Recursively find all images inside any "images" folder
        image_paths = []
        for root, dirs, files in os.walk(source_dir):
            if "images" in root.split(os.sep):
                for f in files:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        image_paths.append(os.path.join(root, f))

        print(f"  Degrading {len(image_paths)} images × {num_augmented} augmentations...")
        count = 0

        for img_path in image_paths:
            # YOLO convention: label path has 'labels' instead of 'images' and '.txt' extension
            label_path = img_path.replace(os.sep + "images" + os.sep, os.sep + "labels" + os.sep)
            # Handle edge case where it might be forward slashes on Windows paths sometimes
            label_path = label_path.replace("/images/", "/labels/")
            
            base_name = os.path.splitext(os.path.basename(img_path))[0]
            label_path = os.path.splitext(label_path)[0] + ".txt"

            if not os.path.exists(label_path):
                continue

            frame = cv2.imread(img_path)
            if frame is None:
                continue

            for aug_idx in range(num_augmented):
                # Apply random OV5647 degradation
                degraded = self.augmentor.random_ov5647_degrade(frame)

                # Save degraded image
                aug_name = f"{base_name}_ov{aug_idx}"
                cv2.imwrite(os.path.join(dst_images, f"{aug_name}.jpg"), degraded)

                # Copy label (annotations are scale-invariant in YOLO format)
                shutil.copy2(label_path, os.path.join(dst_labels, f"{aug_name}.txt"))
                count += 1

            if count % 500 == 0 and count > 0:
                print(f"    Processed {count} images...")

        print(f"  Total degraded images: {count}")
        return count

    def create_splits(self, dataset_dir: str, train_ratio: float = 0.8,
                       val_ratio: float = 0.15, test_ratio: float = 0.05):
        """
        Split a YOLO-format dataset into train/val/test sets.
        """
        images_dir = os.path.join(dataset_dir, "images")
        labels_dir = os.path.join(dataset_dir, "labels")

        all_images = [f for f in os.listdir(images_dir)
                      if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        random.shuffle(all_images)

        n_total = len(all_images)
        n_train = int(n_total * train_ratio)
        n_val = int(n_total * val_ratio)

        splits = {
            "train": all_images[:n_train],
            "val": all_images[n_train:n_train + n_val],
            "test": all_images[n_train + n_val:],
        }

        for split_name, split_files in splits.items():
            split_img_dir = os.path.join(dataset_dir, split_name, "images")
            split_lbl_dir = os.path.join(dataset_dir, split_name, "labels")
            os.makedirs(split_img_dir, exist_ok=True)
            os.makedirs(split_lbl_dir, exist_ok=True)

            for img_file in split_files:
                base = os.path.splitext(img_file)[0]
                shutil.move(os.path.join(images_dir, img_file),
                            os.path.join(split_img_dir, img_file))

                lbl_file = base + ".txt"
                lbl_src = os.path.join(labels_dir, lbl_file)
                if os.path.exists(lbl_src):
                    shutil.move(lbl_src, os.path.join(split_lbl_dir, lbl_file))

            print(f"  {split_name}: {len(split_files)} images")

        # Clean up now-empty directories
        if os.path.exists(images_dir) and not os.listdir(images_dir):
            os.rmdir(images_dir)
        if os.path.exists(labels_dir) and not os.listdir(labels_dir):
            os.rmdir(labels_dir)

    def generate_yaml(self, dataset_dir: str, output_path: str,
                       dataset_name: str = "hashtag_v2_person"):
        """Generate YOLO dataset YAML configuration file."""
        config = {
            "path": os.path.abspath(dataset_dir),
            "train": "train/images",
            "val": "val/images",
            "test": "test/images",
            "nc": 1,
            "names": ["person"],
        }

        import yaml
        with open(output_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

        print(f"  Dataset YAML saved: {output_path}")
        return output_path


def main():
    """
    Example usage: Prepare a COCO-format dataset for OV5647 training.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Prepare datasets for HashtagV2 training")
    parser.add_argument("--source", required=True, help="Source dataset directory")
    parser.add_argument("--format", choices=["coco", "visdrone", "yolo"], default="yolo",
                        help="Source annotation format")
    parser.add_argument("--coco-json", help="Path to COCO annotations JSON (for coco format)")
    parser.add_argument("--output", required=True, help="Output directory for prepared dataset")
    parser.add_argument("--augmentations", type=int, default=2,
                        help="Number of OV5647-degraded copies per image")
    parser.add_argument("--skip-degrade", action="store_true",
                        help="Skip OV5647 degradation (use original images)")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # Step 1: Convert to YOLO format if needed
    converted_dir = os.path.join(args.output, "converted")

    if args.format == "coco":
        if not args.coco_json:
            print("[!] --coco-json required for COCO format")
            return
        print("[1/4] Converting COCO to YOLO format...")
        DatasetConverter.coco_to_yolo(
            args.coco_json,
            os.path.join(args.source, "images") if os.path.exists(os.path.join(args.source, "images")) else args.source,
            converted_dir
        )
    elif args.format == "visdrone":
        print("[1/4] Converting VisDrone to YOLO format...")
        DatasetConverter.visdrone_to_yolo(
            os.path.join(args.source, "annotations"),
            os.path.join(args.source, "images"),
            converted_dir
        )
    else:
        converted_dir = args.source
        print("[1/4] Dataset already in YOLO format, skipping conversion")

    # Step 2: Apply OV5647 degradation
    preparator = DatasetPreparator(args.output)

    if not args.skip_degrade:
        print("[2/4] Applying OV5647 camera degradation...")
        degraded_dir = os.path.join(args.output, "degraded")
        preparator.degrade_dataset(converted_dir, degraded_dir, num_augmented=args.augmentations)
        final_dir = degraded_dir
    else:
        final_dir = converted_dir
        print("[2/4] Skipping degradation (using original images)")

    # Step 3: Create train/val/test splits
    print("[3/4] Creating train/val/test splits...")
    preparator.create_splits(final_dir)

    # Step 4: Generate YAML config
    print("[4/4] Generating dataset YAML...")
    yaml_path = os.path.join(args.output, "dataset.yaml")
    preparator.generate_yaml(final_dir, yaml_path)

    print(f"\n[+] Dataset preparation complete!")
    print(f"    Output: {args.output}")
    print(f"    Config: {yaml_path}")
    print(f"\n    To train: python train_pipeline.py --data {yaml_path}")


if __name__ == "__main__":
    main()
