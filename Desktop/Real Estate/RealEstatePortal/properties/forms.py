from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Amenity, Profile, Property


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=Profile.Role.choices, widget=forms.RadioSelect)
    phone = forms.CharField(max_length=20, required=False)
    agency_name = forms.CharField(max_length=150, required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'role', 'phone', 'agency_name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'role':
                field.widget.attrs['class'] = 'form-control'

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = self.cleaned_data['role']
            profile.phone = self.cleaned_data.get('phone', '')
            profile.agency_name = self.cleaned_data.get('agency_name', '')
            profile.save()
        return user


class PropertyForm(forms.ModelForm):
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Property
        fields = [
            'title', 'description', 'property_type', 'listing_type', 'status',
            'price', 'area_sqft', 'bedrooms', 'bathrooms',
            'address', 'city', 'state', 'zipcode', 'latitude', 'longitude',
            'image', 'amenities', 'is_featured',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'amenities':
                existing = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = (existing + ' form-control').strip()


class AmenityForm(forms.ModelForm):
    class Meta:
        model = Amenity
        fields = ['name', 'icon', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Swimming Pool'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'fa-solid fa-water-ladder'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
        }


class PropertyFilterForm(forms.Form):
    """Advanced search / filter form used on the property list page."""

    keyword = forms.CharField(required=False, widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Search by title, city, address...'}))
    property_type = forms.ChoiceField(
        required=False,
        choices=[('', 'Any Type')] + list(Property.PropertyType.choices),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    listing_type = forms.ChoiceField(
        required=False,
        choices=[('', 'Buy or Rent')] + list(Property.ListingType.choices),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'Any Status')] + list(Property.Status.choices),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    city = forms.CharField(required=False, widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'City'}))
    min_price = forms.DecimalField(required=False, widget=forms.NumberInput(
        attrs={'class': 'form-control', 'placeholder': 'Min Price'}))
    max_price = forms.DecimalField(required=False, widget=forms.NumberInput(
        attrs={'class': 'form-control', 'placeholder': 'Max Price'}))
    min_area = forms.DecimalField(required=False, widget=forms.NumberInput(
        attrs={'class': 'form-control', 'placeholder': 'Min Area (sqft)'}))
    max_area = forms.DecimalField(required=False, widget=forms.NumberInput(
        attrs={'class': 'form-control', 'placeholder': 'Max Area (sqft)'}))
    bedrooms = forms.ChoiceField(
        required=False,
        choices=[('', 'Any'), ('1', '1+'), ('2', '2+'), ('3', '3+'), ('4', '4+'), ('5', '5+')],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    bathrooms = forms.ChoiceField(
        required=False,
        choices=[('', 'Any'), ('1', '1+'), ('2', '2+'), ('3', '3+'), ('4', '4+')],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ('-created_at', 'Newest First'),
            ('price', 'Price: Low to High'),
            ('-price', 'Price: High to Low'),
            ('-area_sqft', 'Largest Area'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
