from django import forms


class MarketingGraphicForm(forms.Form):
    GRAPHIC_CHOICES = (
        ("canada", "Canada — all active employers"),
        ("province", "Province"),
        ("city", "City"),
        ("new", "Newest employers"),
        ("top", "Top hiring employers"),
    )
    FORMAT_CHOICES = (
        ("portrait", "Instagram portrait — 1080 × 1350"),
        ("square", "Instagram square — 1080 × 1080"),
        ("landscape", "Facebook / LinkedIn — 1200 × 630"),
    )
    LIMIT_CHOICES = ((12, "12"), (16, "16"), (20, "20"), (24, "24"))

    graphic_type = forms.ChoiceField(choices=GRAPHIC_CHOICES)
    province = forms.ChoiceField(required=False)
    city = forms.ChoiceField(required=False)
    logo_limit = forms.TypedChoiceField(choices=LIMIT_CHOICES, coerce=int, initial=24)
    output_format = forms.ChoiceField(choices=FORMAT_CHOICES, initial="portrait")

    def __init__(self, *args, province_choices=(), city_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["province"].choices = [("", "Select a province")] + list(province_choices)
        self.fields["city"].choices = [("", "Select a city")] + list(city_choices)

    def clean(self):
        cleaned = super().clean()
        graphic_type = cleaned.get("graphic_type")
        if graphic_type == "province" and not cleaned.get("province"):
            self.add_error("province", "Choose a province.")
        if graphic_type == "city" and not cleaned.get("city"):
            self.add_error("city", "Choose a city.")
        return cleaned
