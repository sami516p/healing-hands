import re
import os

try:
    with open(r'C:\Users\Sunil Kumar Purohit\.gemini\antigravity\brain\fdf135cc-32c0-4947-8b62-e6964add6f5d\.system_generated\steps\101\content.md', 'r', encoding='utf-8') as f:
        google_html = f.read()
    
    # Google uses lh3 or lh5 or similar
    google_imgs = re.findall(r'https://lh[0-9]\.googleusercontent\.com/p/[a-zA-Z0-9_-]+', google_html)
    google_imgs = list(set(google_imgs))
    
    print("--- GOOGLE IMAGES ---")
    for img in google_imgs[:15]:
        # Google images often need a size parameter to render properly in browser, e.g. =s1600-w400
        print(f"{img}=s800")
except Exception as e:
    print("Error reading google:", e)

try:
    with open(r'C:\Users\Sunil Kumar Purohit\.gemini\antigravity\brain\fdf135cc-32c0-4947-8b62-e6964add6f5d\.system_generated\steps\27\content.md', 'r', encoding='utf-8') as f:
        wix_html = f.read()
    wix_imgs = re.findall(r'https://static\.wixstatic\.com/media/[a-zA-Z0-9_]+\.jpg', wix_html)
    wix_imgs = list(set(wix_imgs))
    
    print("\n--- WIX IMAGES ---")
    for img in wix_imgs[:15]:
        print(img)
except Exception as e:
    print("Error reading wix:", e)
