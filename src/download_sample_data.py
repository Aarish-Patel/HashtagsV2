import os
import urllib.request
import zipfile
import shutil

def download_and_extract(url, extract_to="datasets"):
    print(f"[*] Downloading {url}...")
    os.makedirs(extract_to, exist_ok=True)
    zip_path = os.path.join(extract_to, "coco8.zip")
    urllib.request.urlretrieve(url, zip_path)
    
    print(f"[*] Extracting to {extract_to}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
        
    os.remove(zip_path)
    print(f"[+] Download and extraction complete.")
    
    # The zip contains a 'coco8' folder. Let's make sure it's structured correctly for YOLO.
    coco8_dir = os.path.join(extract_to, "coco8")
    return coco8_dir

if __name__ == "__main__":
    url = "https://ultralytics.com/assets/coco8.zip"
    dataset_dir = download_and_extract(url)
    print(f"Dataset is ready at: {dataset_dir}")
    print(f"You can now run:")
    print(f"python dataset_manager.py --source {dataset_dir} --format yolo --output datasets/ready_coco8")
