def pricing_audience(user, product, storefront="canadian"):
    if product.audience != "both":
        return product.audience
    if user.is_authenticated:
        if getattr(user, "international_pt_profile", None):
            return "international"
        return "canadian"
    return storefront
