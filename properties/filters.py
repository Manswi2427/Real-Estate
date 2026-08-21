"""
Advanced PropertyFilter using django-filter (V2 – Advanced Search).

Supports filtering by price range (₹), area, bedrooms, bathrooms,
property/listing type, status, city, state, amenities, and keyword search.
"""

import django_filters
from django.db.models import Q

from .models import Amenity, Property


class PropertyFilter(django_filters.FilterSet):
    """
    Robust filter-set for the Property search API.

    Query Parameters
    ────────────────
    keyword      – searches title, description, address, city, state
    min_price    – price >= value (₹)
    max_price    – price <= value (₹)
    min_area     – area_sqft >= value
    max_area     – area_sqft <= value
    bedrooms     – bedrooms >= value
    bathrooms    – bathrooms >= value
    property_type – exact match (APARTMENT, HOUSE, VILLA, PLOT, COMMERCIAL)
    listing_type  – exact match (SALE, RENT)
    status        – exact match (AVAILABLE, SOLD, RENTED, PENDING)
    city          – case-insensitive contains
    state         – case-insensitive contains
    amenities     – comma-separated IDs (AND logic: property must have ALL)
    is_featured   – true / false
    sort          – ordering field(s)
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
