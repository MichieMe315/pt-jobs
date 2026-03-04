from django.http import HttpResponse

def public_teaser(request):
    return HttpResponse("International candidates teaser is wired.")