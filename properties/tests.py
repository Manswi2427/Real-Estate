"""
V3 – Media Gallery Unit Tests
Tests the PropertyImage model behaviour:
  - creation and auto-promotion logic
  - primary designation and sync to Property.image
  - primary deletion triggers election of next image
"""

import io

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.test import Client
from django.urls import reverse

from .models import Amenity, Message, Profile, Property, PropertyImage


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
