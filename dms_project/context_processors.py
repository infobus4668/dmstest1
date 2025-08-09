# dms_project/context_processors.py

def clinic_details(request):
    # ... (this function remains the same)
    return {
        'CLINIC_NAME': 'Babu Dental Clinic',
        'CLINIC_ADDRESS': 'Beach Road, Kadapakkam, Cheyyur Taluk, Chengalpattu District, Tamilnadu - 603304',
        'CLINIC_PHONE': '04427526041',
        'CLINIC_EMAIL': 'drbdcdental@gmail.com'
    }

def user_roles_processor(request):
    """
    Adds user role flags to the template context based on Group membership.
    """
    if not request.user.is_authenticated:
        return {}

    # Check group membership by name.
    is_manager = request.user.groups.filter(name='Managers').exists()
    is_receptionist = request.user.groups.filter(name='Receptionists').exists()
    is_doctor = request.user.groups.filter(name='Doctors').exists()
    is_assistant = request.user.groups.filter(name='Assistants').exists()
    is_hygienist = request.user.groups.filter(name='Hygienists').exists()
            
    # Superuser has all implicit permissions, but we can set flags for UI consistency.
    if request.user.is_superuser:
        is_manager = True
        is_receptionist = True
        is_doctor = True
        is_assistant = True
        is_hygienist = True
            
    return {
        'is_manager': is_manager,
        'is_doctor': is_doctor,
        'is_receptionist': is_receptionist,
        'is_assistant': is_assistant,
        'is_hygienist': is_hygienist,
    }