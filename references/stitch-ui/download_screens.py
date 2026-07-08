import json
import urllib.request
import os

output_path = r"C:\Users\WELCOME\.gemini\antigravity-ide\brain\748c53f4-72a4-4c49-8879-1b0be9da3d12\.system_generated\steps\7\output.txt"
dest_dir = r"c:\Users\WELCOME\Desktop\FDAS Project\references\stitch-ui"

with open(output_path, "r", encoding="utf-8") as f:
    data = json.load(f)

for screen in data["screens"]:
    title = screen["title"]
    url = screen["htmlCode"]["downloadUrl"]
    print(f"Downloading {title}...")
    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).rstrip()
    dest_path = os.path.join(dest_dir, f"{safe_title}.html")
    try:
        urllib.request.urlretrieve(url, dest_path)
        print(f"Saved {safe_title}.html")
    except Exception as e:
        print(f"Failed to download {title}: {e}")
