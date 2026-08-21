"""
REST API views for V2 – Advanced Search.

Endpoints
─────────
GET /api/properties/search/       – Paginated, filtered property list
GET /api/properties/<slug>/       – Full property detail
GET /api/amenities/               – All amenities (for filter UI)
GET /api/properties/suggestions/  – Distinct cities, states, price range
GET /api/properties/stats/        – Quick aggregate stats
"""

from django.db.models import Avg, Count, Max, Min

from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from django_filters.rest_framework import DjangoFilterBackend

from .filters import PropertyFilter
from .models import Amenity, Property
from .serializers import (
    AmenitySerializer,
    PropertyDetailSerializer,
    PropertyListSerializer,
)


# ─── Pagination ────────────────────────────────────────────────

class PropertyPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 50


# ─── Property Search ──────────────────────────────────────────

class PropertySearchAPIView(generics.ListAPIView):
    """
    Advanced property search with robust filtering.

    All prices in Indian Rupees (₹).

    Filters: keyword, min_price, max_price, min_area, max_area,
             bedrooms, bathrooms, property_type, listing_type,
             status, city, state, amenities, is_featured, sort
    """

    serializer_class = PropertyListSerializer
    pagination_class = PropertyPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = PropertyFilter

    def get_queryset(self):
        return (
            Property.objects
            .select_related('agent', 'agent__profile')
            .prefetch_related('amenities')
            .order_by('-created_at')
        )


# ─── Property Detail ──────────────────────────────────────────

class PropertyDetailAPIView(generics.RetrieveAPIView):
    """Full property detail by slug."""

    serializer_class = PropertyDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return (
            Property.objects
            .select_related('agent', 'agent__profile')
            .prefetch_related('amenities')
        )


# ─── Amenity List ─────────────────────────────────────────────

class AmenityListAPIView(generics.ListAPIView):
    """Return all amenities (used to populate filter checkboxes)."""

    serializer_class = AmenitySerializer
    queryset = Amenity.objects.all().order_by('name')
    pagination_class = None  # return all in one response


# ─── Search Suggestions ──────────────────────────────────────

class SearchSuggestionsAPIView(APIView):
    """
    Provide dynamic data for building the search UI:
      - distinct cities & states
      - available property types & listing types
      - min/max price in the database
      - bedroom counts available
    """

    def get(self, request):
        qs = Property.objects.filter(status=Property.Status.AVAILABLE)

        cities = sorted(
            qs.values_list('city', flat=True).distinct()
        )
        states = sorted(
            qs.values_list('state', flat=True).distinct()
        )
        price_range = qs.aggregate(
            min_price=Min('price'),
            max_price=Max('price'),
        )
        area_range = qs.aggregate(
            min_area=Min('area_sqft'),
            max_area=Max('area_sqft'),
        )
        bedroom_counts = sorted(
            qs.values_list('bedrooms', flat=True).distinct()
        )
        bathroom_counts = sorted(
            qs.values_list('bathrooms', flat=True).distinct()
        )

        return Response({
            'cities': cities,
            'states': states,
            'property_types': [
                {'value': c[0], 'label': c[1]}
                for c in Property.PropertyType.choices
            ],
            'listing_types': [
                {'value': c[0], 'label': c[1]}
                for c in Property.ListingType.choices
            ],
            'price_range': {
                'min': float(price_range['min_price'] or 0),
                'max': float(price_range['max_price'] or 0),
            },
            'area_range': {
                'min': float(area_range['min_area'] or 0),
                'max': float(area_range['max_area'] or 0),
            },
            'bedroom_counts': bedroom_counts,
            'bathroom_counts': bathroom_counts,
        })


# ─── Quick Stats ──────────────────────────────────────────────

class PropertyStatsAPIView(APIView):
    """Quick aggregate stats for dashboard / hero section."""

    def get(self, request):
        all_props = Property.objects.all()
        available = all_props.filter(status=Property.Status.AVAILABLE)

        price_stats = available.aggregate(
            min_price=Min('price'),
            max_price=Max('price'),
            avg_price=Avg('price'),
        )

        return Response({
            'total_properties': all_props.count(),
            'total_available': available.count(),
            'total_cities': all_props.values('city').distinct().count(),
            'total_agents': all_props.values('agent').distinct().count(),
            'price_stats': {
                'min': float(price_stats['min_price'] or 0),
                'max': float(price_stats['max_price'] or 0),
                'avg': round(float(price_stats['avg_price'] or 0), 2),
            },
        })
