with open("templates/resource_hub/browse_resources.html", "r", encoding="utf-8") as f:
    content = f.read()

old = ".resource-thumbnail { display:none !important; }\n</style>"
new = """.resource-thumbnail { display:none !important; }
  .navbar-logo { color: #fff !important; }
  .navbar-logo span { color: #fff !important; }
  .logo-accent { color: #7c6af7 !important; }
  .logo-icon { color: #fff !important; }
  body > div > main { padding-top: 90px; }
</style>"""

content = content.replace(old, new)

with open("templates/resource_hub/browse_resources.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Done!")