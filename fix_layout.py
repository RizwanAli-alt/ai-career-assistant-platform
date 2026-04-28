with open("templates/resource_hub/browse_resources.html", "r", encoding="utf-8") as f:
    content = f.read()

# Wrap the block content inside a container
content = content.replace(
    '{% block content %}',
    '{% block content %}\n<div style="max-width:1200px;margin:0 auto;padding:40px 32px;">'
)

content = content.replace(
    '{% endblock %}',
    '</div>\n{% endblock %}'
)

with open("templates/resource_hub/browse_resources.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Done!")