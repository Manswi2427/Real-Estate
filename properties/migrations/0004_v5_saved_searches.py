"""
V5 – Migration: creates the SavedSearch table.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0003_v4_messaging'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SavedSearch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='A friendly name for this saved search.', max_length=150)),
                ('keyword', models.CharField(blank=True, max_length=200)),
                ('property_type', models.CharField(blank=True, max_length=20)),
                ('listing_type', models.CharField(blank=True, max_length=10)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('state', models.CharField(blank=True, max_length=100)),
                ('min_price', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('max_price', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('min_area', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('max_area', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('bedrooms', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('bathrooms', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_notified_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('buyer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='saved_searches',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('amenities', models.ManyToManyField(
                    blank=True,
                    related_name='saved_searches',
                    to='properties.amenity',
                )),
            ],
            options={
                'ordering': ['-created_at'],
                'verbose_name': 'Saved Search',
                'verbose_name_plural': 'Saved Searches',
            },
        ),
    ]
