"""
Advanced PropertyFilter using django-filter (V2 - Advanced Search).

Supports filtering by price range (₹), area, bedrooms, bathrooms,
property/listing type, status, city, state, amenities, keyword search,
and geolocation proximity (lat, lng, radius_km).
"""

import math
import django_filters
from django.db.models import Q

from .models import Amenity, Property


def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points in km."""
    R = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(float(lat1)))
        * math.cos(math.radians(float(lat2)))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class PropertyFilter(django_filters.FilterSet):
    """
    Robust filter-set for the Property search API.

    Query Parameters
    ----------------
    keyword      - searches title, description, address, city, state
    min_price    - price >= value (₹)
    max_price    - price <= value (₹)
    min_area     - area_sqft >= value
    max_area     - area_sqft <= value
    bedrooms     - bedrooms >= value
    bathrooms    - bathrooms >= value
    property_type - exact match (APARTMENT, HOUSE, VILLA, PLOT, COMMERCIAL)
    listing_type  - exact match (SALE, RENT)
    status        - exact match (AVAILABLE, SOLD, RENTED, PENDING)
    city          - case-insensitive contains
    state         - case-insensitive contains
    amenities     - comma-separated IDs (AND logic: property must have ALL)
    is_featured   - true / false
    lat, lng, radius_km - geolocation proximity search
    sort          - ordering field(s)
    """

    keyword = django_filters.CharFilter(method='filter_keyword', label='Keyword')

    min_price = django_filters.NumberFilter(
        field_name='price', lookup_expr='gte', label='Min Price (₹)'
    )
    max_price = django_filters.NumberFilter(
        field_name='price', lookup_expr='lte', label='Max Price (₹)'
    )

    min_area = django_filters.NumberFilter(
        field_name='area_sqft', lookup_expr='gte', label='Min Area (sqft)'
    )
    max_area = django_filters.NumberFilter(
        field_name='area_sqft', lookup_expr='lte', label='Max Area (sqft)'
    )

    bedrooms = django_filters.NumberFilter(
        field_name='bedrooms', lookup_expr='gte', label='Min Bedrooms'
    )
    bathrooms = django_filters.NumberFilter(
        field_name='bathrooms', lookup_expr='gte', label='Min Bathrooms'
    )

    property_type = django_filters.ChoiceFilter(
        choices=Property.PropertyType.choices, label='Property Type'
    )
    listing_type = django_filters.ChoiceFilter(
        choices=Property.ListingType.choices, label='Listing Type'
    )
    status = django_filters.ChoiceFilter(
        choices=Property.Status.choices, label='Status'
    )

    city = django_filters.CharFilter(
        field_name='city', lookup_expr='icontains', label='City'
    )
    state = django_filters.CharFilter(
        field_name='state', lookup_expr='icontains', label='State'
    )

    amenities = django_filters.ModelMultipleChoiceFilter(
        queryset=Amenity.objects.all(),
        field_name='amenities',
        conjoined=True,   # AND logic: must have ALL selected amenities
        label='Amenities',
    )

    is_featured = django_filters.BooleanFilter(
        field_name='is_featured', label='Featured Only'
    )

    # Geolocation proximity filters
    lat = django_filters.NumberFilter(method='filter_geo_dummy', label='Latitude')
    lng = django_filters.NumberFilter(method='filter_geo_dummy', label='Longitude')
    radius_km = django_filters.NumberFilter(method='filter_geolocation', label='Radius (km)')

    sort = django_filters.OrderingFilter(
        fields=(
            ('price', 'price'),
            ('area_sqft', 'area_sqft'),
            ('created_at', 'created_at'),
            ('bedrooms', 'bedrooms'),
        ),
        field_labels={
            'price': 'Price',
            'area_sqft': 'Area',
            'created_at': 'Date Added',
            'bedrooms': 'Bedrooms',
        },
        label='Sort By',
    )

    class Meta:
        model = Property
        fields = []  # all filters declared explicitly above

    # ---- Custom filter methods ----

    def filter_keyword(self, queryset, name, value):
        """Full-text search across title, description, address, city, state."""
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value)
            | Q(description__icontains=value)
            | Q(address__icontains=value)
            | Q(city__icontains=value)
            | Q(state__icontains=value)
        )

    def filter_geo_dummy(self, queryset, name, value):
        """lat and lng are consumed by filter_geolocation."""
        return queryset

    def filter_geolocation(self, queryset, name, value):
        """Filter properties within radius_km of lat, lng."""
        if not value:
            return queryset
        try:
            radius = float(value)
            lat = float(self.data.get('lat', 0))
            lng = float(self.data.get('lng', 0))
        except (ValueError, TypeError):
            return queryset

        if lat == 0 and lng == 0:
            return queryset

        # Rough bounding box first for database efficiency
        delta_lat = radius / 111.0
        cos_lat = math.cos(math.radians(lat))
        delta_lng = radius / (111.0 * (cos_lat if abs(cos_lat) > 0.01 else 1.0))

        candidates = queryset.filter(
            latitude__isnull=False,
            longitude__isnull=False,
            latitude__gte=lat - delta_lat,
            latitude__lte=lat + delta_lat,
            longitude__gte=lng - delta_lng,
            longitude__lte=lng + delta_lng,
        )

        # Precise haversine filtering
        matching_ids = []
        for prop_id, prop_lat, prop_lng in candidates.values_list('id', 'latitude', 'longitude'):
            if prop_lat is not None and prop_lng is not None:
                dist = haversine_km(lat, lng, prop_lat, prop_lng)
                if dist <= radius:
                    matching_ids.append(prop_id)

        return queryset.filter(id__in=matching_ids)
