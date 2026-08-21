# RealEstatePortal (V1 — Property Catalog)

A Django-based real estate portal with role-based access (Agent / Buyer), advanced
property filtering, and a many-to-many Property <-> Amenity relationship via an
explicit linking table.

## Features
- **Roles**: Every user gets a `Profile` with role `AGENT` or `BUYER` (chosen at signup).
  Only Agents can create/edit/delete their own property listings and add amenities.
- **Schemas**:
  - `Property` — title, type, listing type (sale/rent), price, area, bedrooms/bathrooms,
    address, city, state, zip, **latitude/longitude** (geolocation), image, status.
  - `Amenity` — name, icon, description.
  - `PropertyAmenity` — the explicit many-to-many "through" table linking properties
    and amenities (a property has many amenities; an amenity belongs to many properties).
- **Advanced querying**: keyword search across title/city/address, filter by type,
  listing type, city, price range, minimum bedrooms, amenities (multi-select), and
  sorting — all built with Django `Q` objects and combined into one queryset.
- **Templates**: Bootstrap 5 + Font Awesome styled pages, all interlinked via a shared
  navbar/footer in `base.html` — Home, Properties (list + filters), Property Detail
  (with embedded map from lat/long), Add/Edit Property, Delete confirmation,
  Amenities list/add, Register, Login.

## Setup

```bash
cd RealEstatePortal
python -m venv venv
source venv/bin/activate      # venv\Scripts\activate on Windows
pip install -r requirements.txt

python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/

python manage.py runserver
```

Visit `http://127.0.0.1:8000/`.

## Suggested first steps
1. Go to `/admin/` (or `/amenities/add/` as an agent) and add a few Amenities
   (e.g. WiFi, Swimming Pool, Parking, Gym, Security) with Font Awesome icon classes.
2. Register an account and choose the **Agent** role.
3. Click **Add Property** in the navbar and create your first listing, checking off
   amenities and optionally adding latitude/longitude for the map.
4. Browse `/properties/` and try the filter sidebar (price range, bedrooms, amenities, sort).

## Project Structure
```
RealEstatePortal/
├── manage.py
├── RealEstatePortal/        # project settings, urls, wsgi
└── properties/
    ├── models.py            # Profile, Property, Amenity, PropertyAmenity
    ├── forms.py              # RegisterForm, PropertyForm, AmenityForm, PropertyFilterForm
    ├── views.py               # auth + CRUD + filtering views
    ├── urls.py
    ├── admin.py
    ├── signals.py             # auto-creates a Profile on user signup
    ├── templates/              # all HTML pages (Django template language)
    └── static/properties/css/style.css
```

## Notes for V2 ideas
- Distance-based geolocation search (e.g. "within 5 km") using the stored lat/long.
- Saved searches / favorites for Buyers.
- Image galleries (multiple photos per property) instead of a single image field.
- Agent dashboard with their own listings and inquiry messages.
