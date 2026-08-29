"""Endpoints structures employeur & paie — admin (IsStaff) uniquement."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.members.models import Member
from apps_coop.members.permissions import IsStaff

from . import services as svc
from .models import Structure, StructureEmployee
from .serializers import StructureDetailSerializer, StructureSerializer


def _detail(structure) -> dict:
    structure.refresh_from_db()
    return StructureDetailSerializer(structure).data


@api_view(["GET", "POST"])
@permission_classes([IsStaff])
def structures(request):
    if request.method == "POST":
        s = svc.create_structure(
            nom=request.data.get("nom") or "",
            description=request.data.get("description") or "",
            by=request.user,
        )
        return Response(_detail(s), status=status.HTTP_201_CREATED)
    qs = Structure.objects.all()
    return Response(StructureSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsStaff])
def structure_detail(request, pk: int):
    return Response(_detail(get_object_or_404(Structure, pk=pk)))


@api_view(["POST"])
@permission_classes([IsStaff])
def structure_close(request, pk: int):
    s = get_object_or_404(Structure, pk=pk)
    svc.close_structure(s, by=request.user)
    return Response(_detail(s))


@api_view(["POST"])
@permission_classes([IsStaff])
def structure_fund(request, pk: int):
    s = get_object_or_404(Structure, pk=pk)
    try:
        svc.fund_structure(
            structure=s, montant=request.data.get("montant") or 0, by=request.user
        )
    except svc.StructureError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail(s))


@api_view(["POST"])
@permission_classes([IsStaff])
def structure_withdraw(request, pk: int):
    s = get_object_or_404(Structure, pk=pk)
    try:
        svc.withdraw_funds(
            structure=s, montant=request.data.get("montant") or 0, by=request.user
        )
    except svc.StructureError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail(s))


# ── Employés ──────────────────────────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsStaff])
def structure_add_employee(request, pk: int):
    s = get_object_or_404(Structure, pk=pk)
    member = Member.objects.filter(pk=request.data.get("member_id")).first()
    if member is None:
        return Response({"detail": "Membre introuvable."}, status=404)
    try:
        svc.add_employee(
            s, member,
            poste=request.data.get("poste") or "",
            attribution=request.data.get("attribution") or "",
            montant_paie=request.data.get("montant_paie") or 0,
            by=request.user,
        )
    except svc.StructureError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail(s))


@api_view(["POST"])
@permission_classes([IsStaff])
def structure_update_employee(request, pk: int, emp_id: int):
    s = get_object_or_404(Structure, pk=pk)
    emp = get_object_or_404(StructureEmployee, pk=emp_id, structure=s)
    svc.update_employee(
        emp,
        poste=request.data.get("poste"),
        attribution=request.data.get("attribution"),
        montant_paie=request.data.get("montant_paie"),
        by=request.user,
    )
    return Response(_detail(s))


@api_view(["POST"])
@permission_classes([IsStaff])
def structure_remove_employee(request, pk: int, emp_id: int):
    s = get_object_or_404(Structure, pk=pk)
    emp = get_object_or_404(StructureEmployee, pk=emp_id, structure=s)
    svc.remove_employee(emp, by=request.user)
    return Response(_detail(s))


# ── Paie ──────────────────────────────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsStaff])
def structure_pay_employee(request, pk: int, emp_id: int):
    s = get_object_or_404(Structure, pk=pk)
    emp = get_object_or_404(StructureEmployee, pk=emp_id, structure=s)
    montant = request.data.get("montant")
    try:
        svc.pay_employee(
            structure=s, employee=emp,
            montant=montant if montant not in (None, "") else None,
            by=request.user,
        )
    except svc.StructureError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail(s))


@api_view(["POST"])
@permission_classes([IsStaff])
def structure_run_payroll(request, pk: int):
    s = get_object_or_404(Structure, pk=pk)
    try:
        svc.run_payroll(
            structure=s, periode=request.data.get("periode") or "", by=request.user
        )
    except svc.StructureError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_detail(s))


@api_view(["GET"])
@permission_classes([IsStaff])
def payroll_run_pdf(request, pk: int, run_id: int):
    """PDF « État de paie du mois » d'un lot de paie (registre)."""
    from django.http import HttpResponse

    from .models import PayrollRun
    from .payroll_pdf import build_payroll_pdf

    s = get_object_or_404(Structure, pk=pk)
    run = get_object_or_404(PayrollRun, pk=run_id, structure=s)
    pdf = build_payroll_pdf(run)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = (
        f'inline; filename="etat-paie-{s.nom}-{run.periode}.pdf"'
    )
    return resp
