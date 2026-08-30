"""
V4 – Migration: creates the Message table.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0002_v3_property_image_gallery'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('is_read', models.BooleanField(default=False)),
                ('sent_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('sender', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sent_messages',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('receiver', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='received_messages',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('property', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='messages',
                    to='properties.property',
                    help_text='Optional property context for this message.',
                )),
                ('parent', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='replies',
                    to='properties.message',
                    help_text='Parent message for reply threading.',
                )),
            ],
            options={
                'ordering': ['-sent_at'],
                'indexes': [
                    models.Index(fields=['receiver', 'is_read'], name='props_msg_receiver_read_idx'),
                    models.Index(fields=['sender', 'sent_at'], name='props_msg_sender_sent_idx'),
                ],
            },
        ),
    ]
