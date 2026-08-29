"""Routes des structures employeur & paie (admin)."""
from django.urls import path

from . import views

urlpatterns = [
    path("admin/structures/", views.structures, name="structures-admin"),
    path("admin/structures/<int:pk>/", views.structure_detail, name="structure-detail"),
    path("admin/structures/<int:pk>/close/", views.structure_close, name="structure-close"),
    path("admin/structures/<int:pk>/fund/", views.structure_fund, name="structure-fund"),
    path("admin/structures/<int:pk>/withdraw/", views.structure_withdraw, name="structure-withdraw"),
    path("admin/structures/<int:pk>/employees/add/", views.structure_add_employee, name="structure-add-employee"),
    path("admin/structures/<int:pk>/employees/<int:emp_id>/update/", views.structure_update_employee, name="structure-update-employee"),
    path("admin/structures/<int:pk>/employees/<int:emp_id>/remove/", views.structure_remove_employee, name="structure-remove-employee"),
    path("admin/structures/<int:pk>/employees/<int:emp_id>/pay/", views.structure_pay_employee, name="structure-pay-employee"),
    path("admin/structures/<int:pk>/run-payroll/", views.structure_run_payroll, name="structure-run-payroll"),
    path("admin/structures/<int:pk>/payroll/<int:run_id>/pdf/", views.payroll_run_pdf, name="payroll-run-pdf"),
]
