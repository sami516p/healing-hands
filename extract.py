import re
from html.parser import HTMLParser

class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

data_google = open(r'C:\Users\Sunil Kumar Purohit\.gemini\antigravity\brain\fdf135cc-32c0-4947-8b62-e6964add6f5d\.system_generated\steps\101\content.md', encoding='utf-8', errors='ignore').read()
urls = re.findall(r'https://[^\"\'\s]+\.(?:jpg|jpeg|png)', data_google)
if not urls:
    urls = re.findall(r'https://lh3\.googleusercontent\.com/p/[a-zA-Z0-9_-]+', data_google)
print("GOOGLE IMAGES:", list(set(urls))[:10])

data_about = open(r'C:\Users\Sunil Kumar Purohit\.gemini\antigravity\brain\fdf135cc-32c0-4947-8b62-e6964add6f5d\.system_generated\steps\100\content.md', encoding='utf-8', errors='ignore').read()
s = MLStripper()
s.feed(data_about)
text = s.get_data()
text = re.sub(r'\s+', ' ', text)
# Find the actual about us paragraph by searching for keywords
idx = text.lower().find('golden hive')
print("ABOUT TEXT:", text[max(0, idx-50):idx+500])

data_services = open(r'C:\Users\Sunil Kumar Purohit\.gemini\antigravity\brain\fdf135cc-32c0-4947-8b62-e6964add6f5d\.system_generated\steps\27\content.md', encoding='utf-8', errors='ignore').read()
s2 = MLStripper()
s2.feed(data_services)
text2 = s2.get_data()
text2 = re.sub(r'\s+', ' ', text2)
idx2 = text2.lower().find('hair cut')
if idx2 == -1: idx2 = text2.lower().find('services')
print("SERVICES TEXT:", text2[max(0, idx2-50):idx2+800])
