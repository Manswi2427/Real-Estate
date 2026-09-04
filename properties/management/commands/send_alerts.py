import logging
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone
from properties.models import SavedSearch, Property, Message

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'V5 - Send email and message alerts for saved searches by checking newly listed properties'

    def handle(self, *args, **options):
        self.stdout.write("Starting send_alerts background job...")
        
        saved_searches = SavedSearch.objects.select_related('buyer').prefetch_related('amenities').all()
        alerts_sent = 0
        emails_sent = 0
        
        for search in saved_searches:
            # Find properties created or updated after the last notification time
            recent_properties = (
                Property.objects
                .filter(
                    created_at__gt=search.last_notified_at,
                    status=Property.Status.AVAILABLE,
                )
                .select_related('agent')
                .prefetch_related('amenities')
            )
            
            matching_properties = [p for p in recent_properties if search.matches_property(p)]
                    
            if matching_properties:
                self.stdout.write(
                    f"Found {len(matching_properties)} matches for search '{search.name}' (Buyer: {search.buyer.username})"
                )
                
                for prop in matching_properties:
                    subject = f"Property Alert: '{prop.title}' matches your search '{search.name}'"
                    body = (
                        f"Hello {search.buyer.first_name or search.buyer.username},\n\n"
                        f"A new property '{prop.title}' matches your saved search criteria for '{search.name}'.\n\n"
                        f"Property Highlights:\n"
                        f"- Type: {prop.get_property_type_display()} ({prop.get_listing_type_display()})\n"
                        f"- Price: ₹{prop.price}\n"
                        f"- Location: {prop.address}, {prop.city}, {prop.state}\n"
                        f"- Specifications: {prop.bedrooms} BHK | {prop.bathrooms} Baths | {prop.area_sqft} sq. ft.\n"
                        f"- Listed by: {prop.agent.get_full_name() or prop.agent.username}\n\n"
                        f"Log in to RealEstatePortal to view photos, maps, and contact the agent!"
                    )
                    
                    # 1. Internal Platform Message
                    Message.objects.create(
                        sender=prop.agent,
                        receiver=search.buyer,
                        property=prop,
                        subject=subject,
                        body=body
                    )
                    alerts_sent += 1
                    
                    # 2. Direct Email Alert
                    if search.buyer.email:
                        try:
                            send_mail(
                                subject=subject,
                                message=body,
                                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@estateportal.com'),
                                recipient_list=[search.buyer.email],
                                fail_silently=False,
                            )
                            emails_sent += 1
                        except Exception as e:
                            logger.error(f"Failed to send email to {search.buyer.email}: {e}")
                
                search.last_notified_at = timezone.now()
                search.save(update_fields=['last_notified_at'])
                
        self.stdout.write(
            self.style.SUCCESS(f"Successfully processed alerts: {alerts_sent} messages created, {emails_sent} emails dispatched.")
        )
