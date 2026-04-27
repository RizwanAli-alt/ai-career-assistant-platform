from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0002_category_slug'),
    ]

    operations = [
        migrations.AddField(
            model_name='forumcategory',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.RunSQL(
            sql=(
                "UPDATE forum_category "
                "SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
                "WHERE created_at IS NULL"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name='forumcategory',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]