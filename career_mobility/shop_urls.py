from django.urls import path
from . import catalogue, store_views, views

urlpatterns = [
    path("shop/starter-bundle/<int:pk>/", store_views.claim_starter_bundle, name="mobility_claim_starter_bundle"),
    path('shop/', views.shop, name='mobility_shop'),
    path('shop/products/<slug:slug>/', catalogue.detail, name='mobility_product_detail'),
    path('shop/images/<int:pk>/pages/<int:image_pk>/', catalogue.product_gallery_image, name='mobility_product_gallery_image'),
    path('shop/images/<int:pk>/', catalogue.product_image, name='mobility_product_image'),
]
