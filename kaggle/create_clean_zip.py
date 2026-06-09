import os
import zipfile
import time

source_dir = r"d:\Instrek\Hashtags\HashtagV2\src\datasets"
target_zip = r"d:\Instrek\Hashtags\HashtagV2\kaggle\hashtag_dataset_clean.zip"

folders_to_zip = [
    "tinyperson",
    "coco_persons",
    "WiderPerson",
    "OChuman",
    "VisDrone",
    "CrowdHuman_YOLO"
]

print(f"Creating clean zip: {target_zip}")
start_time = time.time()

# We use ZIP_STORED because JPEGs don't compress well.
# This makes the zipping process 10x faster (only limited by SSD write speed)
# and prevents the duplicate directory bug in Kaggle.
with zipfile.ZipFile(target_zip, 'w', zipfile.ZIP_STORED) as zipf:
    # 1. Add the yaml file
    yaml_path = r"d:\Instrek\Hashtags\HashtagV2\kaggle\Combined_Kaggle.yaml"
    zipf.write(yaml_path, arcname="Combined_Kaggle.yaml")
    
    # 2. Add the dataset folders
    for folder in folders_to_zip:
        folder_path = os.path.join(source_dir, folder)
        print(f"Adding {folder}...")
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith(('.zip', '.tar', '.gz')):
                    print(f"Skipping archive: {file}")
                    continue
                file_path = os.path.join(root, file)
                # Ensure the path inside the zip starts with the folder name and uses forward slashes
                arcname = os.path.relpath(file_path, source_dir).replace("\\", "/")
                zipf.write(file_path, arcname=arcname)

print(f"Finished in {time.time() - start_time:.2f} seconds!")
