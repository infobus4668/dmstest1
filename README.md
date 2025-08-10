# Dental Clinic Management System

A comprehensive web-based management system for dental clinics, built with Django. It streamlines patient management, appointments, billing, inventory, lab cases, staff, reporting, and audit logging.

## Features

- **Patient Management**: Register, edit, and view patient details, medical history, and appointment history.
- **Appointments**: Schedule, manage, and print appointment summaries and bills.
- **Billing & Invoices**: Create invoices, record payments, refunds, manage suppliers, products, and inventory.
- **Inventory Management**: Track stock, purchase orders, returns, and replacements.
- **Lab Cases**: Log, track, and manage dental lab cases and payments.
- **Dental Records & Prescriptions**: Record treatments, upload images, manage prescriptions, and print prescription sheets.
- **Staff Management**: Add, edit, and view staff members, assign roles, and manage credentials.
- **Reporting**: Financial summaries, supplier payments, stock received, and lab case reports.
- **Audit Log**: Track changes to user roles for compliance and security.
- **Authentication**: Secure login, password reset, and permission-based access control.

## Project Structure

```
dms_project/           # Django project settings
appointments/          # App for appointment scheduling and billing
audit_log/             # App for role change audit logging
billing/               # App for invoices, payments, suppliers, inventory
dashboard/             # Main dashboard and statistics
dental_records/        # App for dental records and prescriptions
lab_cases/             # App for managing lab cases and payments
patients/              # Patient registration and management
reporting/             # Financial and operational reports
staff/                 # Staff management and roles
static/                # Static files (CSS, JS, images)
templates/             # HTML templates for all modules
media/                 # Uploaded files (images, documents)
db.sqlite3             # SQLite database (default)
manage.py              # Django management script
requirements.txt       # Python dependencies
.env                   # Environment variables
```

## Setup Instructions

1. **Clone the repository**
   ```sh
   git clone <repo-url>
   cd dmstest1
   ```

2. **Install dependencies**
   ```sh
   pip install -r requirements.txt
   ```

3. **Apply migrations**
   ```sh
   python manage.py migrate
   ```

4. **Create a superuser**
   ```sh
   python manage.py createsuperuser
   ```

5. **Run the development server**
   ```sh
   python manage.py runserver
   ```

6. **Access the application**
   - Open [http://localhost:8000](http://localhost:8000) in your browser.

## Usage

- **Admin Panel**: `/admin/` for managing users, groups, and all models.
- **Dashboard**: Overview of appointments, outstanding balances, and quick links.
- **Patients**: Register new patients, view details, and appointment history.
- **Appointments**: Schedule and manage appointments.
- **Billing**: Create invoices, record payments, refunds, and manage suppliers/products.
- **Inventory**: Track stock, purchase orders, and returns.
- **Lab Cases**: Log and manage dental lab cases and payments.
- **Staff**: Manage staff members and assign roles.
- **Reports**: View financial, supplier, stock, and lab case reports.
- **Audit Log**: Track role changes for users.

## Technologies Used

- **Backend**: Django (Python)
- **Database**: SQLite (default, can be switched to PostgreSQL)
- **Frontend**: HTML, CSS (custom + Bootstrap), JavaScript
- **Authentication**: Django Auth
- **Reporting**: Custom templates and context processors

## Customization

- **Clinic Details**: Set clinic name, address, phone, and email in context processors ([dms_project/settings.py](dms_project/settings.py)).
- **Static & Media Files**: Configure paths in settings.
- **User Roles**: Assign roles via Django admin or staff management UI.

## License

This project is proprietary and intended for internal use by dental clinics.

## Support

For issues or feature requests, contact the clinic manager or system