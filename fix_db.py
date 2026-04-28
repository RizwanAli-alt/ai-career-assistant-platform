import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection
cursor = connection.cursor()
cursor.execute('DROP TABLE IF EXISTS resource_hub_bookmark')
cursor.execute('DROP TABLE IF EXISTS resource_hub_userprogress')
cursor.execute('DROP TABLE IF EXISTS resource_hub_cvskillgap')
cursor.execute('DROP TABLE IF EXISTS resource_hub_resource')
cursor.execute("DELETE FROM django_migrations WHERE app='resource_hub'")
print('Done - tables dropped and migrations cleared')