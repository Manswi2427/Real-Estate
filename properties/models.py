from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone


class Profile(models.Model):
    """Extends the built-in User model with a role (Agent / Buyer)."""

    class Role(models.TextChoices):
        AGENT = 'AGENT', 'Agent'
        BUYER = 'BUYER', 'Buyer'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile'
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.BUYER)
    phone = models.CharField(max_length=20, blank=True)
    agency_name = models.CharField(max_length=150, blank=True, help_text="Agents only")

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_agent(self):
        return self.role == self.Role.AGENT

    @property
    def is_buyer(self):
        return self.role == self.Role.BUYER


class Amenity(models.Model):
    """A feature/amenity that can belong to many properties (M2M)."""

    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(
        max_length=50,
        default='fa-solid fa-circle-check',
        help_text="Font Awesome icon class, e.g. fa-solid fa-swimming-pool",
    )
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = 'Amenities'
        ordering = ['name']

    def __str__(self):
        return self.name


class Property(models.Model):
    """A real-estate listing. Linked to Amenity via PropertyAmenity (M2M through)."""

    class PropertyType(models.TextChoices):
        APARTMENT = 'APARTMENT', 'Apartment'
        HOUSE = 'HOUSE', 'House'
        VILLA = 'VILLA', 'Villa'
        PLOT = 'PLOT', 'Plot / Land'
        COMMERCIAL = 'COMMERCIAL', 'Commercial'

    class ListingType(models.TextChoices):
        SALE = 'SALE', 'For Sale'
        RENT = 'RENT', 'For Rent'

    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        SOLD = 'SOLD', 'Sold'
        RENTED = 'RENTED', 'Rented'
        PENDING = 'PENDING', 'Pending'

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='properties',
        limit_choices_to={'profile__role': 'AGENT'},
    )

    property_type = models.CharField(max_length=20, choices=PropertyType.choices)
    listing_type = models.CharField(max_length=10, choices=ListingType.choices, default=ListingType.SALE)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AVAILABLE)

    price = models.DecimalField(max_digits=14, decimal_places=2)
    area_sqft = models.DecimalField(max_digits=10, decimal_places=2, help_text="Area in sq. ft.")
    bedrooms = models.PositiveSmallIntegerField(default=0)
    bathrooms = models.PositiveSmallIntegerField(default=0)

    # Address / geolocation attributes
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=100, db_index=True)
    zipcode = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    image = models.ImageField(upload_to='property_images/', blank=True, null=True)

    amenities = models.ManyToManyField(
        Amenity, through='PropertyAmenity', related_name='properties', blank=True
    )

    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Properties'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['city', 'property_type', 'listing_type']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Property.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('property_detail', kwargs={'slug': self.slug})

    @property
    def has_geolocation(self):
        return self.latitude is not None and self.longitude is not None


class PropertyAmenity(models.Model):
    """Explicit linking (through) table between Property and Amenity."""

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_amenities')
    amenity = models.ForeignKey(Amenity, on_delete=models.CASCADE, related_name='amenity_properties')
    added_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('property', 'amenity')
        verbose_name_plural = 'Property Amenities'

    def __str__(self):
        return f"{self.property.title} - {self.amenity.name}"


class PropertyImage(models.Model):
    """
    V3 – Media Gallery: Stores multiple images for a single Property.
    One image is designated as the 'primary' thumbnail; the rest are gallery items.
    """

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='images',
    )
    image = models.ImageField(upload_to='property_images/gallery/')
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(
        default=False,
        help_text='Designate this image as the primary thumbnail shown in listings.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Property Image'
        verbose_name_plural = 'Property Images'
        ordering = ['-is_primary', 'created_at']

    def __str__(self):
        flag = ' [PRIMARY]' if self.is_primary else ''
        return f"{self.property.title} – Image #{self.pk}{flag}"

    def save(self, *args, **kwargs):
        """
        If this image is being set as primary:
          1. Unset is_primary on all other images of this property.
          2. Sync the parent Property.image to point to this image file.
        If no primary image exists yet, auto-promote the first image saved.
        """
        is_new = self.pk is None
        if self.is_primary:
            # Unset other primary images for this property (only when we have a pk to exclude)
            if not is_new:
                PropertyImage.objects.filter(
                    property=self.property, is_primary=True
                ).exclude(pk=self.pk).update(is_primary=False)

        super().save(*args, **kwargs)

        if self.is_primary:
            # Also handle unset when brand-new (saved, so pk now exists)
            PropertyImage.objects.filter(
                property=self.property, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
            # Sync parent Property.image to this image
            Property.objects.filter(pk=self.property_id).update(image=self.image.name)

        elif is_new:
            # If this is the first image on the property, auto-promote it
            if not PropertyImage.objects.filter(
                property=self.property, is_primary=True
            ).exclude(pk=self.pk).exists():
                self.is_primary = True
                PropertyImage.objects.filter(
                    property=self.property, is_primary=True
                ).exclude(pk=self.pk).update(is_primary=False)
                PropertyImage.objects.filter(pk=self.pk).update(is_primary=True)
                Property.objects.filter(pk=self.property_id).update(image=self.image.name)

    def make_primary(self):
        """Public helper to set this image as primary and sync everything."""
        PropertyImage.objects.filter(
            property=self.property, is_primary=True
        ).update(is_primary=False)
        self.is_primary = True
        self.save(update_fields=['is_primary'])
        Property.objects.filter(pk=self.property_id).update(image=self.image.name)


# ─────────────────────────────────────────────────────────────────────────────
# V4 – Messaging System
# ─────────────────────────────────────────────────────────────────────────────

class Message(models.Model):
    """
    Internal messaging between users (Buyer ↔ Agent).

    Schema
    ──────
    sender   : FK(User)            – who sent the message
    receiver : FK(User)            – who receives it
    property : FK(Property, null)  – PropertyContext (optional)
    subject  : CharField           – thread subject / title
    body     : TextField           – message body
    parent   : FK('self', null)    – reply threading
    is_read  : BooleanField        – unread tracking
    sent_at  : DateTimeField       – timestamp
    """

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_messages',
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
        help_text='Optional property context for this message.',
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
        help_text='Parent message for reply threading.',
    )
    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['receiver', 'is_read']),
            models.Index(fields=['sender', 'sent_at']),
        ]

    def __str__(self):
        return f"[{self.sent_at:%d %b %Y}] {self.sender} → {self.receiver}: {self.subject[:40]}"

    def get_thread_root(self):
        """Walk up the parent chain to return the root message."""
        msg = self
        while msg.parent_id is not None:
            msg = msg.parent
        return msg

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            Message.objects.filter(pk=self.pk).update(is_read=True)


# ─────────────────────────────────────────────────────────────────────────────
# V5 – Saved Searches & Alerts
# ─────────────────────────────────────────────────────────────────────────────

class SavedSearch(models.Model):
    """
    Stores search filter criteria saved by a Buyer user.
    Used to match new property listings and notify them via alerts.
    """

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_searches',
    )
    name = models.CharField(max_length=150, help_text="A friendly name for this saved search.")

    # Filter criteria
    keyword = models.CharField(max_length=200, blank=True)
    property_type = models.CharField(max_length=20, blank=True)
    listing_type = models.CharField(max_length=10, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    
    min_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    max_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    
    min_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    bedrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    bathrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    
    amenities = models.ManyToManyField(Amenity, blank=True, related_name='saved_searches')

    created_at = models.DateTimeField(auto_now_add=True)
    last_notified_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Saved Search'
        verbose_name_plural = 'Saved Searches'

    def __str__(self):
        return f"{self.buyer.username} – {self.name}"

    def matches_property(self, prop):
        """
        Evaluate if a Property instance matches the search criteria.
        """
        # Keyword search
        if self.keyword:
            kw = self.keyword.lower()
            in_title = kw in prop.title.lower()
            in_desc = kw in prop.description.lower()
            in_addr = kw in prop.address.lower()
            in_city = kw in prop.city.lower()
            in_state = kw in prop.state.lower()
            if not (in_title or in_desc or in_addr or in_city or in_state):
                return False

        # Property type, listing type
        if self.property_type and prop.property_type != self.property_type:
            return False
        if self.listing_type and prop.listing_type != self.listing_type:
            return False

        # City / State (case-insensitive contains / match)
        if self.city and self.city.lower() not in prop.city.lower():
            return False
        if self.state and self.state.lower() not in prop.state.lower():
            return False

        # Price limits
        if self.min_price is not None and prop.price < self.min_price:
            return False
        if self.max_price is not None and prop.price > self.max_price:
            return False

        # Area limits
        if self.min_area is not None and prop.area_sqft < self.min_area:
            return False
        if self.max_area is not None and prop.area_sqft > self.max_area:
            return False

        # Room minimum counts
        if self.bedrooms is not None and prop.bedrooms < self.bedrooms:
            return False
        if self.bathrooms is not None and prop.bathrooms < self.bathrooms:
            return False

        # Amenity checks: property must have ALL the selected amenities in the search criteria
        if self.pk:
            search_amenity_ids = set(self.amenities.values_list('id', flat=True))
            if search_amenity_ids:
                prop_amenity_ids = set(prop.amenities.values_list('id', flat=True))
                if not search_amenity_ids.issubset(prop_amenity_ids):
                    return False

        return True


