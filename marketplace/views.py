from django.http import HttpResponse

def marketplace_home(request):
    return HttpResponse("Marketplace app is wired.")