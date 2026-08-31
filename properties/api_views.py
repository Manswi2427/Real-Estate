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
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django_filters.rest_framework import DjangoFilterBackend

from .filters import PropertyFilter
from .models import Amenity, Message, Property, SavedSearch
from .serializers import (
    AmenitySerializer,
    MessageSerializer,
    PropertyDetailSerializer,
    PropertyListSerializer,
    SavedSearchSerializer,
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


# ─────────────────────────────────────────────────────────────────────────────
# V4 – Messaging API Views
# ─────────────────────────────────────────────────────────────────────────────

class InboxAPIView(generics.ListAPIView):
    """
    GET /api/messages/inbox/
    Returns the authenticated user's received messages, newest first.
    Requires authentication.
    """
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Message.objects
            .filter(receiver=self.request.user)
            .select_related('sender', 'receiver', 'property')
            .order_by('-sent_at')
        )


class ComposeAPIView(generics.CreateAPIView):
    """
    POST /api/messages/compose/
    Send a new message.
    Body: { receiver_username, property_id (optional), subject, body }
    """
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        from django.contrib.auth.models import User
        receiver_username = request.data.get('receiver_username')
        try:
            receiver = User.objects.get(username=receiver_username)
        except User.DoesNotExist:
            return Response({'error': 'Receiver not found.'}, status=status.HTTP_400_BAD_REQUEST)

        if receiver == request.user:
            return Response({'error': 'Cannot message yourself.'}, status=status.HTTP_400_BAD_REQUEST)

        property_obj = None
        property_id = request.data.get('property_id')
        if property_id:
            try:
                property_obj = Property.objects.get(pk=property_id)
            except Property.DoesNotExist:
                pass

        msg = Message.objects.create(
            sender=request.user,
            receiver=receiver,
            property=property_obj,
            subject=request.data.get('subject', ''),
            body=request.data.get('body', ''),
        )
        return Response(MessageSerializer(msg, context={'request': request}).data, status=status.HTTP_201_CREATED)


class ThreadAPIView(generics.RetrieveAPIView):
    """
    GET /api/messages/<pk>/
    Returns full thread: root message + all replies.
    Marks all unread messages in thread as read.
    """
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Q
        return Message.objects.filter(
            Q(sender=self.request.user) | Q(receiver=self.request.user)
        ).select_related('sender', 'receiver', 'property')

    def retrieve(self, request, *args, **kwargs):
        from django.db.models import Q
        root = self.get_object()
        replies = root.replies.select_related('sender', 'receiver').order_by('sent_at')
        # Mark unread
        Message.objects.filter(
            Q(pk=root.pk) | Q(parent=root),
            receiver=request.user,
            is_read=False,
        ).update(is_read=True)
        data = {
            'root': MessageSerializer(root, context={'request': request}).data,
            'replies': MessageSerializer(replies, many=True, context={'request': request}).data,
        }
        return Response(data)


class UnreadCountAPIView(APIView):
    """
    GET /api/messages/unread-count/
    Returns number of unread messages for the authenticated user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Message.objects.filter(receiver=request.user, is_read=False).count()
        return Response({'unread_count': count})


# V5 - Saved Searches

class SavedSearchListCreateAPIView(generics.ListCreateAPIView):
    """V5 - List and create saved searches for the authenticated user."""
    serializer_class = SavedSearchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SavedSearch.objects.filter(buyer=self.request.user)

    def perform_create(self, serializer):
        serializer.save(buyer=self.request.user)


class SavedSearchDestroyAPIView(generics.DestroyAPIView):
    """V5 - Delete a saved search for the authenticated user."""
    serializer_class = SavedSearchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SavedSearch.objects.filter(buyer=self.request.user)
