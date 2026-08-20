from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from properties.models import Amenity, Profile, Property


AMENITIES = [
    ("WiFi", "fa-solid fa-wifi"),
    ("Swimming Pool", "fa-solid fa-water-ladder"),
    ("Covered Parking", "fa-solid fa-square-parking"),
    ("24/7 Security", "fa-solid fa-shield-halved"),
    ("Gym", "fa-solid fa-dumbbell"),
    ("Power Backup", "fa-solid fa-bolt"),
    ("Clubhouse", "fa-solid fa-champagne-glasses"),
    ("Pet Friendly", "fa-solid fa-paw"),
    ("Garden", "fa-solid fa-tree"),
    ("Elevator", "fa-solid fa-elevator"),
]

PROPERTIES = [
    dict(title="Sunlit 3BHK in Koregaon Park", property_type="APARTMENT", listing_type="SALE",
         price=8500000, area_sqft=1450, bedrooms=3, bathrooms=2, city="Pune", state="Maharashtra",
         address="14 Lane 5, Koregaon Park", zipcode="411001", latitude=Decimal("18.5362"), longitude=Decimal("73.8938"),
         amenities=["WiFi", "Swimming Pool", "Gym", "24/7 Security"], featured=True),
    dict(title="Modern Villa with Private Garden", property_type="VILLA", listing_type="SALE",
         price=21000000, area_sqft=3200, bedrooms=4, bathrooms=4, city="Bengaluru", state="Karnataka",
         address="27 Whitefield Main Road", zipcode="560066", latitude=Decimal("12.9698"), longitude=Decimal("77.7500"),
         amenities=["Garden", "Covered Parking", "24/7 Security", "Power Backup"], featured=True),
    dict(title="Cozy 1BHK Near Metro Station", property_type="APARTMENT", listing_type="RENT",
         price=18000, area_sqft=650, bedrooms=1, bathrooms=1, city="Mumbai", state="Maharashtra",
         address="Andheri West, Link Road", zipcode="400058", latitude=Decimal("19.1364"), longitude=Decimal("72.8296"),
         amenities=["WiFi", "Elevator", "Power Backup"], featured=False),
    dict(title="Spacious Family House with Backyard", property_type="HOUSE", listing_type="SALE",
         price=9800000, area_sqft=2100, bedrooms=3, bathrooms=3, city="Ahmedabad", state="Gujarat",
         address="Satellite Road", zipcode="380015", latitude=Decimal("23.0225"), longitude=Decimal("72.5714"),
         amenities=["Garden", "Covered Parking", "Pet Friendly"], featured=True),
    dict(title="Premium 2BHK with Clubhouse Access", property_type="APARTMENT", listing_type="RENT",
         price=32000, area_sqft=1100, bedrooms=2, bathrooms=2, city="Pune", state="Maharashtra",
         address="Baner - Balewadi Road", zipcode="411045", latitude=Decimal("18.5679"), longitude=Decimal("73.7788"),
         amenities=["Swimming Pool", "Clubhouse", "Gym", "WiFi", "24/7 Security"], featured=True),
    dict(title="Commercial Office Space in Business District", property_type="COMMERCIAL", listing_type="RENT",
         price=95000, area_sqft=1800, bedrooms=0, bathrooms=2, city="Gurugram", state="Haryana",
         address="Cyber City, DLF Phase 3", zipcode="122002", latitude=Decimal("28.4950"), longitude=Decimal("77.0890"),
         amenities=["WiFi", "Elevator", "Covered Parking", "24/7 Security"], featured=False),
    dict(title="Residential Plot Ready for Construction", property_type="PLOT", listing_type="SALE",
         price=4200000, area_sqft=2400, bedrooms=0, bathrooms=0, city="Jaipur", state="Rajasthan",
         address="Vaishali Nagar Extension", zipcode="302021", latitude=Decimal("26.9124"), longitude=Decimal("75.7873"),
         amenities=["24/7 Security"], featured=False),
    dict(title="Luxury Penthouse with City Skyline View", property_type="APARTMENT", listing_type="SALE",
         price=32000000, area_sqft=2800, bedrooms=4, bathrooms=4, city="Mumbai", state="Maharashtra",
         address="Lower Parel", zipcode="400013", latitude=Decimal("18.9960"), longitude=Decimal("72.8300"),
         amenities=["Swimming Pool", "Gym", "Clubhouse", "24/7 Security", "Elevator", "Power Backup"], featured=True),
    dict(title="Charming Bungalow Near the Lake", property_type="HOUSE", listing_type="RENT",
         price=45000, area_sqft=1900, bedrooms=3, bathrooms=2, city="Udaipur", state="Rajasthan",
         address="Fatehsagar Lake Road", zipcode="313001", latitude=Decimal("24.5943"), longitude=Decimal("73.6839"),
         amenities=["Garden", "Pet Friendly", "Covered Parking"], featured=False),
]


class Command(BaseCommand):
    help = "Seeds the database with demo amenities, an agent/buyer account, and sample properties."

    def handle(self, *args, **options):
        # Demo agent
        agent, created = User.objects.get_or_create(
            username="demoagent", defaults={"email": "agent@estateportal.demo", "first_name": "Riya", "last_name": "Sharma"}
        )
        if created:
            agent.set_password("DemoPass123!")
            agent.save()
        Profile.objects.update_or_create(
            user=agent, defaults={"role": Profile.Role.AGENT, "phone": "+91 90000 12345", "agency_name": "Skyline Realty"}
        )

        # Demo buyer
        buyer, created = User.objects.get_or_create(
            username="demobuyer", defaults={"email": "buyer@estateportal.demo", "first_name": "Aman", "last_name": "Verma"}
        )
        if created:
            buyer.set_password("DemoPass123!")
            buyer.save()
        Profile.objects.update_or_create(user=buyer, defaults={"role": Profile.Role.BUYER})

        # Amenities
        amenity_objs = {}
        for name, icon in AMENITIES:
            obj, _ = Amenity.objects.get_or_create(name=name, defaults={"icon": icon})
            amenity_objs[name] = obj

        # Properties
        created_count = 0
        for data in PROPERTIES:
            if Property.objects.filter(title=data["title"]).exists():
                continue
            amenity_names = data.pop("amenities")
            featured = data.pop("featured")
            prop = Property.objects.create(
                agent=agent,
                status=Property.Status.AVAILABLE,
                is_featured=featured,
                description=(
                    f"A beautiful {data['bedrooms']}-bedroom {data['property_type'].lower()} "
                    f"located in {data['city']}, offering {data['area_sqft']} sq. ft. of well-planned space. "
                    "Close to schools, hospitals, and major transit routes — perfect for families and professionals alike."
                ),
                **data,
            )
            prop.amenities.set([amenity_objs[n] for n in amenity_names])
            created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete: {len(amenity_objs)} amenities, {created_count} new properties. "
            f"Demo agent login -> username: demoagent / password: DemoPass123!"
        ))
