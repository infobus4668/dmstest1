# DENTALCLINICSYSTEM/staff/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
# This is the new import to handle the database error
from django.db.models import ProtectedError
from .models import StaffMember
from .forms import StaffMemberForm

@login_required
@permission_required('staff.view_staffmember', raise_exception=True)
def staff_list(request):
    staff_members = StaffMember.objects.select_related('user').prefetch_related('user__groups').all()
    return render(request, 'staff/staff_list.html', {'staff_members': staff_members, 'page_title': 'Staff Management'})

@login_required
@permission_required('staff.add_staffmember', raise_exception=True)
def add_staff_member(request):
    if request.method == 'POST':
        form = StaffMemberForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Staff member added successfully.')
            return redirect('staff:staff_list')
    else:
        form = StaffMemberForm()
    
    # --- CHANGE 1: Point to the new template ---
    return render(request, 'staff/staff_form.html', {'form': form, 'page_title': 'Add New Staff Member'})

@login_required
@permission_required('staff.change_staffmember', raise_exception=True)
def edit_staff_member(request, pk):
    staff_member = get_object_or_404(StaffMember, pk=pk)
    if request.method == 'POST':
        form = StaffMemberForm(request.POST, instance=staff_member)
        if form.is_valid():
            form.save()
            messages.success(request, 'Staff member details updated successfully.')
            return redirect('staff:staff_list')
    else:
        form = StaffMemberForm(instance=staff_member)
    
    # --- CHANGE 2: Point to the new template and pass the 'object' ---
    return render(request, 'staff/staff_form.html', {
        'form': form, 
        'page_title': f'Edit Staff: {staff_member.name}',
        'object': staff_member  # This is the key for our 'if' check in the template
    })

@login_required
@permission_required('staff.delete_staffmember', raise_exception=True)
def delete_staff_member(request, pk):
    staff_member = get_object_or_404(StaffMember, pk=pk)
    if request.method == 'POST':
        try:
            staff_name = staff_member.name
            staff_member.user.delete()
            messages.success(request, f'Staff member {staff_name} and their user account have been deleted.')
        except ProtectedError:
            # This is the new, user-friendly error handling
            messages.error(request, f'Cannot delete {staff_member.name} because they are linked to existing records (e.g., appointments, invoices). Please re-assign or delete those records first.')
        
        return redirect('staff:staff_list')
        
    return render(request, 'staff/staff_confirm_delete.html', {'staff_member': staff_member})