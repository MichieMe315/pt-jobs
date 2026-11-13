from django.urls import path
from django.views.generic import RedirectView
from . import public_previews as previews, designs

from .editable_products import demo, choose_journal

urlpatterns = [
    path("shop/designs/<int:pk>/save/", designs.save, name="mobility_save_design"),
    path("shop/designs/<int:pk>/activity/", designs.activity, name="mobility_design_activity"),
    path("shop/editor/journal/", choose_journal, name="mobility_choose_journal"),
    path("shop/editor/<slug:key>/", demo, name="mobility_editable_preview"),
    path("previews/editable/<slug:key>/", demo),
    path("shop/card-studio/", previews.try_cards, name="mobility_try_cards"),
    path("shop/card-studio/save/", previews.keep_card, name="mobility_keep_card"),
    path("shop/card-studio/claim/", previews.claim_card, name="mobility_claim_card"),
    path("shop/card-studio/render.svg", previews.try_card_svg, name="mobility_try_card_svg"),
    path('previews/', RedirectView.as_view(pattern_name='mobility_shop'), name='mobility_public_previews'),
    path('previews/resume/<slug:layout>.pdf', previews.resume_preview, name='mobility_public_resume_preview'),
    path('previews/card-studio/', previews.try_cards),
    path('previews/card-studio/render.svg', previews.try_card_svg),
    path('previews/card/<slug:design>/<slug:side>.svg', previews.card_preview, name='mobility_public_card_preview'),
]
