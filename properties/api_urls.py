"""
API URL configuration for V2 – Advanced Search.

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
]
