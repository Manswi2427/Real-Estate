from django.contrib import admin
from django.utils.html import format_html

from .models import Amenity, Profile, Property, PropertyAmenity, PropertyImage


class PropertyAmenityInline(admin.TabularInline):
    model = PropertyAmenity
    extra = 1


class PropertyImageInline(admin.TabularInline):
    """V3 – Manage gallery images directly within the Property admin page."""
    model = PropertyImage
    extra = 1
    fields = ('image', 'caption', 'is_primary', 'image_preview')
    readonly_fields = ('image_preview',)

    @admin.display(description='Preview')
    def image_preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:6px;object-fit:cover;" />',
                obj.image.url,
            )
        return '—'


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'city', 'property_type', 'listing_type', 'price', 'status', 'agent', 'image_count', 'created_at')
    list_filter = ('property_type', 'listing_type', 'status', 'city')
    search_fields = ('title', 'city', 'address', 'state')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [PropertyAmenityInline, PropertyImageInline]
    exclude = ('amenities',)

    @admin.display(description='Images')
    def image_count(self, obj):
        return obj.images.count()


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone', 'agency_name')
    list_filter = ('role',)


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    """V3 – Standalone admin for PropertyImage records."""
    list_display = ('id', 'property', 'is_primary', 'caption', 'image_preview', 'created_at')
    list_filter = ('is_primary',)
    search_fields = ('property__title', 'caption')
    readonly_fields = ('image_preview',)

    @admin.display(description='Preview')
    def image_preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" style="height:80px;border-radius:8px;object-fit:cover;" />',
                obj.image.url,
            )
        return '—'


admin.site.register(PropertyAmenity)

