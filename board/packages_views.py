from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from .models import PostingPackage, Order, OrderLine

def package_list(request):
    packages = PostingPackage.objects.filter(is_active=True).order_by("order", "name")
    return render(request, "packages/package_list.html", {"packages": packages})

@transaction.atomic
def checkout_start(request, code):
    pkg = get_object_or_404(PostingPackage, code=code, is_active=True)
    # very simple, non-payment "checkout" to create an order
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        if not email:
            messages.error(request, "Please enter your email.")
        else:
            order = Order.objects.create(
                employer=None,  # can associate later if logged in
                email=email,
                provider="none",
                status="pending",
                total_cents=pkg.price_cents,
            )
            OrderLine.objects.create(order=order, package=pkg, quantity=1, price_cents=pkg.price_cents)
            return redirect("checkout_done")
    return render(request, "checkout/checkout_start.html", {"package": pkg})

def checkout_done(request):
    return render(request, "checkout/checkout_done.html")
