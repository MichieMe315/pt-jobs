from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class WebsitePage(models.Model):
    title = models.CharField(max_length=150)
    slug = models.SlugField(max_length=100, unique=True)
    body = models.TextField(help_text="Plain text. Separate paragraphs with a blank line.")
    seo_description = models.CharField(max_length=160, blank=True)
    published = models.BooleanField(default=False)
    header = models.BooleanField(default=False, verbose_name="Show in header")
    footer = models.BooleanField(default=False, verbose_name="Show in footer")
    position = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ("position", "title", "pk")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("website_page", args=[self.slug])


class SignupQuestion(models.Model):
    AUDIENCES = (("employer", "Employer"), ("jobseeker", "Job seeker"))
    TYPES = (("text", "Short text"), ("long", "Paragraph"), ("choice", "Dropdown"))
    audience = models.CharField(max_length=12, choices=AUDIENCES)
    label = models.CharField(max_length=120)
    help_text = models.CharField(max_length=250, blank=True)
    kind = models.CharField(max_length=12, choices=TYPES, default="text")
    options = models.TextField(blank=True, help_text="For dropdowns: one option per line.")
    required = models.BooleanField(default=False)
    enabled = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ("audience", "position", "pk")

    def __str__(self):
        return self.label

    def choices(self):
        return list(dict.fromkeys(line.strip() for line in self.options.splitlines() if line.strip()))

    def clean(self):
        from django.core.exceptions import ValidationError
        options = self.choices()
        if self.kind == "choice" and (not 2 <= len(options) <= 50 or any(len(option) > 150 for option in options)):
            raise ValidationError({"options": "Enter 2 to 50 distinct options, at most 150 characters each."})


class SignupAnswer(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.ForeignKey(SignupQuestion, on_delete=models.PROTECT)
    label_at_signup = models.CharField(max_length=120)
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "question"), name="board_one_signup_answer")]


class AffiliateProgram(models.Model):
    enabled = models.BooleanField(default=False)
    applications_open = models.BooleanField(default=False)
    default_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name="Default commission (%)")
    terms = models.TextField(blank=True)

    def __str__(self):
        return "Affiliate program settings"


class AffiliatePartner(models.Model):
    STATUSES = (("pending", "Pending review"), ("approved", "Approved"), ("declined", "Declined"), ("suspended", "Suspended"))
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    code = models.SlugField(max_length=48, unique=True)
    website = models.URLField(blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default="pending", db_index=True)
    rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name="Commission override (%)")
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class AffiliateReferral(models.Model):
    partner = models.ForeignKey(AffiliatePartner, on_delete=models.PROTECT)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class AffiliateCommission(models.Model):
    referral = models.ForeignKey(AffiliateReferral, on_delete=models.PROTECT)
    invoice = models.OneToOneField("board.Invoice", on_delete=models.PROTECT)
    rate = models.DecimalField(max_digits=5, decimal_places=2)
    cents = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    payment_reference = models.CharField(max_length=160, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)


class EmailDeliveryLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    recipients = models.CharField(max_length=1000)
    subject = models.CharField(max_length=255)
    outcome = models.CharField(max_length=20, choices=(("submitted", "Accepted by mail backend"), ("failed", "Failed"), ("unknown", "Result unavailable")), db_index=True)
    detail = models.CharField(max_length=100, blank=True)
