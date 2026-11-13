from django.urls import path
from . import cards

app_name = 'jobseeker_cards'
urlpatterns = [
    path('', cards.index, name='cards'),
    path('new/', cards.create, name='card_create'),
    path('<uuid:pk>/', cards.edit, name='card_edit'),
    path('<uuid:pk>/save/', cards.save, name='card_save'),
    path('<uuid:pk>/preview.svg', cards.preview, name='card_preview'),
    path('<uuid:pk>/download.pdf', cards.download, name='card_download'),
    path('<uuid:pk>/delete/', cards.delete, name='card_delete'),
]
