from django.contrib import admin
from django.http import Http404
from .models import InternationalActivity

def activity_report(request):
    model_admin=admin.site._registry.get(InternationalActivity)
    if model_admin is None:raise Http404
    return model_admin.changelist_view(request)
