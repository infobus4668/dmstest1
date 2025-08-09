# staff/signals.py

from django.db.models.signals import post_migrate
from django.apps import apps
from django.contrib.auth.models import Group, Permission

def assign_permissions(group, permissions):
    """
    Assigns a list of permissions to a group, clearing previous ones.
    """
    group.permissions.clear()
    for perm_codename in permissions:
        try:
            app_label, codename = perm_codename.split('.')
            perm = Permission.objects.get(content_type__app_label=app_label, codename=codename)
            group.permissions.add(perm)
        except Permission.DoesNotExist:
            print(f"Warning: Permission '{perm_codename}' not found. Skipping.")

def create_user_groups(sender, **kwargs):
    """
    Creates the initial user groups (roles) and assigns a comprehensive set of 
    default permissions after all migrations are run. This ensures a secure and
    logically structured user access system from the start.
    """
    roles_permissions = {
        # Managers have full control over all aspects of the clinic's operations,
        # from staff and patient management to billing and inventory.
        "Managers": [
            # Staff Management
            'staff.view_staffmember', 'staff.add_staffmember', 'staff.change_staffmember', 'staff.delete_staffmember',
            # Patient Management
            'patients.view_patient', 'patients.add_patient', 'patients.change_patient', 'patients.delete_patient',
            # Appointments
            'appointments.view_appointment', 'appointments.add_appointment', 'appointments.change_appointment', 'appointments.delete_appointment',
            # Billing & Invoicing (Full Control)
            'billing.view_invoice', 'billing.add_invoice', 'billing.change_invoice', 'billing.delete_invoice',
            'billing.add_invoicepayment', 'billing.add_refund',
            # Services Management
            'billing.view_service', 'billing.add_service', 'billing.change_service', 'billing.delete_service',
            # Inventory & Supplier Management
            'billing.view_product', 'billing.add_product', 'billing.change_product', 'billing.delete_product',
            'billing.view_productvariant', 'billing.add_productvariant', 'billing.change_productvariant', 'billing.delete_productvariant',
            'billing.view_stockitem', 'billing.add_stockitem', 'billing.change_stockitem', 'billing.delete_stockitem',
            'billing.view_supplier', 'billing.add_supplier', 'billing.change_supplier', 'billing.delete_supplier',
            'billing.view_purchaseorder', 'billing.add_purchaseorder', 'billing.change_purchaseorder', 'billing.delete_purchaseorder',
            'billing.add_stockadjustment', 'billing.view_stockadjustment',
            # Lab Cases
            'lab_cases.view_labcase', 'lab_cases.add_labcase', 'lab_cases.change_labcase', 'lab_cases.delete_labcase',
            # Dental Records (View only for oversight)
            'dental_records.view_dentalrecord',
        ],
        # Doctors have full control over clinical data but limited access to financial or administrative data.
        "Doctors": [
            'patients.view_patient', 'patients.add_patient', 'patients.change_patient',
            'appointments.view_appointment', 'appointments.add_appointment', 'appointments.change_appointment',
            'dental_records.view_dentalrecord', 'dental_records.add_dentalrecord', 'dental_records.change_dentalrecord', 'dental_records.delete_dentalrecord',
            'dental_records.view_prescription', 'dental_records.add_prescription', 'dental_records.change_prescription', 'dental_records.delete_prescription',
            'lab_cases.view_labcase', 'lab_cases.add_labcase', 'lab_cases.change_labcase',
            'billing.view_invoice', # Can see invoices but not create/edit them
        ],
        # Receptionists are the primary point of contact for patients and manage the front desk.
        "Receptionists": [
            'patients.view_patient', 'patients.add_patient', 'patients.change_patient', 'patients.delete_patient',
            'appointments.view_appointment', 'appointments.add_appointment', 'appointments.change_appointment', 'appointments.delete_appointment',
            'billing.view_invoice', 'billing.add_invoice', 'billing.add_invoicepayment',
            'lab_cases.view_labcase', 'lab_cases.add_labcase', 'lab_cases.change_labcase',
        ],
        # Assistants and Hygienists have limited, view-only access to support their clinical duties.
        "Assistants": [
            'patients.view_patient',
            'appointments.view_appointment',
            'dental_records.view_dentalrecord', # View-only access to prepare for procedures
        ],
        "Hygienists": [
            'patients.view_patient',
            'appointments.view_appointment',
            'dental_records.view_dentalrecord', 'dental_records.add_dentalrecord', # Can add their own notes/records
        ]
    }
    
    print("Checking for and creating initial user groups and permissions...")
    for role_name, perms in roles_permissions.items():
        group, _ = Group.objects.get_or_create(name=role_name)
        assign_permissions(group, perms)
        print(f"  - Successfully configured permissions for group: {group.name}.")

# Connect the signal to run after all migrations are complete.
post_migrate.connect(create_user_groups)