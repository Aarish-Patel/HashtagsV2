from ultralytics import YOLO

def main():
    print("Starting Advanced Detection Training Pipeline")
    print("Initializing YOLOv8 model for Occluded/Small Person Detection")
    
    # Load a model (we use YOLOv8x for maximum capability on small objects)
    model = YOLO("yolov8x.pt")
    
    # Custom training configuration targeting occlusion and small objects
    # We heavily boost Mosaic, MixUp, and enable specific data augmentation
    print("Starting training with advanced augmentation...")
    results = model.train(
        data="datasets/Combined.yaml",
        epochs=50,        # Max epochs if time limit isn't hit first
        time=9.5,         # Auto-stop after 9.5 hours to fit the 10 hour window
        imgsz=640,        # Reduced from 800 to prevent OOM/memory issues
        batch=8,          # Increased batch size since imgsz is smaller
        device="0",       # Use GPU
        
        # Augmentation hyperparameters specifically for Occlusion and Camouflage
        mosaic=1.0,       # 100% chance of mosaic (crucial for small/occluded objects)
        mixup=0.2,        # 20% chance of MixUp
        copy_paste=0.3,   # 30% chance of copy-paste (great for pasting humans onto greenery)
        erasing=0.4,      # Random erasing (forces model to learn from partial visibility/limbs)
        
        # Optimizer settings
        optimizer="AdamW",
        lr0=0.001,
        
        # CIoU loss is default in YOLOv8, but we ensure box loss is prioritized
        box=7.5,
        cls=0.5,
        
        # Project tracking
        project="Advanced_Person_Detection",
        name="Occlusion_Camouflage_V1"
    )
    
    print("Training complete. Best model saved to Advanced_Person_Detection/Occlusion_Camouflage_V1/weights/best.pt")

if __name__ == "__main__":
    main()
