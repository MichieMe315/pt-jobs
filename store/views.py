from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

def health(request):
    return HttpResponse("store app ok")

@csrf_exempt
def webhook_placeholder(request):
    # Stripe not configured yet; accept to avoid webhook noise in logs.
    return HttpResponse("webhook disabled", status=200)
