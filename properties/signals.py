from django.contrib.auth.models import User
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Profile, Property, PropertyImage


@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    """Ensure every user has a Profile (defaults to Buyer)."""
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_delete, sender=PropertyImage)
def promote_new_primary_after_delete(sender, instance, **kwargs):
    """
    V3 – When a PropertyImage is deleted:
      - Check if the property still has a primary image.
      - If not, elect the next available image as primary and sync Property.image.
      - If there are no more images left at all, clear the Property.image field.

    Note: We check DB state (not instance.is_primary) to handle cases where
    the instance's in-memory state may be stale (e.g. was promoted to primary
    by a previous deletion's signal).
    """
    try:
        prop = Property.objects.get(pk=instance.property_id)
    except Property.DoesNotExist:
        return

    # Check if a primary image still exists after this deletion
    still_has_primary = PropertyImage.objects.filter(property=prop, is_primary=True).exists()
    if still_has_primary:
        return  # Nothing to do

    # No primary exists: elect the next available image
    next_image = PropertyImage.objects.filter(property=prop).first()
    if next_image:
        PropertyImage.objects.filter(property=prop).update(is_primary=False)
        next_image.is_primary = True
        next_image.save(update_fields=['is_primary'])
        Property.objects.filter(pk=prop.pk).update(image=next_image.image.name)
    else:
        # No images left at all — clear the Property thumbnail field completely
        Property.objects.filter(pk=prop.pk).update(image=None)
