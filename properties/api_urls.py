"""
API URL configuration for V2 – Advanced Search / V4 – Messaging.

All endpoints are prefixed with /api/ (configured in the project urls.py).
"""

from django.urls import path

from . import api_views

urlpatterns = [
    # Property search & detail
    path('properties/search/', api_views.PropertySearchAPIView.as_view(), name='api_property_search'),
    path('properties/suggestions/', api_views.SearchSuggestionsAPIView.as_view(), name='api_search_suggestions'),
    path('properties/stats/', api_views.PropertyStatsAPIView.as_view(), name='api_property_stats'),
    path('properties/<slug:slug>/', api_views.PropertyDetailAPIView.as_view(), name='api_property_detail'),

    # Amenities
    path('amenities/', api_views.AmenityListAPIView.as_view(), name='api_amenity_list'),

    # V4 – Messaging
    path('messages/inbox/', api_views.InboxAPIView.as_view(), name='api_inbox'),
    path('messages/compose/', api_views.ComposeAPIView.as_view(), name='api_compose'),
    path('messages/unread-count/', api_views.UnreadCountAPIView.as_view(), name='api_unread_count'),
    path('messages/<int:pk>/', api_views.ThreadAPIView.as_view(), name='api_thread'),
]
