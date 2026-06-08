import os
import glob
import datetime

CLIPS_DIR = r"D:\Instrek\Hashtags\HashtagV2\src\Clips"

def main():
    # Get all .mp4 files in the directory
    mp4_files = glob.glob(os.path.join(CLIPS_DIR, "*.mp4"))
    
    # Sort them by modification time (newest first)
    mp4_files.sort(key=os.path.getmtime, reverse=True)
    
    # Keep the top 3
    keep_mp4s = mp4_files[:3]
    
    # Delete the rest
    for mp4 in mp4_files[3:]:
        os.remove(mp4)
        json_file = mp4.replace(".mp4", "_report.json")
        if os.path.exists(json_file):
            os.remove(json_file)
            
    print(f"Deleted {len(mp4_files) - 3} old clips.")
    
    # Rename the remaining 3
    for mp4 in keep_mp4s:
        base_name = os.path.basename(mp4)
        # Parse old format: HASH-1_THREAT_20260608_115046.mp4
        parts = base_name.split('_')
        node_id = parts[0]
        
        # Hardcode some node mappings for the existing dummy files
        node_name = "TIGER_CHONGJAN" if node_id == "HASH-1" else "PANGAL_SANGJAI" if node_id == "HASH-2" else node_id
        loc = "24.165_94.259" if node_id == "HASH-1" else "24.180_94.260" if node_id == "HASH-2" else "UNKNOWN"
        
        # Keep original timestamp from filename if available
        # HASH-1_THREAT_20260608_115046.mp4 -> parts[2] is 20260608, parts[3] is 115046.mp4
        if len(parts) >= 4 and "THREAT" in parts:
            ts_date = parts[2]
            ts_time = parts[3].replace(".mp4", "")
            ts = f"{ts_date}_{ts_time}"
        else:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
        new_name = f"{ts}_{loc}_{node_name}.mp4"
        new_mp4 = os.path.join(CLIPS_DIR, new_name)
        
        # Rename MP4
        if mp4 != new_mp4:
            os.rename(mp4, new_mp4)
            print(f"Renamed {base_name} -> {new_name}")
            
        # Rename JSON and update its clip_file field
        old_json = mp4.replace(".mp4", "_report.json")
        new_json = new_mp4.replace(".mp4", "_report.json")
        if os.path.exists(old_json):
            import json
            with open(old_json, 'r') as f:
                try:
                    data = json.load(f)
                    data['clip_file'] = new_name
                except:
                    data = {}
            with open(old_json, 'w') as f:
                json.dump(data, f)
            if old_json != new_json:
                os.rename(old_json, new_json)

if __name__ == "__main__":
    main()
