import math
import os
import requests
import time

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def download_tiles(base_lat, base_lon, zoom_start=10, zoom_end=18, radius=3):
    headers = {
        'User-Agent': 'OfflineTacticalMapDownloader/1.0'
    }
    
    # URL format: https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}
    base_url = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    
    out_dir = r"D:\Instrek\Hashtags\HashtagV2\frontend\public\tiles"
    os.makedirs(out_dir, exist_ok=True)
    
    total_downloaded = 0
    for z in range(zoom_start, zoom_end + 1):
        cx, cy = deg2num(base_lat, base_lon, z)
        
        for x in range(cx - radius, cx + radius + 1):
            for y in range(cy - radius, cy + radius + 1):
                url = base_url.format(z=z, x=x, y=y)
                
                tile_path = os.path.join(out_dir, str(z), str(x))
                os.makedirs(tile_path, exist_ok=True)
                
                file_path = os.path.join(tile_path, f"{y}.png")
                
                if not os.path.exists(file_path):
                    try:
                        resp = requests.get(url, headers=headers, timeout=10)
                        if resp.status_code == 200:
                            with open(file_path, "wb") as f:
                                f.write(resp.content)
                            total_downloaded += 1
                            print(f"Downloaded z={z} x={x} y={y}")
                        else:
                            print(f"Failed {url} - Status: {resp.status_code}")
                    except Exception as e:
                        print(f"Error {url}: {e}")
                    
                    time.sleep(0.1)  # Be polite to the server
                else:
                    pass # already downloaded
                    
    print(f"Finished! Downloaded {total_downloaded} new tiles.")

if __name__ == "__main__":
    lat = 24.1655665
    lon = 94.2599847
    print(f"Downloading tiles for center: {lat}, {lon}")
    # Download zoom levels 10 to 18 with a 3-tile radius (7x7 grid per zoom)
    download_tiles(lat, lon, zoom_start=10, zoom_end=18, radius=3)
