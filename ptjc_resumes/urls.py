from django.urls import path
from . import views
from .designs import preview as design_preview
app_name='ptjc_resumes'
urlpatterns=[path('designs/<slug:layout>/preview.pdf',design_preview,name='design_preview')]
urlpatterns += [path('',views.index,name='index'),path('new/',views.create,name='create'),path('<uuid:pk>/',views.edit,name='edit'),path('<uuid:pk>/save/',views.save,name='save'),path('<uuid:pk>/preview.pdf',views.preview,name='preview'),path('<uuid:pk>/download.pdf',views.download,name='download'),path('<uuid:pk>/delete/',views.delete,name='delete')]

from . import public
urlpatterns += [path('start/',public.start,name='start'),path('public/step/<int:step>/',public.step,name='public_step'),path('public/save/',public.save,name='public_save'),path('public/preview.pdf',public.preview,name='public_preview'),path('claim/',public.claim,name='claim'),path('<uuid:pk>/step/<int:step>/',views.edit,name='edit_step')]

from . import cards
urlpatterns += [path('cards/',cards.index,name='cards'),path('cards/new/',cards.create,name='card_create'),path('cards/<uuid:pk>/',cards.edit,name='card_edit'),path('cards/<uuid:pk>/save/',cards.save,name='card_save'),path('cards/<uuid:pk>/preview.svg',cards.preview,name='card_preview'),path('cards/<uuid:pk>/download.pdf',cards.download,name='card_download'),path('cards/<uuid:pk>/delete/',cards.delete,name='card_delete')]

