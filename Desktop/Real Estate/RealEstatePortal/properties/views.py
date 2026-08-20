from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AmenityForm, PropertyFilterForm, PropertyForm, RegisterForm
from .models import Amenity, Property


def agent_required(view_func):
    """Only logged-in users with the Agent role may pass."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Please log in to continue.")
            return redirect('login')
        if not hasattr(request.user, 'profile') or not request.user.profile.is_agent:
            messages.error(request, "Only agents can perform this action.")
            return redirect('property_list')
        return view_func(request, *args, **kwargs)
    return _wrapped


# ---------- Auth Views ----------

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to RealEstatePortal, {user.username}!")
            return redirect('home')
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})


def _style_auth_form(form):
    form.fields['username'].widget.attrs['class'] = 'form-control'
    form.fields['password'].widget.attrs['class'] = 'form-control'
    return form


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = _style_auth_form(AuthenticationForm(request, data=request.POST))
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                next_url = request.GET.get('next', 'home')
                return redirect(next_url)
    else:
        form = _style_auth_form(AuthenticationForm())
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('home')


# ---------- Core Views ----------

def home(request):
    featured = Property.objects.filter(
        status=Property.Status.AVAILABLE
    ).prefetch_related('amenities').order_by('-is_featured', '-created_at')[:6]
    total_properties = Property.objects.count()
    total_cities = Property.objects.values('city').distinct().count()
    total_agents = Property.objects.values('agent').distinct().count()
    context = {
        'featured_properties': featured,
        'total_properties': total_properties,
        'total_cities': total_cities,
        'total_agents': total_agents,
        'property_types': Property.PropertyType.choices,
    }
    return render(request, 'home.html', context)


def get_filtered_properties_queryset(filter_params):
    """
    Constructs a filtered queryset for properties based on filter_params.
    """
    qs = Property.objects.select_related('agent', 'agent__profile').prefetch_related('amenities')

    keyword = filter_params.get('keyword')
    if keyword:
        qs = qs.filter(
            Q(title__icontains=keyword) | Q(city__icontains=keyword) |
            Q(address__icontains=keyword) | Q(state__icontains=keyword)
        )

    property_type = filter_params.get('property_type')
    if property_type:
        qs = qs.filter(property_type=property_type)

    listing_type = filter_params.get('listing_type')
    if listing_type:
        qs = qs.filter(listing_type=listing_type)

    city = filter_params.get('city')
    if city:
        qs = qs.filter(city__icontains=city)

    min_price = filter_params.get('min_price')
    if min_price is not None:
        qs = qs.filter(price__gte=min_price)

    max_price = filter_params.get('max_price')
    if max_price is not None:
        qs = qs.filter(price__lte=max_price)

    min_area_sqft = filter_params.get('min_area_sqft')
    if min_area_sqft is not None:
        qs = qs.filter(area_sqft__gte=min_area_sqft)

    max_area_sqft = filter_params.get('max_area_sqft')
    if max_area_sqft is not None:
        qs = qs.filter(area_sqft__lte=max_area_sqft)

    bedrooms = filter_params.get('bedrooms')
    if bedrooms:
        qs = qs.filter(bedrooms__gte=int(bedrooms))

    bathrooms = filter_params.get('bathrooms')
    if bathrooms:
        qs = qs.filter(bathrooms__gte=int(bathrooms))

    amenities = filter_params.get('amenities')
    if amenities:
        for amenity in amenities:
            qs = qs.filter(amenities=amenity)

    sort = filter_params.get('sort') or '-created_at'
    allowed_sorts = ['-created_at', 'price', '-price', '-area_sqft']
    if sort not in allowed_sorts:
        sort = '-created_at'
    qs = qs.order_by(sort)

    return qs.distinct()


def serialize_property(prop, request=None):
    """
    Serializes a Property instance to a dictionary.
    """
    image_url = ''
    if prop.image:
        image_url = prop.image.url
        if request:
            image_url = request.build_absolute_uri(image_url)

    return {
        'id': prop.id,
        'title': prop.title,
        'slug': prop.slug,
        'description': prop.description,
        'property_type': prop.property_type,
        'listing_type': prop.listing_type,
        'status': prop.status,
        'price': str(prop.price),
        'area_sqft': str(prop.area_sqft),
        'bedrooms': prop.bedrooms,
        'bathrooms': prop.bathrooms,
        'address': prop.address,
        'city': prop.city,
        'state': prop.state,
        'zipcode': prop.zipcode,
        'latitude': str(prop.latitude) if prop.latitude is not None else None,
        'longitude': str(prop.longitude) if prop.longitude is not None else None,
        'image_url': image_url,
        'is_featured': prop.is_featured,
        'created_at': prop.created_at.isoformat(),
        'updated_at': prop.updated_at.isoformat(),
        'agent': {
            'id': prop.agent.id,
            'username': prop.agent.username,
            'email': prop.agent.email,
            'phone': prop.agent.profile.phone if hasattr(prop.agent, 'profile') else '',
            'agency_name': prop.agent.profile.agency_name if hasattr(prop.agent, 'profile') else '',
        },
        'amenities': [
            {
                'id': am.id,
                'name': am.name,
                'icon': am.icon,
                'description': am.description,
            }
            for am in prop.amenities.all()
        ]
    }


def property_list(request):
    form = PropertyFilterForm(request.GET or None)

    if form.is_valid():
        qs = get_filtered_properties_queryset(form.cleaned_data)
    else:
        qs = get_filtered_properties_queryset({})

    paginator = Paginator(qs, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'form': form,
        'page_obj': page_obj,
        'properties': page_obj.object_list,
        'total_results': paginator.count,
    }
    return render(request, 'property_list.html', context)


def property_search_api(request):
    """
    JSON API endpoint for searching properties.
    Supports filtering by price range, square footage, bedrooms, bathrooms, and specific amenities.
    """
    # Parse request GET parameters into a structure suitable for validation by PropertyFilterForm
    data = {}
    for key in request.GET:
        if key == 'amenities':
            raw_amenities = request.GET.getlist('amenities')
            amenities_ids = []
            for val in raw_amenities:
                if ',' in val:
                    amenities_ids.extend([v.strip() for v in val.split(',') if v.strip()])
                elif val.strip():
                    amenities_ids.append(val.strip())
            data['amenities'] = amenities_ids
        else:
            data[key] = request.GET.get(key)

    form = PropertyFilterForm(data)
    if form.is_valid():
        qs = get_filtered_properties_queryset(form.cleaned_data)

        # Basic pagination support
        try:
            limit = int(request.GET.get('limit', 10))
            if limit < 1 or limit > 100:
                limit = 10
        except ValueError:
            limit = 10

        try:
            offset = int(request.GET.get('offset', 0))
            if offset < 0:
                offset = 0
        except ValueError:
            offset = 0

        total_count = qs.count()
        qs_slice = qs[offset : offset + limit]

        serialized_properties = [serialize_property(p, request) for p in qs_slice]

        return JsonResponse({
            'total_results': total_count,
            'limit': limit,
            'offset': offset,
            'properties': serialized_properties
        })
    else:
        return JsonResponse({
            'error': 'Invalid filter parameters',
            'details': form.errors
        }, status=400)


def property_detail(request, slug):
    property_obj = get_object_or_404(
        Property.objects.select_related('agent', 'agent__profile').prefetch_related('amenities'),
        slug=slug,
    )
    is_owner = request.user.is_authenticated and property_obj.agent_id == request.user.id
    related = Property.objects.filter(
        city=property_obj.city
    ).exclude(pk=property_obj.pk)[:3]
    context = {
        'property': property_obj,
        'is_owner': is_owner,
        'related_properties': related,
    }
    return render(request, 'property_detail.html', context)


@agent_required
def property_create(request):
    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES)
        if form.is_valid():
            new_property = form.save(commit=False)
            new_property.agent = request.user
            new_property.save()
            form.save_m2m()
            messages.success(request, "Property listed successfully!")
            return redirect('property_detail', slug=new_property.slug)
    else:
        form = PropertyForm()
    return render(request, 'property_form.html', {'form': form, 'is_edit': False})


@agent_required
def property_update(request, slug):
    property_obj = get_object_or_404(Property, slug=slug)
    if property_obj.agent_id != request.user.id:
        messages.error(request, "You can only edit your own listings.")
        return redirect('property_detail', slug=slug)

    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES, instance=property_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Property updated successfully!")
            return redirect('property_detail', slug=property_obj.slug)
    else:
        form = PropertyForm(instance=property_obj)
    return render(request, 'property_form.html', {'form': form, 'is_edit': True, 'property': property_obj})


@agent_required
def property_delete(request, slug):
    property_obj = get_object_or_404(Property, slug=slug)
    if property_obj.agent_id != request.user.id:
        messages.error(request, "You can only delete your own listings.")
        return redirect('property_detail', slug=slug)

    if request.method == 'POST':
        property_obj.delete()
        messages.success(request, "Property deleted.")
        return redirect('property_list')
    return render(request, 'property_confirm_delete.html', {'property': property_obj})


def amenity_list(request):
    amenities = Amenity.objects.all().order_by('name')
    return render(request, 'amenity_list.html', {'amenities': amenities})


@agent_required
def amenity_create(request):
    if request.method == 'POST':
        form = AmenityForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Amenity added.")
            return redirect('amenity_list')
    else:
        form = AmenityForm()
    return render(request, 'amenity_form.html', {'form': form})
