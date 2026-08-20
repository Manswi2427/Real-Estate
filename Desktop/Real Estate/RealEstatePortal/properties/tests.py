from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from properties.models import Amenity, Profile, Property


class PropertySearchAPITests(TestCase):

    def setUp(self):
        # Create an Agent user
        self.agent_user = User.objects.create_user(
            username='testagent',
            email='agent@test.com',
            password='Password123!'
        )
        self.agent_profile = self.agent_user.profile
        self.agent_profile.role = Profile.Role.AGENT
        self.agent_profile.phone = '+1 555-0199'
        self.agent_profile.agency_name = 'Apex Realty'
        self.agent_profile.save()

        # Create some amenities
        self.wifi = Amenity.objects.create(name='WiFi', icon='fa-wifi', description='High speed internet')
        self.pool = Amenity.objects.create(name='Pool', icon='fa-swimming-pool', description='Swimming pool')
        self.gym = Amenity.objects.create(name='Gym', icon='fa-dumbbell', description='Fitness center')

        # Create Property 1: Apartment, Rent, 15000, 700sqft, 1 Bed, 1 Bath, Pune, WiFi, Pool
        self.p1 = Property.objects.create(
            title='Cozy Apartment',
            description='Nice place near Pune university',
            agent=self.agent_user,
            property_type=Property.PropertyType.APARTMENT,
            listing_type=Property.ListingType.RENT,
            status=Property.Status.AVAILABLE,
            price=Decimal('15000.00'),
            area_sqft=Decimal('700.00'),
            bedrooms=1,
            bathrooms=1,
            address='123 University Road',
            city='Pune',
            state='Maharashtra',
            zipcode='411007',
            latitude=Decimal('18.5204'),
            longitude=Decimal('73.8567'),
            is_featured=False
        )
        self.p1.amenities.add(self.wifi, self.pool)

        # Create Property 2: Villa, Sale, 12000000, 3000sqft, 4 Bed, 4 Bath, Bengaluru, Gym, Pool, WiFi
        self.p2 = Property.objects.create(
            title='Luxury Villa',
            description='Premium residency in Whitefield',
            agent=self.agent_user,
            property_type=Property.PropertyType.VILLA,
            listing_type=Property.ListingType.SALE,
            status=Property.Status.AVAILABLE,
            price=Decimal('12000000.00'),
            area_sqft=Decimal('3000.00'),
            bedrooms=4,
            bathrooms=4,
            address='45 Whitefield Main Road',
            city='Bengaluru',
            state='Karnataka',
            zipcode='560066',
            latitude=Decimal('12.9698'),
            longitude=Decimal('77.7500'),
            is_featured=True
        )
        self.p2.amenities.add(self.wifi, self.pool, self.gym)

        # Create Property 3: House, Sale, 5000000, 1800sqft, 3 Bed, 2 Bath, Pune, Gym, WiFi
        self.p3 = Property.objects.create(
            title='Spacious House',
            description='Lovely house with backyard',
            agent=self.agent_user,
            property_type=Property.PropertyType.HOUSE,
            listing_type=Property.ListingType.SALE,
            status=Property.Status.AVAILABLE,
            price=Decimal('5000000.00'),
            area_sqft=Decimal('1800.00'),
            bedrooms=3,
            bathrooms=2,
            address='89 Kothrud Road',
            city='Pune',
            state='Maharashtra',
            zipcode='411038',
            latitude=Decimal('18.5074'),
            longitude=Decimal('73.8077'),
            is_featured=True
        )
        self.p3.amenities.add(self.wifi, self.gym)

    def test_search_no_filters(self):
        """No filters should return all properties."""
        response = self.client.get(reverse('property_search_api'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_results'], 3)
        self.assertEqual(len(data['properties']), 3)

    def test_search_price_range(self):
        """Filter by price range."""
        # Property under 10M but above 100k
        response = self.client.get(reverse('property_search_api'), {'min_price': '100000', 'max_price': '6000000'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_results'], 1)
        self.assertEqual(data['properties'][0]['title'], 'Spacious House')

    def test_search_square_footage(self):
        """Filter by square footage (area_sqft)."""
        # Between 500 and 1000 sqft
        response = self.client.get(reverse('property_search_api'), {'min_area_sqft': '500', 'max_area_sqft': '1000'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_results'], 1)
        self.assertEqual(data['properties'][0]['title'], 'Cozy Apartment')

        # Between 1500 and 3500 sqft
        response = self.client.get(reverse('property_search_api'), {'min_area_sqft': '1500', 'max_area_sqft': '3500'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_results'], 2)

    def test_search_bedrooms_and_bathrooms(self):
        """Filter by bedrooms and bathrooms minimum values."""
        # 3+ bedrooms
        response = self.client.get(reverse('property_search_api'), {'bedrooms': '3'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_results'], 2)

        # 3+ bedrooms and 3+ bathrooms
        response = self.client.get(reverse('property_search_api'), {'bedrooms': '3', 'bathrooms': '3'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_results'], 1)
        self.assertEqual(data['properties'][0]['title'], 'Luxury Villa')

    def test_search_single_amenity(self):
        """Filter by a single amenity."""
        # Properties with Gym (p2, p3)
        response = self.client.get(reverse('property_search_api'), {'amenities': [str(self.gym.id)]})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_results'], 2)
        titles = [p['title'] for p in data['properties']]
        self.assertIn('Luxury Villa', titles)
        self.assertIn('Spacious House', titles)

    def test_search_multiple_amenities(self):
        """Filter by multiple amenities (must match all)."""
        # Properties with WiFi, Pool, AND Gym (only p2)
        response = self.client.get(
            reverse('property_search_api'),
            {'amenities': f"{self.wifi.id},{self.pool.id},{self.gym.id}"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_results'], 1)
        self.assertEqual(data['properties'][0]['title'], 'Luxury Villa')

    def test_search_keyword(self):
        """Filter by keyword match on title/address/city/state."""
        response = self.client.get(reverse('property_search_api'), {'keyword': 'Whitefield'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_results'], 1)
        self.assertEqual(data['properties'][0]['title'], 'Luxury Villa')

    def test_search_city(self):
        """Filter by city."""
        response = self.client.get(reverse('property_search_api'), {'city': 'Pune'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_results'], 2)

    def test_search_invalid_params(self):
        """API should return 400 error for invalid values."""
        response = self.client.get(reverse('property_search_api'), {'min_price': 'abc'})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('details', data)

    def test_search_sorting(self):
        """Check sorting options."""
        # Price Low to High
        response = self.client.get(reverse('property_search_api'), {'sort': 'price'})
        self.assertEqual(response.status_code, 200)
        properties = response.json()['properties']
        self.assertEqual(properties[0]['title'], 'Cozy Apartment')  # 15000
        self.assertEqual(properties[2]['title'], 'Luxury Villa')   # 12M

        # Price High to Low
        response = self.client.get(reverse('property_search_api'), {'sort': '-price'})
        self.assertEqual(response.status_code, 200)
        properties = response.json()['properties']
        self.assertEqual(properties[0]['title'], 'Luxury Villa')
        self.assertEqual(properties[2]['title'], 'Cozy Apartment')

    def test_search_pagination(self):
        """Check pagination offset and limits."""
        response = self.client.get(reverse('property_search_api'), {'limit': '1', 'offset': '1'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_results'], 3)
        self.assertEqual(len(data['properties']), 1)
