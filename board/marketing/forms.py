from django import forms


class MarketingGraphicForm(forms.Form):
    GRAPHIC_CHOICES = (
        ("canada", "Canada — all active employers"),
        ("province", "Province"),
        ("city", "City"),
        ("new", "Newest employers"),
        ("top", "Top hiring employers"),
        ("single", "Single clinic post"),
    )
    HEADLINE_CHOICES = (
        ("top_real", "Top Employers. Real Opportunities."),
        ("leading_clinics", "Canada's Leading Clinics"),
        ("clinics_hiring", "Clinics Hiring Now"),
        ("featured", "Featured Employers"),
        ("careers", "Physiotherapy Careers"),
    )
    FORMAT_CHOICES = (
        ("square", "Instagram post — 1080 × 1080"),
        ("portrait", "Instagram portrait — 1080 × 1350"),
        ("landscape", "Facebook / LinkedIn — 1200 × 630"),
    )
    LIMIT_CHOICES = ((8, "8"), (12, "12"), (16, "16"), (20, "20"), (24, "24"))

    graphic_type = forms.ChoiceField(choices=GRAPHIC_CHOICES, initial="canada")
    headline = forms.ChoiceField(choices=HEADLINE_CHOICES, initial="top_real")
    employer = forms.ChoiceField(required=False, label="Clinic")
    province = forms.ChoiceField(required=False)
    city = forms.ChoiceField(required=False)
    logo_limit = forms.TypedChoiceField(choices=LIMIT_CHOICES, coerce=int, initial=16)
    output_format = forms.ChoiceField(choices=FORMAT_CHOICES, initial="square")

    def __init__(self, *args, province_choices=(), city_choices=(), employer_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["province"].choices = [("", "Select a province")] + list(province_choices)
        self.fields["city"].choices = [("", "Select a city")] + list(city_choices)
        self.fields["employer"].choices = [("", "Select a clinic")] + list(employer_choices)

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("graphic_type")
        if kind == "province" and not cleaned.get("province"):
            self.add_error("province", "Choose a province.")
        if kind == "city" and not cleaned.get("city"):
            self.add_error("city", "Choose a city.")
        if kind == "single" and not cleaned.get("employer"):
            self.add_error("employer", "Choose a clinic.")
        return cleaned
