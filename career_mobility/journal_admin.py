from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .journal_content import worksheets
from .models import JournalTemplate


class JournalTemplateForm(forms.ModelForm):
    class Meta:
        model = JournalTemplate
        exclude = ("content",)
        widgets = {"default_colour": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        track = self.instance.key.removesuffix("-physio-journal")
        stock = self.instance.content or worksheets(track)
        for i, sheet in enumerate(stock):
            self.fields[f"sheet_{i}_title"] = forms.CharField(label="Page title", max_length=140, initial=sheet["title"])
            self.fields[f"sheet_{i}_intro"] = forms.CharField(label="Introduction", max_length=500, widget=forms.Textarea(attrs={"rows": 2}), initial=sheet["intro"])
            for j, field in enumerate(sheet["fields"]):
                self.fields[f"sheet_{i}_{j}_label"] = forms.CharField(label=f"Writing area {j+1} — heading", max_length=120, initial=field["label"])
                self.fields[f"sheet_{i}_{j}_prompt"] = forms.CharField(label=f"Writing area {j+1} — guidance", max_length=500, widget=forms.Textarea(attrs={"rows": 2}), initial=field["prompt"])

    def save(self, commit=True):
        record = super().save(commit=False)
        record.content = [{
            "title": self.cleaned_data[f"sheet_{i}_title"],
            "intro": self.cleaned_data[f"sheet_{i}_intro"],
            "fields": [{
                "label": self.cleaned_data[f"sheet_{i}_{j}_label"],
                "prompt": self.cleaned_data[f"sheet_{i}_{j}_prompt"],
            } for j in range(4)],
        } for i in range(6)]
        if commit:
            record.save()
        return record


@admin.register(JournalTemplate)
class JournalTemplateAdmin(admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    form = JournalTemplateForm
    list_display = ("title", "default_design", "default_colour", "editor_link")
    readonly_fields = ("key", "editor_link")
    search_fields = ("title", "key")

    def get_fieldsets(self, request, obj=None):
        groups = [(None, {"fields": ("key", "title", "subtitle", "default_design", "default_colour", "editor_link")})]
        if obj:
            for i in range(6):
                fields = [f"sheet_{i}_title", f"sheet_{i}_intro"]
                for j in range(4):
                    fields.extend((f"sheet_{i}_{j}_label", f"sheet_{i}_{j}_prompt"))
                groups.append((f"Worksheet {i+1}", {"fields": fields, "classes": ("collapse",)}))
        return groups

    def get_form(self, request, obj=None, **kwargs):
        if obj:
            # Declare worksheet fields before Django validates the admin fieldsets.
            stock = obj.content or worksheets(obj.key.removesuffix("-physio-journal"))
            declared = {}
            for i, sheet in enumerate(stock):
                declared[f"sheet_{i}_title"] = forms.CharField(label="Page title", max_length=140)
                declared[f"sheet_{i}_intro"] = forms.CharField(label="Introduction", max_length=500, widget=forms.Textarea(attrs={"rows": 2}))
                for j, field in enumerate(sheet["fields"]):
                    declared[f"sheet_{i}_{j}_label"] = forms.CharField(label=f"Writing area {j+1} — heading", max_length=120)
                    declared[f"sheet_{i}_{j}_prompt"] = forms.CharField(label=f"Writing area {j+1} — guidance", max_length=500, widget=forms.Textarea(attrs={"rows": 2}))
            kwargs["form"] = type("ConfiguredJournalForm", (self.form,), declared)
        return super().get_form(request, obj, **kwargs)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Preview")
    def editor_link(self, obj):
        if not obj:
            return "Save the journal first."
        return format_html('<a href="{}" target="_blank" rel="noopener">Open editable sample ↗</a>', reverse("mobility_editable_preview", args=[obj.key]))
