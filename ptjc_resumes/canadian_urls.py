from django.urls import path

from . import canadian, canadian_editor
app_name = "ptjc_canadian_resumes"
urlpatterns = [
    path('', canadian.index, name='canadian_index'),
    path('start/', canadian_editor.start, name='canadian_start'),
    path('public/save/', canadian_editor.guest_save, name='canadian_guest_save'),
    path('public/preview.pdf', canadian_editor.guest_preview, name='canadian_guest_preview'),
    path('claim/', canadian_editor.claim, name='canadian_claim'),
    path('<uuid:pk>/save/', canadian_editor.saved_save, name='canadian_save'),
    path('new/', canadian.create, name='canadian_create'),
    path('<uuid:pk>/', canadian.edit, name='canadian_edit'),
    path('<uuid:pk>/preview.pdf', canadian.export, {'preview': True}, name='canadian_preview'),
    path('<uuid:pk>/download.pdf', canadian.export, name='canadian_download'),
    path('<uuid:pk>/delete/', canadian.delete, name='canadian_delete'),
]
