from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db.models import Q
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


def property_list(request):
    form = PropertyFilterForm(request.GET or None)
    qs = Property.objects.select_related('agent', 'agent__profile').prefetch_related('amenities')

    if form.is_valid():
        data = form.cleaned_data
        if data.get('keyword'):
            kw = data['keyword']
            qs = qs.filter(
                Q(title__icontains=kw) | Q(city__icontains=kw) |
                Q(address__icontains=kw) | Q(state__icontains=kw)
            )
        if data.get('property_type'):
            qs = qs.filter(property_type=data['property_type'])
        if data.get('listing_type'):
            qs = qs.filter(listing_type=data['listing_type'])
        if data.get('city'):
            qs = qs.filter(city__icontains=data['city'])
        if data.get('min_price') is not None:
            qs = qs.filter(price__gte=data['min_price'])
        if data.get('max_price') is not None:
            qs = qs.filter(price__lte=data['max_price'])
        if data.get('bedrooms'):
            qs = qs.filter(bedrooms__gte=int(data['bedrooms']))
        if data.get('amenities'):
            for amenity in data['amenities']:
                qs = qs.filter(amenities=amenity)
        sort = data.get('sort') or '-created_at'
        qs = qs.order_by(sort)
    else:
        qs = qs.order_by('-created_at')

    qs = qs.distinct()
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
