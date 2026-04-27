from django.db import migrations, models
from django.utils.text import slugify


def populate_category_slugs(apps, schema_editor):
    Category = apps.get_model('forum', 'ForumCategory')

    used_slugs = set(
        Category.objects.exclude(slug__isnull=True)
        .exclude(slug='')
        .values_list('slug', flat=True)
    )

    for category in Category.objects.all().order_by('id'):
        base_slug = slugify(category.name) or f'category-{category.id}'
        slug = base_slug
        suffix = 2
        while slug in used_slugs:
            slug = f'{base_slug}-{suffix}'
            suffix += 1

        category.slug = slug
        category.save(update_fields=['slug'])
        used_slugs.add(slug)


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='forumcategory',
            name='slug',
            field=models.SlugField(blank=True, null=True),
        ),
        migrations.RunPython(populate_category_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='forumcategory',
            name='slug',
            field=models.SlugField(unique=True),
        ),
    ]