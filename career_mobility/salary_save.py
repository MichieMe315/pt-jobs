"""Save salary comparisons to Canadian job seeker accounts only.

Saved plans remain private to the signed-in job seeker.
"""
import json
import math

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST, require_GET

from .models import SavedCareerPlan


def _offer_title(inputs):
    try:
        from .salary_report import compute
        v=compute(inputs)
        pay=f"${v['pay']:,.0f}/hr" if v['pay_type']=='hourly' else f"${v['pay']:,.0f}/yr"
        return f"{pay} vs. {v['split']:g}% split"
    except (KeyError, ValueError, TypeError, OverflowError):
        return "Salary vs. Split comparison"

@require_POST
@login_required
def save_salary_comparison(request):
    if hasattr(request.user, "international_pt_profile") or not getattr(getattr(request.user, "jobseeker", None), "is_approved", False):
        return JsonResponse({"error": "A Canadian job seeker account is required to save comparisons.", "signup_url": reverse("jobseeker_signup")}, status=403)
    try:
        data = json.loads(request.body)
        if data.get("plan_type") != "salary":
            return JsonResponse({"error": "Only salary comparisons can be saved here."}, status=400)
        inputs = data.get("inputs")
        if not isinstance(inputs, dict) or not inputs or len(json.dumps(inputs)) > 6000:
            return JsonResponse({"error": "Invalid comparison."}, status=400)
        if not all(
            isinstance(k, str)
            and isinstance(v, (str, int, float, bool, type(None)))
            and (not isinstance(v, float) or math.isfinite(v))
            for k, v in inputs.items()
        ):
            return JsonResponse({"error": "Invalid comparison values."}, status=400)
        from .salary_report import compute
        compute(inputs)  # Recalculate from actual inputs; never trust client totals.
        plan = SavedCareerPlan.objects.create(
            user=request.user,
            plan_type="salary",
            title=" ".join(str(data.get("title") or _offer_title(inputs)).split())[:120],
            inputs=inputs,
        )
        return JsonResponse({"saved": True, "id": plan.pk, "url": reverse("jobseeker_dashboard")})
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid comparison data."}, status=400)


@require_GET
@login_required
def load_salary_comparison(request, pk):
    if hasattr(request.user, "international_pt_profile") or not getattr(getattr(request.user, "jobseeker", None), "is_approved", False):
        return JsonResponse({"error": "A job seeker account is required."}, status=403)
    plan = SavedCareerPlan.objects.filter(pk=pk, user=request.user, plan_type="salary").first()
    if plan is None:
        return JsonResponse({"error": "Comparison not found."}, status=404)
    return JsonResponse({"inputs": plan.inputs})
