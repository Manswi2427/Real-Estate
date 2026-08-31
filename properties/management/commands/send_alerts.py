import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from properties.models import SavedSearch, Property, Message

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'V5 - Send alerts for saved searches by checking properties created since last_notified_at'

    def handle(self, *args, **options):
        self.stdout.write("Starting send_alerts job...")
        
        saved_searches = SavedSearch.objects.all()
        alerts_sent = 0
        
        for search in saved_searches:
            # Find properties that were created AFTER the last time we notified this search
            recent_properties = Property.objects.filter(
                created_at__gt=search.last_notified_at,
                status='active'
            )
            
            # Find matching properties
            matching_properties = []
            for prop in recent_properties:
                if search.matches_property(prop):
                    matching_properties.append(prop)
                    
            if matching_properties:
                self.stdout.write(f"Found {len(matching_properties)} matches for search '{search.name}' (User: {search.buyer.username})")
                
                # We could send one combined message or individual messages
                for prop in matching_properties:
                    subject = f"Alert: Property matches your search '{search.name}'"
                    body = (
                        f"Hello {search.buyer.username},\n\n"
                        f"A property '{prop.title}' matches your saved search criteria "
                        f"for '{search.name}'.\n\n"
                        f"Check it out!"
                    )
                    
                    Message.objects.create(
                        sender=prop.owner,
                        receiver=search.buyer,
                        property=prop,
                        subject=subject,
                        body=body
                    )
                    alerts_sent += 1
                
                search.last_notified_at = timezone.now()
                search.save(update_fields=['last_notified_at'])
                
        self.stdout.write(self.style.SUCCESS(f"Successfully sent {alerts_sent} alerts."))
