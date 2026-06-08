import os
import yaml
from pathlib import Path
from ultralytics.utils.downloads import download
from ultralytics.utils.checks import check_yaml

def download_ultralytics_dataset(yaml_name, target_dir="datasets"):
    print(f"[*] Fetching dataset info for {yaml_name}...")
    yaml_path = check_yaml(yaml_name)
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        
    download_url = data.get('download')
    if not download_url:
        print(f"[!] No download link found in {yaml_name}")
        return
        
    print(f"[*] Downloading {yaml_name} to {target_dir} (This may take a while)...")
    
    # Store current dir
    cwd = os.getcwd()
    
    # Ultralytics download function usually extracts to the current directory or a specific datasets dir
    # Let's ensure it goes to our target
    os.makedirs(target_dir, exist_ok=True)
    os.chdir(target_dir)
    
    try:
        # Download can be a string or list of strings
        if isinstance(download_url, str):
            download(download_url)
        elif isinstance(download_url, list):
            for url in download_url:
                download(url)
        else:
            # Sometimes it's a script. Let's just use the direct URL if we know it.
            pass
            
    except Exception as e:
        print(f"[!] Error downloading: {e}")
    finally:
        os.chdir(cwd)
        
    print(f"[+] Finished downloading {yaml_name}")

if __name__ == "__main__":
    print("============================================================")
    print("  HASHTAG V2 — ADVANCED DATASET DOWNLOADER")
    print("============================================================")
    print("Downloading advanced datasets for small/occluded humans...")
    
    # VisDrone: Drone footage, tiny humans from top-down angles
    download_ultralytics_dataset("VisDrone.yaml")
    
    # WiderPerson: Dense crowds, occluded humans, body parts
    # WiderPerson isn't built into standard Ultralytics YAMLs by default with a direct zip,
    # but let's try Argoverse (autonomous driving, small pedestrians)
    download_ultralytics_dataset("Argoverse.yaml")

    print("\n[+] Downloads complete!")
    print("You can now process these with dataset_manager.py")
