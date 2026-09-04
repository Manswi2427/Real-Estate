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


# ─────────────────────────────────────────────────────────────────────────────
# V5 - Saved Search Notifications
# ─────────────────────────────────────────────────────────────────────────────

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from .models import SavedSearch, Message

@receiver(post_save, sender=Property)
def notify_saved_searches(sender, instance, created, **kwargs):
    """
    V5 - When a new property is created, find matching saved searches,
    send an internal message, and dispatch an email alert to the buyer.
    """
    if not created:
        return
        
    if instance.status != Property.Status.AVAILABLE:
        return

    saved_searches = SavedSearch.objects.select_related('buyer').prefetch_related('amenities').all()
    for search in saved_searches:
        if search.matches_property(instance):
            subject = f"Alert: New Property matches your search '{search.name}'"
            body = (
                f"Hello {search.buyer.first_name or search.buyer.username},\n\n"
                f"A new property '{instance.title}' has just been listed which matches "
                f"your saved search criteria for '{search.name}'.\n\n"
                f"Property Details:\n"
                f"- Type: {instance.get_property_type_display()} ({instance.get_listing_type_display()})\n"
                f"- Price: ₹{instance.price}\n"
                f"- Location: {instance.address}, {instance.city}, {instance.state}\n"
                f"- Bedrooms: {instance.bedrooms} | Bathrooms: {instance.bathrooms}\n"
                f"- Area: {instance.area_sqft} sq. ft.\n\n"
                f"Check it out on RealEstatePortal!"
            )
            
            # 1. Internal Message
            Message.objects.create(
                sender=instance.agent,
                receiver=search.buyer,
                property=instance,
                subject=subject,
                body=body
            )
            
            # 2. Email alert
            if search.buyer.email:
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@estateportal.com'),
                    recipient_list=[search.buyer.email],
                    fail_silently=True,
                )
            
            search.last_notified_at = timezone.now()
            search.save(update_fields=['last_notified_at'])
