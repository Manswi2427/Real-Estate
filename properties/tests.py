"""
V3 – Media Gallery Unit Tests
Tests the PropertyImage model behaviour:
  - creation and auto-promotion logic
  - primary designation and sync to Property.image
  - primary deletion triggers election of next image
"""

import io

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.test import Client
from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from .models import Amenity, Message, Profile, Property, PropertyAmenity, PropertyImage, SavedSearch


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_image(name="test.jpg"):
    """Create a minimal in-memory JPEG for upload testing."""
    # 1×1 red pixel JPEG
    data = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c'
        b'\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c'
        b'\x1c $.\' ",#\x1c\x1c(7),\x01\x02\x01\x01\x01\x01\x01\x01\x01\x01\x01'
        b'\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01'
        b'\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01'
        b'\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\xff\xc0\x00\x0b\x08\x00'
        b'\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01'
        b'\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05'
        b'\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04'
        b'\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!'
        b'1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1'
        b'\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJ'
        b'STUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93'
        b'\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa'
        b'\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8'
        b'\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5'
        b'\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff'
        b'\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd2\x8a(\x03\xff\xd9'
    )
    return SimpleUploadedFile(name, data, content_type='image/jpeg')


def _make_agent():
    """Create an agent user with profile."""
    user = User.objects.create_user(username='agent1', password='agent1pass', email='agent1@example.com')
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.role = Profile.Role.AGENT
    profile.save()
    return user


def _make_property(agent):
    """Create a minimal Property for testing."""
    return Property.objects.create(
        title='Test Villa',
        description='A lovely test property.',
        agent=agent,
        property_type=Property.PropertyType.VILLA,
        listing_type=Property.ListingType.SALE,
        status=Property.Status.AVAILABLE,
        price=5000000,
        area_sqft=1500,
        bedrooms=3,
        bathrooms=2,
        address='123 Test St',
        city='TestCity',
        state='TestState',
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

@override_settings(
    MEDIA_ROOT='/tmp/test_media/',
    DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage',
)
class PropertyImageCreationTest(TestCase):
    """Tests for V3 PropertyImage model creation and auto-promotion."""

    def setUp(self):
        self.agent = _make_agent()
        self.prop = _make_property(self.agent)

    def test_first_image_becomes_primary(self):
        """The first PropertyImage saved for a property is auto-set as primary."""
        img = PropertyImage.objects.create(
            property=self.prop,
            image=_make_image('first.jpg'),
        )
        img.refresh_from_db()
        self.assertTrue(img.is_primary, "First image should be auto-promoted to primary.")

    def test_second_image_is_not_primary(self):
        """Subsequent images are NOT auto-promoted if a primary already exists."""
        img1 = PropertyImage.objects.create(property=self.prop, image=_make_image('a.jpg'))
        img2 = PropertyImage.objects.create(property=self.prop, image=_make_image('b.jpg'))
        img1.refresh_from_db()
        img2.refresh_from_db()
        self.assertTrue(img1.is_primary, "First image should remain primary.")
        self.assertFalse(img2.is_primary, "Second image should NOT be primary.")

    def test_property_image_field_synced_to_primary(self):
        """Property.image is synced to the primary gallery image path."""
        img = PropertyImage.objects.create(
            property=self.prop,
            image=_make_image('primary.jpg'),
        )
        self.prop.refresh_from_db()
        self.assertIn(img.image.name, self.prop.image.name)


@override_settings(
    MEDIA_ROOT='/tmp/test_media/',
    DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage',
)
class PropertyImagePrimaryPromotionTest(TestCase):
    """Tests for manually setting a primary image."""

    def setUp(self):
        self.agent = _make_agent()
        self.prop = _make_property(self.agent)
        self.img1 = PropertyImage.objects.create(property=self.prop, image=_make_image('x.jpg'))
        self.img2 = PropertyImage.objects.create(property=self.prop, image=_make_image('y.jpg'))

    def test_make_primary_switches_flag(self):
        """make_primary() sets the correct image as primary and clears others."""
        self.img2.make_primary()
        self.img1.refresh_from_db()
        self.img2.refresh_from_db()
        self.assertFalse(self.img1.is_primary, "img1 should no longer be primary.")
        self.assertTrue(self.img2.is_primary, "img2 should now be primary.")

    def test_make_primary_syncs_property_image(self):
        """make_primary() syncs Property.image to the new primary."""
        self.img2.make_primary()
        self.prop.refresh_from_db()
        self.assertIn(self.img2.image.name, self.prop.image.name)


@override_settings(
    MEDIA_ROOT='/tmp/test_media/',
    DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage',
)
class PropertyImageDeletionTest(TestCase):
    """Tests for the post_delete signal logic after deleting primary images."""

    def setUp(self):
        self.agent = _make_agent()
        self.prop = _make_property(self.agent)
        self.img1 = PropertyImage.objects.create(property=self.prop, image=_make_image('del1.jpg'))
        self.img2 = PropertyImage.objects.create(property=self.prop, image=_make_image('del2.jpg'))

    def test_primary_deletion_promotes_next_image(self):
        """Deleting the primary image promotes the next image to primary."""
        self.img1.refresh_from_db()
        self.assertTrue(self.img1.is_primary)
        self.img1.delete()
        self.img2.refresh_from_db()
        self.assertTrue(self.img2.is_primary, "img2 should be auto-promoted to primary after img1 deletion.")

    def test_all_images_deleted_clears_property_image(self):
        """When all gallery images are deleted, Property.image is cleared."""
        self.img1.delete()
        self.img2.delete()
        self.prop.refresh_from_db()
        # ImageField.name should be None or empty string after clearing
        self.assertFalse(
            self.prop.image.name,
            "Property.image.name should be empty or None when gallery is empty."
        )


@override_settings(
    MEDIA_ROOT='/tmp/test_media/',
    DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage',
)
class GalleryAJAXViewTest(TestCase):
    """Tests for the V3 AJAX gallery management endpoints."""

    def setUp(self):
        self.agent = _make_agent()
        self.prop = _make_property(self.agent)
        self.img1 = PropertyImage.objects.create(property=self.prop, image=_make_image('v1.jpg'))
        self.img2 = PropertyImage.objects.create(property=self.prop, image=_make_image('v2.jpg'))
        self.client = Client()
        self.client.login(username='agent1', password='agent1pass')

    def test_set_primary_ajax(self):
        """POST to set-primary endpoint returns success and updates is_primary."""
        url = reverse('gallery_image_set_primary', args=[self.img2.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.img2.refresh_from_db()
        self.assertTrue(self.img2.is_primary)

    def test_delete_ajax(self):
        """POST to delete endpoint removes the image from the database."""
        url = reverse('gallery_image_delete', args=[self.img2.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertFalse(PropertyImage.objects.filter(pk=self.img2.pk).exists())

    def test_unauthorized_delete_returns_403(self):
        """A non-owner cannot delete a gallery image."""
        other = User.objects.create_user(username='buyer1', password='buyer1pass')
        Profile.objects.get_or_create(user=other)
        self.client.login(username='buyer1', password='buyer1pass')
        url = reverse('gallery_image_delete', args=[self.img1.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)


# ── V4 Messaging System Tests ──────────────────────────────────────────────────

class MessagingSystemTest(TestCase):
    """Tests for the V4 internal messaging system (UI and API)."""

    def setUp(self):
        # Create users
        self.agent = User.objects.create_user(username='agent_m', password='password', email='agent@test.com')
        self.agent_profile, _ = Profile.objects.get_or_create(user=self.agent)
        self.agent_profile.role = Profile.Role.AGENT
        self.agent_profile.save()

        self.buyer = User.objects.create_user(username='buyer_m', password='password', email='buyer@test.com')
        self.buyer_profile, _ = Profile.objects.get_or_create(user=self.buyer)
        self.buyer_profile.role = Profile.Role.BUYER
        self.buyer_profile.save()

        self.other_user = User.objects.create_user(username='other_m', password='password')

        # Create property context
        self.prop = _make_property(self.agent)

        self.client = Client()

    def test_compose_message_flow(self):
        """A buyer can compose a message to an agent about a property."""
        self.client.login(username='buyer_m', password='password')
        url = reverse('compose_message') + f"?to={self.agent.username}&property_id={self.prop.pk}"
        
        # Test GET compose page load
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"To: {self.agent.username}")
        self.assertContains(response, self.prop.title)

        # Test POST message submit
        post_data = {
            'subject': 'Interested in Test Villa',
            'body': 'I would like to schedule a viewing.'
        }
        response = self.client.post(url, data=post_data)
        
        # Should redirect to thread view
        self.assertEqual(response.status_code, 302)
        
        # Verify message created in DB
        msg = Message.objects.filter(sender=self.buyer, receiver=self.agent).first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.subject, 'Interested in Test Villa')
        self.assertEqual(msg.property, self.prop)
        self.assertFalse(msg.is_read)

    def test_thread_details_and_read_status(self):
        """Viewing a thread displays messages and marks received ones as read."""
        msg = Message.objects.create(
            sender=self.buyer,
            receiver=self.agent,
            property=self.prop,
            subject='Question',
            body='Hello Agent.'
        )
        self.assertFalse(msg.is_read)

        # Viewing thread as buyer (sender) doesn't mark it read for agent
        self.client.login(username='buyer_m', password='password')
        url = reverse('thread_view', args=[msg.pk])
        self.client.get(url)
        msg.refresh_from_db()
        self.assertFalse(msg.is_read)

        # Viewing thread as agent (receiver) marks the message as read
        self.client.login(username='agent_m', password='password')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hello Agent.')
        
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)

    def test_unauthorized_thread_access(self):
        """A user cannot access a thread they are not part of."""
        msg = Message.objects.create(
            sender=self.buyer,
            receiver=self.agent,
            subject='Private convo',
            body='Secret info.'
        )
        self.client.login(username='other_m', password='password')
        url = reverse('thread_view', args=[msg.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # redirects with error message

    def test_reply_flow(self):
        """A user can reply to a message thread."""
        msg = Message.objects.create(
            sender=self.buyer,
            receiver=self.agent,
            subject='Greeting',
            body='Hello agent.'
        )

        self.client.login(username='agent_m', password='password')
        url = reverse('message_reply', args=[msg.pk])
        response = self.client.post(url, data={'body': 'Hello back, buyer!'})
        
        self.assertEqual(response.status_code, 302)
        
        # Verify reply was created
        reply = Message.objects.filter(parent=msg).first()
        self.assertIsNotNone(reply)
        self.assertEqual(reply.sender, self.agent)
        self.assertEqual(reply.receiver, self.buyer)
        self.assertEqual(reply.body, 'Hello back, buyer!')
        self.assertEqual(reply.subject, 'Re: Greeting')

    # API Tests
    def test_api_inbox_and_unread_count(self):
        """Tests DRF inbox and unread counts."""
        self.client.login(username='agent_m', password='password')
        
        # No messages initially
        res = self.client.get(reverse('api_unread_count'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['unread_count'], 0)

        # Create unread message
        Message.objects.create(
            sender=self.buyer,
            receiver=self.agent,
            subject='API Msg',
            body='Hello via API'
        )

        # Unread count should be 1
        res = self.client.get(reverse('api_unread_count'))
        self.assertEqual(res.json()['unread_count'], 1)

        # Inbox API check
        inbox_res = self.client.get(reverse('api_inbox'))
        self.assertEqual(inbox_res.status_code, 200)
        self.assertEqual(len(inbox_res.json()['results']), 1)
        self.assertEqual(inbox_res.json()['results'][0]['subject'], 'API Msg')

    def test_api_compose_message(self):
        """Tests sending a message via the REST API compose endpoint."""
        self.client.login(username='buyer_m', password='password')
        post_data = {
            'receiver_username': self.agent.username,
            'property_id': self.prop.pk,
            'subject': 'API Inquiry',
            'body': 'Inquiring via API.'
        }
        res = self.client.post(reverse('api_compose'), data=post_data, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        
        # Verify creation in DB
        msg = Message.objects.filter(subject='API Inquiry').first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.sender, self.buyer)
        self.assertEqual(msg.receiver, self.agent)


# ── V1 Property Catalog & Auth Tests ─────────────────────────────────────────

class V1PropertyCatalogAuthTest(TestCase):
    """Tests for V1 Property Catalog, Roles (Agent/Buyer), M2M Amenities, and Auth."""

    def setUp(self):
        self.client = Client()

    def test_registration_as_buyer(self):
        """User can register with Buyer role."""
        url = reverse('register')
        data = {
            'username': 'newbuyer',
            'email': 'buyer@example.com',
            'role': Profile.Role.BUYER,
            'password1': 'SecretPass123!',
            'password2': 'SecretPass123!',
        }
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, 302)
        user = User.objects.filter(username='newbuyer').first()
        self.assertIsNotNone(user)
        self.assertTrue(user.profile.is_buyer)
        self.assertFalse(user.profile.is_agent)

    def test_registration_as_agent(self):
        """User can register with Agent role and agency name."""
        url = reverse('register')
        data = {
            'username': 'newagent',
            'email': 'agent@example.com',
            'role': Profile.Role.AGENT,
            'phone': '+91 98765 43210',
            'agency_name': 'Premier Properties',
            'password1': 'SecretPass123!',
            'password2': 'SecretPass123!',
        }
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, 302)
        user = User.objects.filter(username='newagent').first()
        self.assertIsNotNone(user)
        self.assertTrue(user.profile.is_agent)
        self.assertEqual(user.profile.agency_name, 'Premier Properties')

    def test_login_and_logout_flow(self):
        """User can log in and log out."""
        user = User.objects.create_user(username='loginuser', password='MyPassword123!', email='u@test.com')
        Profile.objects.get_or_create(user=user)

        # Login
        login_res = self.client.post(reverse('login'), {'username': 'loginuser', 'password': 'MyPassword123!'})
        self.assertEqual(login_res.status_code, 302)

        # Logout
        logout_res = self.client.get(reverse('logout'))
        self.assertEqual(logout_res.status_code, 302)

    def test_property_amenity_through_table(self):
        """Property <-> Amenity M2M relationship via PropertyAmenity linking table."""
        agent = _make_agent()
        prop = _make_property(agent)
        amenity = Amenity.objects.create(name="Swimming Pool", icon="fa-solid fa-water-ladder")

        # Explicit through table creation
        link = PropertyAmenity.objects.create(property=prop, amenity=amenity)
        self.assertEqual(link.property, prop)
        self.assertEqual(link.amenity, amenity)

        # Verification through M2M descriptors
        self.assertIn(amenity, prop.amenities.all())
        self.assertIn(prop, amenity.properties.all())

    def test_buyer_forbidden_from_property_create(self):
        """A Buyer cannot access property_create view and is redirected."""
        buyer = User.objects.create_user(username='buyer_only', password='password')
        Profile.objects.get_or_create(user=buyer, defaults={'role': Profile.Role.BUYER})
        self.client.login(username='buyer_only', password='password')

        response = self.client.get(reverse('property_create'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('property_list'))


# ── V2 Advanced Search API Tests ─────────────────────────────────────────────

class V2AdvancedSearchAPITest(TestCase):
    """Tests for V2 Advanced Search API endpoints, complex ORM filters & geolocation."""

    def setUp(self):
        self.client = Client()
        self.agent = _make_agent()

        # Create amenities
        self.wifi = Amenity.objects.create(name="WiFi", icon="fa-solid fa-wifi")
        self.pool = Amenity.objects.create(name="Pool", icon="fa-solid fa-water-ladder")
        self.gym = Amenity.objects.create(name="Gym", icon="fa-solid fa-dumbbell")

        # Property A in South Mumbai (lat 18.9438, lng 72.8232)
        self.prop_a = Property.objects.create(
            title='South Mumbai Luxury Apartment',
            description='Near marine drive',
            agent=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            listing_type=Property.ListingType.SALE,
            status=Property.Status.AVAILABLE,
            price=5000000,
            area_sqft=1200,
            bedrooms=2,
            bathrooms=2,
            city='Mumbai',
            state='Maharashtra',
            latitude=18.9438,
            longitude=72.8232,
        )
        self.prop_a.amenities.set([self.wifi, self.pool])

        # Property B in Pune (lat 18.5204, lng 73.8567) - approx 120km from Mumbai
        self.prop_b = Property.objects.create(
            title='Pune Modern Villa',
            description='Spacious villa in Kothrud',
            agent=self.agent,
            property_type=Property.PropertyType.VILLA,
            listing_type=Property.ListingType.SALE,
            status=Property.Status.AVAILABLE,
            price=8000000,
            area_sqft=2200,
            bedrooms=3,
            bathrooms=3,
            city='Pune',
            state='Maharashtra',
            latitude=18.5204,
            longitude=73.8567,
        )
        self.prop_b.amenities.set([self.wifi])

        # Property C in Mumbai Suburb (lat 19.0760, lng 72.8777)
        self.prop_c = Property.objects.create(
            title='Bandra Sea View Penthouse',
            description='Penthouse near Bandstand',
            agent=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            listing_type=Property.ListingType.RENT,
            status=Property.Status.AVAILABLE,
            price=150000,
            area_sqft=3000,
            bedrooms=4,
            bathrooms=4,
            city='Mumbai',
            state='Maharashtra',
            latitude=19.0760,
            longitude=72.8777,
        )
        self.prop_c.amenities.set([self.pool, self.gym])

    def test_search_price_range(self):
        """Filter by price range."""
        url = reverse('api_property_search') + '?min_price=4000000&max_price=6000000'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        results = res.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.prop_a.id)

    def test_search_bedroom_and_area(self):
        """Filter by minimum bedrooms and area."""
        url = reverse('api_property_search') + '?bedrooms=3&min_area=2000'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        ids = [p['id'] for p in res.json()['results']]
        self.assertIn(self.prop_b.id, ids)
        self.assertIn(self.prop_c.id, ids)
        self.assertNotIn(self.prop_a.id, ids)

    def test_conjoined_amenities_filter(self):
        """Property must have ALL requested amenities (conjoined AND logic)."""
        # Search for Pool AND WiFi: only prop_a has both
        url = reverse('api_property_search') + f'?amenities={self.pool.id}&amenities={self.wifi.id}'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        results = res.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.prop_a.id)

    def test_geolocation_proximity_radius_search(self):
        """Filter by latitude, longitude, and radius in km."""
        # Query near South Mumbai (18.94, 72.82) within 15 km
        url = reverse('api_property_search') + '?lat=18.94&lng=72.82&radius_km=15'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        ids = [p['id'] for p in res.json()['results']]
        self.assertIn(self.prop_a.id, ids)
        self.assertNotIn(self.prop_b.id, ids)  # Pune is ~120km away

    def test_search_suggestions_endpoint(self):
        """Suggestions endpoint provides distinct cities, price range, and choices."""
        res = self.client.get(reverse('api_search_suggestions'))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('Mumbai', data['cities'])
        self.assertIn('Pune', data['cities'])
        self.assertIn('price_range', data)

    def test_property_stats_endpoint(self):
        """Stats endpoint provides aggregate property metrics."""
        res = self.client.get(reverse('api_property_stats'))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(data['total_properties'], 3)
        self.assertIn('price_stats', data)


# ── V5 Bulk Upload & Saved Search Alerts Tests ───────────────────────────────

class V5BulkUploadAndAlertsTest(TestCase):
    """Tests for V5 CSV Bulk Upload and Saved Search Email Alerts."""

    def setUp(self):
        self.client = Client()
        self.agent = _make_agent()
        self.buyer = User.objects.create_user(username='buyer_alert', password='password', email='buyer_alert@example.com')
        Profile.objects.get_or_create(user=self.buyer, defaults={'role': Profile.Role.BUYER})

    def test_bulk_upload_sample_csv_download(self):
        """Agent can download a sample CSV template."""
        self.client.login(username='agent1', password='agent1pass')
        res = self.client.get(reverse('bulk_upload_sample_csv'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename=', res['Content-Disposition'])

    def test_bulk_upload_valid_csv(self):
        """Agent can successfully upload properties via CSV."""
        self.client.login(username='agent1', password='agent1pass')
        csv_content = (
            "title,description,property_type,listing_type,price,area_sqft,bedrooms,bathrooms,city,state,amenities\n"
            "Bulk Villa Alpha,A great villa,VILLA,SALE,12000000,2800,4,3,Jaipur,Rajasthan,\"Garden, Parking\"\n"
            "Bulk Apt Beta,A modern flat,APARTMENT,RENT,35000,1100,2,2,Jaipur,Rajasthan,WiFi\n"
        )
        csv_file = SimpleUploadedFile("properties.csv", csv_content.encode('utf-8'), content_type="text/csv")
        res = self.client.post(reverse('bulk_upload'), {'csv_file': csv_file})
        self.assertEqual(res.status_code, 302)

        # Check properties created
        self.assertTrue(Property.objects.filter(title="Bulk Villa Alpha").exists())
        self.assertTrue(Property.objects.filter(title="Bulk Apt Beta").exists())
        villa = Property.objects.get(title="Bulk Villa Alpha")
        self.assertEqual(villa.bedrooms, 4)
        self.assertTrue(villa.amenities.filter(name="Garden").exists())

    def test_bulk_upload_invalid_csv_rolls_back(self):
        """If one row is invalid, the entire upload is rolled back atomically."""
        self.client.login(username='agent1', password='agent1pass')
        csv_content = (
            "title,description,property_type,listing_type,price,area_sqft,city,state\n"
            "Valid Prop,Good prop,HOUSE,SALE,5000000,1500,Delhi,Delhi\n"
            "Invalid Prop,Bad price,HOUSE,SALE,-9999,1500,Delhi,Delhi\n"  # Invalid negative price
        )
        csv_file = SimpleUploadedFile("bad_props.csv", csv_content.encode('utf-8'), content_type="text/csv")
        res = self.client.post(reverse('bulk_upload'), {'csv_file': csv_file})
        self.assertEqual(res.status_code, 200)  # Form redisplayed with errors

        # Ensure atomicity: Valid Prop must NOT have been saved
        self.assertFalse(Property.objects.filter(title="Valid Prop").exists())

    def test_saved_search_creation_via_api(self):
        """Buyer can create a saved search via API."""
        self.client.login(username='buyer_alert', password='password')
        amenity = Amenity.objects.create(name="Central AC")
        payload = {
            'name': 'Luxury Delhi Houses',
            'city': 'Delhi',
            'property_type': 'HOUSE',
            'min_price': 5000000,
            'max_price': 20000000,
            'amenities': [amenity.name]
        }
        res = self.client.post(reverse('api_saved_searches'), data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        search = SavedSearch.objects.filter(name='Luxury Delhi Houses').first()
        self.assertIsNotNone(search)
        self.assertEqual(search.buyer, self.buyer)
        self.assertTrue(search.amenities.filter(name="Central AC").exists())

    def test_send_alerts_command_dispatches_email_and_messages(self):
        """Background send_alerts command notifies buyers of new matching listings."""
        # Create a saved search for Buyer in Delhi
        search = SavedSearch.objects.create(
            buyer=self.buyer,
            name='Affordable Delhi Rent',
            city='Delhi',
            listing_type='RENT',
            max_price=40000,
            last_notified_at=timezone.now() - timedelta(days=1)
        )

        # Create a matching property listed just now
        prop = Property.objects.create(
            title='Delhi 2BHK Near Metro',
            description='Cozy 2BHK',
            agent=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            listing_type=Property.ListingType.RENT,
            status=Property.Status.AVAILABLE,
            price=25000,
            area_sqft=900,
            bedrooms=2,
            bathrooms=2,
            city='Delhi',
            state='Delhi',
        )

        # Clear any signal-generated messages and mailbox
        Message.objects.filter(receiver=self.buyer).delete()
        mail.outbox = []

        # Explicitly set last_notified_at to the past so the background job picks up recent property
        search.last_notified_at = timezone.now() - timedelta(days=1)
        search.save(update_fields=['last_notified_at'])

        # Run background job command
        call_command('send_alerts')

        # 1. Verify internal message created
        msg = Message.objects.filter(receiver=self.buyer, property=prop).first()
        self.assertIsNotNone(msg, "Internal alert message should be created.")
        self.assertIn("Affordable Delhi Rent", msg.subject)

        # 2. Verify email alert dispatched to buyer's email
        self.assertEqual(len(mail.outbox), 1, "An email alert should be sent to the buyer.")
        self.assertEqual(mail.outbox[0].to, ['buyer_alert@example.com'])
        self.assertIn("Delhi 2BHK Near Metro", mail.outbox[0].body)
