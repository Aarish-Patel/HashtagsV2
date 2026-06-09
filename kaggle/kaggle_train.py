import os
import shutil
from ultralytics import YOLO
import ultralytics.data.augment

# --- OV5647 SENSOR SIMULATION (Monkey-Patch) ---
# We override YOLOv8's default Albumentations to inject specific ESP32 camera artifacts
def custom_albumentations_init(self, p=1.0):
    self.p = p
    self.transform = None
    try:
        import albumentations as A
        # Simulating OV5647 ESP32 streaming artifacts:
        T = [
            A.ImageCompression(quality_lower=20, quality_upper=60, p=0.5), # ESP32 heavy JPEG compression
            A.MotionBlur(blur_limit=7, p=0.3),                             # 10fps slow shutter motion blur
            A.GaussNoise(var_limit=(10.0, 50.0), p=0.4),                   # Tiny sensor low-light noise
            A.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.1, p=0.4), # Bad auto-exposure
            A.ToGray(p=0.05),
            A.CLAHE(p=0.05)
        ]
        self.transform = A.Compose(T, bbox_params=A.BboxParams(format='yolo', label_fields=['class_labels']))
    except ImportError:
        pass

ultralytics.data.augment.Albumentations.__init__ = custom_albumentations_init
# -----------------------------------------------
# 2. Check if we are resuming from a previous Kaggle session
checkpoint_path = "/kaggle/working/last.pt"

if os.path.exists(checkpoint_path):
    print("Found existing Kaggle checkpoint! Resuming training...")
    model = YOLO(checkpoint_path)
    resume_flag = True
else:
    print("Starting fresh from local laptop weights...")
    model = YOLO("/kaggle/input/hashtag-person-detection-v1/best.pt")
    resume_flag = False

# 3. Dynamically fix the dataset YAML path
import yaml
# Kaggle converts "Hashtag Dataset" into the slug "hashtag-dataset"
dataset_dir = "/kaggle/input/hashtag-dataset"
working_yaml = "/kaggle/working/Combined_Kaggle.yaml"

with open(f"{dataset_dir}/Combined_Kaggle.yaml", "r") as f:
    config = yaml.safe_load(f)

config['path'] = dataset_dir

with open(working_yaml, "w") as f:
    yaml.dump(config, f, default_flow_style=False)

# 4. Start the massive training block
results = model.train(
    data=working_yaml,
    epochs=150,           # Massive convergence goal
    time=11.5,            # Safely stop at 11.5 hours to save the checkpoint
    imgsz=640,            
    batch=16,             # We can safely double the batch size thanks to 16GB VRAM!
    device=[0, 1],        # Use BOTH T4 GPUs! (DataParallel)
    resume=resume_flag,
    
    # Same powerful augmentations
    mosaic=1.0,       
    mixup=0.2,        
    copy_paste=0.3,   
    erasing=0.4,      
    
    # Optimizer settings
    optimizer="AdamW",
    lr0=0.001,
    box=7.5,
    cls=0.5,
    
    project="/kaggle/working/Advanced_Person_Detection",
    name="Occlusion_Camouflage_Kaggle"
)

# 3. Copy the final weights to the root working directory so they are easy to download
shutil.copy("/kaggle/working/Advanced_Person_Detection/Occlusion_Camouflage_Kaggle/weights/last.pt", "/kaggle/working/last.pt")
try:
    shutil.copy("/kaggle/working/Advanced_Person_Detection/Occlusion_Camouflage_Kaggle/weights/best.pt", "/kaggle/working/best.pt")
except FileNotFoundError:
    pass
print("Training block complete! Weights saved to /kaggle/working/")
