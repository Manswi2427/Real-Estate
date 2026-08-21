"""
DRF Serializers for the Property API (V2 – Advanced Search).
All prices are in Indian Rupees (₹).
"""

from rest_framework import serializers

from .models import Amenity, Property, PropertyAmenity


class AmenitySerializer(serializers.ModelSerializer):
    """Compact amenity representation."""

    class Meta:
        model = Amenity
        fields = ['id', 'name', 'icon', 'description']


class PropertyListSerializer(serializers.ModelSerializer):
    """
    Compact serializer used in search results / list views.
    Includes formatted ₹ price and nested amenities.
    """

    property_type_display = serializers.CharField(
        source='get_property_type_display', read_only=True
    )
    listing_type_display = serializers.CharField(
        source='get_listing_type_display', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )
    amenities = AmenitySerializer(many=True, read_only=True)
    agent_name = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    price_display = serializers.SerializerMethodField()
    price_label = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            'id', 'title', 'slug',
            'property_type', 'property_type_display',
            'listing_type', 'listing_type_display',
            'status', 'status_display',
            'price', 'price_display', 'price_label',
            'area_sqft', 'bedrooms', 'bathrooms',
            'city', 'state', 'address',
            'image_url', 'amenities',
            'agent_name', 'url',
            'is_featured', 'created_at',
        ]

    # ---- helpers ----

    @staticmethod
    def _format_inr(value):
        """Format a number in Indian numbering (₹ 12,34,567)."""
        try:
            value = int(value)
        except (TypeError, ValueError):
            return str(value)
        is_negative = value < 0
        value = abs(value)
        s = str(value)
        if len(s) <= 3:
            result = s
        else:
            last3 = s[-3:]
            rest = s[:-3]
            groups = []
            while rest:
                groups.insert(0, rest[-2:])
                rest = rest[:-2]
            result = ','.join(groups) + ',' + last3
        return f"-₹{result}" if is_negative else f"₹{result}"

    @staticmethod
    def _price_label(value):
        """Return human-readable label like '₹25 Lakh' or '₹1.2 Cr'."""
        try:
            value = float(value)
        except (TypeError, ValueError):
            return str(value)
        if value >= 1_00_00_000:  # 1 Crore
            cr = value / 1_00_00_000
            return f"₹{cr:.2f} Cr" if cr != int(cr) else f"₹{int(cr)} Cr"
        elif value >= 1_00_000:  # 1 Lakh
            lk = value / 1_00_000
            return f"₹{lk:.2f} Lakh" if lk != int(lk) else f"₹{int(lk)} Lakh"
        else:
            return PropertyListSerializer._format_inr(value)

    def get_agent_name(self, obj):
        full = obj.agent.get_full_name()
        return full if full.strip() else obj.agent.username

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url'):
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        # Stable fallback based on id
        fallbacks = [
            "https://images.unsplash.com/photo-1568605114967-8130f3a36994?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1613977257363-707ba9348227?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80",
        ]
        return fallbacks[(obj.id or 0) % len(fallbacks)]

    def get_url(self, obj):
        return obj.get_absolute_url()

    def get_price_display(self, obj):
        return self._format_inr(obj.price)

    def get_price_label(self, obj):
        return self._price_label(obj.price)


class PropertyDetailSerializer(PropertyListSerializer):
    """
    Full-detail serializer with all fields including geolocation,
    agent profile info, and complete description.
    """

    agent_detail = serializers.SerializerMethodField()

    class Meta(PropertyListSerializer.Meta):
        fields = PropertyListSerializer.Meta.fields + [
            'description', 'zipcode',
            'latitude', 'longitude',
            'agent_detail', 'updated_at',
        ]

    def get_agent_detail(self, obj):
        profile = getattr(obj.agent, 'profile', None)
        return {
            'username': obj.agent.username,
            'full_name': obj.agent.get_full_name() or obj.agent.username,
            'email': obj.agent.email,
            'phone': profile.phone if profile else '',
            'agency_name': profile.agency_name if profile else '',
            'role': profile.get_role_display() if profile else 'Agent',
        }
