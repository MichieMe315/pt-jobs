from django import template
from career_mobility.models import SavedCareerPlan
register = template.Library()

@register.inclusion_tag("career_mobility/jobseeker_salary_plans.html", takes_context=True)
def jobseeker_salary_plans(context):
    user = context["request"].user
    plans = SavedCareerPlan.objects.none()
    if user.is_authenticated and hasattr(user, "jobseeker"):
        plans = SavedCareerPlan.objects.filter(user=user, plan_type="salary").order_by("-created_at")[:10]
    return {"plans": plans}
