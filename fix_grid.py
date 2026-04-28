with open("templates/resource_hub/browse_resources.html", "r", encoding="utf-8") as f:
    content = f.read()

# Join all lines, then fix the broken div
import re
fixed = re.sub(
    r'<div class="resources-grid" id="resources-grid"[^>]*>(\s*</div>)?',
    '<div class="resources-grid" id="resources-grid" style="display:grid!important;grid-template-columns:repeat(3,1fr)!important;gap:20px!important;">',
    content,
    flags=re.DOTALL
)

with open("templates/resource_hub/browse_resources.html", "w", encoding="utf-8") as f:
    f.write(fixed)

print("Done!")