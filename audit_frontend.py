import re

with open(r'C:\Users\chanc\.gemini\antigravity\scratch\PlateTrackAI-Dashboard\frontend\app.js', 'r', encoding='utf-8') as f:
    js_content = f.read()

with open(r'C:\Users\chanc\.gemini\antigravity\scratch\PlateTrackAI-Dashboard\frontend\index.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

dom_ids = re.findall(r'document\.getElementById\(["\']([^"\']+)["\']\)', js_content)
missing = []
for dom_id in set(dom_ids):
    if f'id="{dom_id}"' not in html_content and f"id='{dom_id}'" not in html_content:
        missing.append(dom_id)

print(f"Total getElementById calls: {len(dom_ids)}")
print(f"Unique DOM IDs checked: {len(set(dom_ids))}")
print("Missing DOM IDs in index.html:", missing)
