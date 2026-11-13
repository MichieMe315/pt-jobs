from .models import ResumeAdPlacement

def placement():return ResumeAdPlacement.objects.filter(enabled=True).order_by('pk').first()

def international_placement():
    return ResumeAdPlacement.objects.filter(enabled=True,show_on_international_planner=True).order_by('pk').first()
