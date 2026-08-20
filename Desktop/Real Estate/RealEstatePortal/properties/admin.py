from django.contrib import admin

from .models import Amenity, Profile, Property, PropertyAmenity


class PropertyAmenityInline(admin.TabularInline):
    model = PropertyAmenity
    extra = 1


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'city', 'property_type', 'listing_type', 'price', 'status', 'agent', 'created_at')
    list_filter = ('property_type', 'listing_type', 'status', 'city')
    search_fields = ('title', 'city', 'address', 'state')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [PropertyAmenityInline]
    exclude = ('amenities',)


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone', 'agency_name')
    list_filter = ('role',)


admin.site.register(PropertyAmenity)
