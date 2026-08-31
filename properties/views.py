import csv
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    AmenityForm, BulkUploadForm, MessageComposeForm, MessageReplyForm,
    PropertyFilterForm, PropertyForm, RegisterForm, SavedSearchForm
)
from .models import Amenity, Message, Property, PropertyImage, SavedSearch



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


def _save_gallery_images(property_obj, files):
    """
    V3 helper – Create PropertyImage records from a list of uploaded files.
    The first image saved triggers auto-promotion to primary (via model logic).
    """
    for f in files:
        PropertyImage.objects.create(property=property_obj, image=f)


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
    ).prefetch_related('amenities', 'images').order_by('-is_featured', '-created_at')[:6]
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
    qs = Property.objects.select_related('agent', 'agent__profile').prefetch_related('amenities', 'images')

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
        if data.get('status'):
            qs = qs.filter(status=data['status'])
        if data.get('city'):
            qs = qs.filter(city__icontains=data['city'])
        if data.get('min_price') is not None:
            qs = qs.filter(price__gte=data['min_price'])
        if data.get('max_price') is not None:
            qs = qs.filter(price__lte=data['max_price'])
        if data.get('min_area') is not None:
            qs = qs.filter(area_sqft__gte=data['min_area'])
        if data.get('max_area') is not None:
            qs = qs.filter(area_sqft__lte=data['max_area'])
        if data.get('bedrooms'):
            qs = qs.filter(bedrooms__gte=int(data['bedrooms']))
        if data.get('bathrooms'):
            qs = qs.filter(bathrooms__gte=int(data['bathrooms']))
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


def advanced_search(request):
    """Renders the dedicated Advanced Search page with AJAX functionality."""
    return render(request, 'advanced_search.html')


def property_detail(request, slug):
    property_obj = get_object_or_404(
        Property.objects.select_related('agent', 'agent__profile').prefetch_related('amenities', 'images'),
        slug=slug,
    )
    is_owner = request.user.is_authenticated and property_obj.agent_id == request.user.id
    related = Property.objects.filter(
        city=property_obj.city
    ).exclude(pk=property_obj.pk).prefetch_related('images')[:3]

    # V3 – ordered gallery images (primary first)
    gallery_images = list(property_obj.images.order_by('-is_primary', 'created_at'))

    context = {
        'property': property_obj,
        'is_owner': is_owner,
        'related_properties': related,
        'gallery_images': gallery_images,
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

            # V3 – Process gallery images
            uploaded_files = request.FILES.getlist('gallery_images')
            if uploaded_files:
                _save_gallery_images(new_property, uploaded_files)

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

            # V3 – Process newly uploaded gallery images
            uploaded_files = request.FILES.getlist('gallery_images')
            if uploaded_files:
                _save_gallery_images(property_obj, uploaded_files)

            messages.success(request, "Property updated successfully!")
            return redirect('property_detail', slug=property_obj.slug)
    else:
        form = PropertyForm(instance=property_obj)

    # V3 – Existing gallery for display in the edit form
    gallery_images = list(property_obj.images.order_by('-is_primary', 'created_at'))
    return render(request, 'property_form.html', {
        'form': form,
        'is_edit': True,
        'property': property_obj,
        'gallery_images': gallery_images,
    })


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


# ---------- V3 – Gallery AJAX Views ----------

@require_POST
@login_required
def gallery_image_delete(request, image_id):
    """
    AJAX endpoint – Deletes a gallery image.
    Only the property owner (agent) can delete.
    Returns JSON {success, message, new_primary_url?}.
    """
    img = get_object_or_404(PropertyImage, pk=image_id)
    prop = img.property

    if prop.agent_id != request.user.id:
        return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)

    was_primary = img.is_primary
    img.delete()  # signal will elect next primary if needed

    # Refresh property to get updated image field
    prop.refresh_from_db()
    new_primary_url = None
    if prop.image:
        new_primary_url = prop.image.url

    return JsonResponse({
        'success': True,
        'message': 'Image deleted.',
        'was_primary': was_primary,
        'new_primary_url': new_primary_url,
    })


@require_POST
@login_required
def gallery_image_set_primary(request, image_id):
    """
    AJAX endpoint – Sets a gallery image as the primary thumbnail.
    Only the property owner (agent) can change this.
    Returns JSON {success, message, image_url}.
    """
    img = get_object_or_404(PropertyImage, pk=image_id)
    prop = img.property

    if prop.agent_id != request.user.id:
        return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)

    img.make_primary()

    return JsonResponse({
        'success': True,
        'message': 'Primary image updated.',
        'image_url': img.image.url,
        'image_id': img.pk,
    })


# ---------- Amenity Views ----------

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


# ─────────────────────────────────────────────────────────────────────────────
# V4 – Messaging System Views
# ─────────────────────────────────────────────────────────────────────────────


def _get_unread_count(user):
    """Helper: number of unread messages in user's inbox."""
    if not user.is_authenticated:
        return 0
    return Message.objects.filter(receiver=user, is_read=False).count()


@login_required
def inbox_view(request):
    """
    Inbox – shows all messages received by the current user.
    Groups them by 'thread root' so reply chains appear once.
    Unread count badge shown per thread.
    """
    # All received messages, newest first
    received = (
        Message.objects
        .filter(receiver=request.user)
        .select_related('sender', 'property', 'parent')
        .order_by('-sent_at')
    )

    # Build thread list: walk to root and deduplicate
    seen_roots = set()
    threads = []
    for msg in received:
        root = msg.get_thread_root()
        if root.pk not in seen_roots:
            seen_roots.add(root.pk)
            # Count unread in this thread (messages where receiver=user)
            unread = Message.objects.filter(
                Q(pk=root.pk) | Q(parent=root),
                receiver=request.user,
                is_read=False,
            ).count()
            threads.append({'root': root, 'latest': msg, 'unread': unread})

    paginator = Paginator(threads, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'inbox.html', {
        'page_obj': page_obj,
        'threads': page_obj.object_list,
        'unread_total': _get_unread_count(request.user),
    })


@login_required
def sent_view(request):
    """Outbox – all messages sent by the current user."""
    sent_msgs = (
        Message.objects
        .filter(sender=request.user)
        .select_related('receiver', 'property')
        .order_by('-sent_at')
    )
    paginator = Paginator(sent_msgs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'sent.html', {
        'page_obj': page_obj,
        'sent_messages': page_obj.object_list,
    })


@login_required
def compose_view(request):
    """
    Compose a new message.
    Supports GET params: ?to=<username>&property_id=<id>
    to pre-fill receiver and property context from a property detail page.
    """
    # Resolve receiver from ?to= param
    receiver = None
    to_username = request.GET.get('to') or request.POST.get('to_username')
    if to_username:
        receiver = get_object_or_404(User, username=to_username)

    # Prevent messaging yourself
    if receiver and receiver == request.user:
        messages.error(request, "You cannot send a message to yourself.")
        return redirect('inbox')

    # Resolve optional property context
    property_obj = None
    property_id = request.GET.get('property_id') or request.POST.get('property_id')
    if property_id:
        try:
            property_obj = Property.objects.get(pk=property_id)
        except Property.DoesNotExist:
            pass

    if request.method == 'POST':
        if not receiver:
            messages.error(request, "Recipient not specified.")
            return redirect('inbox')
        form = MessageComposeForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.sender = request.user
            msg.receiver = receiver
            msg.property = property_obj
            msg.save()
            messages.success(request, f"Message sent to {receiver.username}!")
            return redirect('thread_view', pk=msg.pk)
    else:
        # Pre-fill subject if property context provided
        initial = {}
        if property_obj:
            initial['subject'] = f"Enquiry about: {property_obj.title}"
        form = MessageComposeForm(initial=initial)

    return render(request, 'compose.html', {
        'form': form,
        'receiver': receiver,
        'property_obj': property_obj,
    })


@login_required
def thread_view(request, pk):
    """
    Full conversation thread.
    Shows the root message + all its replies, oldest-first.
    Marks all unread messages in this thread (where receiver=user) as read.
    Also contains the inline reply form.
    """
    root_msg = get_object_or_404(
        Message.select_related('sender', 'receiver', 'property')
        if hasattr(Message, 'select_related') else Message.objects,
        pk=pk,
    )
    # Re-fetch with select_related
    root_msg = get_object_or_404(
        Message.objects.select_related('sender', 'receiver', 'property'),
        pk=pk,
    )

    # Security: only sender or receiver (or their participants) may view
    if request.user not in (root_msg.sender, root_msg.receiver):
        messages.error(request, "You do not have permission to view this conversation.")
        return redirect('inbox')

    # Get all replies in chronological order
    reply_msgs = (
        root_msg.replies
        .select_related('sender', 'receiver')
        .order_by('sent_at')
    )

    # Mark unread messages as read for the current user
    Message.objects.filter(
        Q(pk=root_msg.pk) | Q(parent=root_msg),
        receiver=request.user,
        is_read=False,
    ).update(is_read=True)

    reply_form = MessageReplyForm()

    return render(request, 'thread.html', {
        'root_msg': root_msg,
        'reply_msgs': reply_msgs,
        'reply_form': reply_form,
        'other_user': root_msg.receiver if request.user == root_msg.sender else root_msg.sender,
    })


@require_POST
@login_required
def message_reply_view(request, pk):
    """
    POST endpoint to submit a reply to a thread.
    pk = root message pk.
    """
    root_msg = get_object_or_404(Message, pk=pk)

    if request.user not in (root_msg.sender, root_msg.receiver):
        messages.error(request, "You do not have permission to reply to this conversation.")
        return redirect('inbox')

    form = MessageReplyForm(request.POST)
    if form.is_valid():
        # Determine the other party
        other = root_msg.receiver if request.user == root_msg.sender else root_msg.sender
        Message.objects.create(
            sender=request.user,
            receiver=other,
            property=root_msg.property,
            subject=f"Re: {root_msg.subject}",
            body=form.cleaned_data['body'],
            parent=root_msg,
        )
        messages.success(request, "Reply sent.")
    else:
        messages.error(request, "Could not send reply. Please try again.")

    return redirect('thread_view', pk=pk)


@require_POST
@login_required
def message_delete_view(request, pk):
    """
    Delete a message (sender or receiver can delete).
    Only deletes root messages; replies are deleted by cascade when root is deleted.
    """
    msg = get_object_or_404(Message, pk=pk)
    if request.user not in (msg.sender, msg.receiver):
        messages.error(request, "Permission denied.")
        return redirect('inbox')
    msg.delete()
    messages.success(request, "Message deleted.")
    return redirect('inbox')


# ─────────────────────────────────────────────────────────────────────────────
# V5 – Bulk Upload & Saved Searches Views
# ─────────────────────────────────────────────────────────────────────────────

@agent_required
def bulk_upload_view(request):
    """
    Allows agents to bulk-upload property listings using a CSV file.
    Validates rows, manages transactions, and dynamically links amenities.
    """
    if request.method == 'POST':
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            
            # Read and decode CSV content
            try:
                decoded_file = csv_file.read().decode('utf-8-sig').splitlines()
                reader = csv.DictReader(decoded_file)
            except Exception as e:
                messages.error(request, f"Error reading CSV file: {str(e)}")
                return redirect('bulk_upload')

            # Ensure CSV has columns
            required_cols = {'title', 'description', 'property_type', 'listing_type', 'price', 'area_sqft'}
            if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
                messages.error(
                    request,
                    f"Invalid CSV structure. Missing one or more required columns: {required_cols}"
                )
                return redirect('bulk_upload')

            row_errors = []
            created_properties = []

            # Perform parsing in transaction block
            try:
                with transaction.atomic():
                    for idx, row in enumerate(reader, start=1):
                        errors = []
                        
                        # Required fields validation
                        title = (row.get('title') or '').strip()
                        description = (row.get('description') or '').strip()
                        if not title:
                            errors.append("Title is required.")
                        if not description:
                            errors.append("Description is required.")

                        # Choice fields validation
                        prop_type = (row.get('property_type') or '').strip().upper()
                        if prop_type not in dict(Property.PropertyType.choices):
                            errors.append(f"Invalid property_type '{prop_type}'. Choices: {list(dict(Property.PropertyType.choices).keys())}")

                        list_type = (row.get('listing_type') or '').strip().upper()
                        if list_type not in dict(Property.ListingType.choices):
                            errors.append(f"Invalid listing_type '{list_type}'. Choices: {list(dict(Property.ListingType.choices).keys())}")

                        status_val = (row.get('status') or 'AVAILABLE').strip().upper()
                        if status_val not in dict(Property.Status.choices):
                            errors.append(f"Invalid status '{status_val}'. Choices: {list(dict(Property.Status.choices).keys())}")

                        # Numeric validation
                        try:
                            price = float(row.get('price') or 0)
                            if price <= 0:
                                errors.append("Price must be positive.")
                        except ValueError:
                            errors.append("Price must be a valid number.")

                        try:
                            area_sqft = float(row.get('area_sqft') or 0)
                            if area_sqft <= 0:
                                errors.append("Area must be positive.")
                        except ValueError:
                            errors.append("Area must be a valid number.")

                        bedrooms = 0
                        if row.get('bedrooms'):
                            try:
                                bedrooms = int(row['bedrooms'])
                            except ValueError:
                                errors.append("Bedrooms must be an integer.")

                        bathrooms = 0
                        if row.get('bathrooms'):
                            try:
                                bathrooms = int(row['bathrooms'])
                            except ValueError:
                                errors.append("Bathrooms must be an integer.")

                        # Geolocation / Address optional parsing
                        address = (row.get('address') or '').strip()
                        city = (row.get('city') or '').strip()
                        state = (row.get('state') or '').strip()
                        zipcode = (row.get('zipcode') or '').strip()

                        latitude = None
                        if row.get('latitude'):
                            try:
                                latitude = float(row['latitude'])
                            except ValueError:
                                errors.append("Latitude must be a valid float.")

                        longitude = None
                        if row.get('longitude'):
                            try:
                                longitude = float(row['longitude'])
                            except ValueError:
                                errors.append("Longitude must be a valid float.")

                        # If errors found on this row, log them
                        if errors:
                            row_errors.append(f"Row {idx} ({title or 'Unnamed'}): " + " | ".join(errors))
                            continue

                        # Instantiate Property
                        prop = Property(
                            title=title,
                            description=description,
                            agent=request.user,
                            property_type=prop_type,
                            listing_type=list_type,
                            status=status_val,
                            price=price,
                            area_sqft=area_sqft,
                            bedrooms=bedrooms,
                            bathrooms=bathrooms,
                            address=address,
                            city=city,
                            state=state,
                            zipcode=zipcode,
                            latitude=latitude,
                            longitude=longitude,
                        )
                        prop.save()  # Triggers slugify and post_save matches

                        # Handle comma-separated list of amenities
                        amenity_names_str = row.get('amenities') or ''
                        if amenity_names_str:
                            names = [n.strip() for n in amenity_names_str.split(',') if n.strip()]
                            for name in names:
                                amenity_obj, _ = Amenity.objects.get_or_create(
                                    name=name,
                                    defaults={'icon': 'fa-solid fa-circle-check'}
                                )
                                prop.amenities.add(amenity_obj)

                        created_properties.append(prop)

                    if row_errors:
                        # Rollback complete transaction by raising Exception
                        raise Exception("Validation errors in CSV rows.")

            except Exception as e:
                # If transaction failed due to validation or DB constraint
                context = {
                    'form': form,
                    'errors': row_errors or [f"Transaction aborted: {str(e)}"],
                }
                return render(request, 'bulk_upload.html', context)

            messages.success(request, f"Successfully uploaded {len(created_properties)} property listings!")
            return redirect('property_list')
    else:
        form = BulkUploadForm()
    return render(request, 'bulk_upload.html', {'form': form})


@login_required
def saved_searches_list_view(request):
    """Lists saved searches of the logged-in buyer."""
    searches = SavedSearch.objects.filter(buyer=request.user).prefetch_related('amenities')
    return render(request, 'saved_searches.html', {'saved_searches': searches})


@require_POST
@login_required
def saved_search_delete_view(request, pk):
    """Deletes a saved search."""
    search = get_object_or_404(SavedSearch, pk=pk)
    if search.buyer_id != request.user.id:
        messages.error(request, "Permission denied.")
        return redirect('saved_searches')
    search.delete()
    messages.success(request, "Saved search deleted.")
    return redirect('saved_searches')

