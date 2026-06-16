import re

# Read About Us HTML
about_html = open(r'C:\Users\Sunil Kumar Purohit\.gemini\antigravity\brain\fdf135cc-32c0-4947-8b62-e6964add6f5d\.system_generated\steps\100\content.md', encoding='utf-8', errors='ignore').read()

# Try to extract plain text between tags for About Us
text_matches = re.findall(r'>([^<]+)<', about_html)
about_text = [t.strip() for t in text_matches if len(t.strip()) > 30]

print("--- ABOUT US TEXT ---")
for t in about_text:
    if "Golden" in t or "Salon" in t or "We" in t:
        print(t)

# Read Main HTML for Services and Images
main_html = open(r'C:\Users\Sunil Kumar Purohit\.gemini\antigravity\brain\fdf135cc-32c0-4947-8b62-e6964add6f5d\.system_generated\steps\27\content.md', encoding='utf-8', errors='ignore').read()

print("\n--- IMAGES ---")
images = re.findall(r'https://static\.wixstatic\.com/media/[a-zA-Z0-9_]+\.(?:jpg|jpeg|png)', main_html)
images.extend(re.findall(r'https://static\.wixstatic\.com/media/[a-zA-Z0-9_]+\.(?:jpg|jpeg|png)', about_html))
for img in list(set(images))[:10]:
    print(img)
