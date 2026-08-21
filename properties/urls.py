from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),

    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Properties
    path('properties/', views.property_list, name='property_list'),
    path('properties/add/', views.property_create, name='property_create'),
    path('properties/<slug:slug>/', views.property_detail, name='property_detail'),
    path('properties/<slug:slug>/edit/', views.property_update, name='property_update'),
    path('properties/<slug:slug>/delete/', views.property_delete, name='property_delete'),

    # Amenities
    path('amenities/', views.amenity_list, name='amenity_list'),
    path('amenities/add/', views.amenity_create, name='amenity_create'),
]
