from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),

    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Properties – specific paths FIRST (before slug wildcard)
    path('properties/', views.property_list, name='property_list'),
    path('properties/advanced-search/', views.advanced_search, name='property_advanced_search'),
    path('properties/add/', views.property_create, name='property_create'),
    path('properties/bulk-upload/', views.bulk_upload_view, name='bulk_upload'),
    path('properties/bulk-upload/sample-csv/', views.bulk_upload_sample_csv, name='bulk_upload_sample_csv'),

    # V3 – Gallery image management (AJAX) – before slug wildcard
    path('properties/images/<int:image_id>/delete/', views.gallery_image_delete, name='gallery_image_delete'),
    path('properties/images/<int:image_id>/set-primary/', views.gallery_image_set_primary, name='gallery_image_set_primary'),

    # Slug-based property routes (AFTER specific named paths)
    path('properties/<slug:slug>/', views.property_detail, name='property_detail'),
    path('properties/<slug:slug>/edit/', views.property_update, name='property_update'),
    path('properties/<slug:slug>/delete/', views.property_delete, name='property_delete'),

    # Amenities
    path('amenities/', views.amenity_list, name='amenity_list'),
    path('amenities/add/', views.amenity_create, name='amenity_create'),

    # V4 – Messaging System
    path('messages/', views.inbox_view, name='inbox'),
    path('messages/sent/', views.sent_view, name='sent_messages'),
    path('messages/compose/', views.compose_view, name='compose_message'),
    path('messages/<int:pk>/', views.thread_view, name='thread_view'),
    path('messages/<int:pk>/reply/', views.message_reply_view, name='message_reply'),
    path('messages/<int:pk>/delete/', views.message_delete_view, name='message_delete'),

    # V5 – Saved Searches
    path('saved-searches/', views.saved_searches_list_view, name='saved_searches'),
    path('saved-searches/<int:pk>/delete/', views.saved_search_delete_view, name='saved_search_delete'),
]


