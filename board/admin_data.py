from django.contrib.admin.views.main import ChangeList
from django.http import HttpResponseRedirect, QueryDict
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.urls import path, reverse
from django.views.decorators.http import require_POST
from import_export import formats, resources
from import_export.admin import ImportExportModelAdmin

from .models import Employer, Job, JobSeeker


class EmployerResource(resources.ModelResource):
    class Meta:
        model = Employer
        fields = ('user', 'email', 'name', 'company_name', 'company_description', 'description',
                  'phone', 'website', 'location', 'created_at')
        import_id_fields = ('user',)
        clean_model_instances = True
        use_transactions = True
        skip_unchanged = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields['created_at'].readonly = True


class JobSeekerResource(resources.ModelResource):
    class Meta:
        model = JobSeeker
        fields = ('user', 'email', 'first_name', 'last_name', 'position_desired', 'current_location',
                  'registered_in_canada', 'opportunity_type', 'open_to_relocate', 'relocate_where',
                  'require_sponsorship', 'seeking_immigration', 'created_at')
        import_id_fields = ('user',)
        clean_model_instances = True
        use_transactions = True
        skip_unchanged = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields['created_at'].readonly = True


class JobResource(resources.ModelResource):
    class Meta:
        model = Job
        fields = ('id', 'employer', 'title', 'description', 'location', 'job_type', 'compensation_type',
                  'compensation_min', 'compensation_max', 'apply_via', 'apply_email', 'apply_url',
                  'posting_date', 'expiry_date', 'relocation_assistance', 'source', 'is_active')
        import_id_fields = ('id',)
        clean_model_instances = True
        use_transactions = True
        skip_unchanged = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields['is_active'].readonly = True

    def after_init_instance(self, instance, new, row, **kwargs):
        if new:
            instance.is_active = False


class SafeCSV(formats.base_formats.CSV):
    def export_data(self, dataset, **kwargs):
        rows = []
        for row in dataset:
            rows.append([
                "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value
                for value in row
            ])
        from tablib import Dataset
        return super().export_data(Dataset(*rows, headers=dataset.headers), **kwargs)


RECORD_PAGE_SIZES = (25, 50, 100)


class RecordsChangeList(ChangeList):
    def get_filters_params(self, params=None):
        filters = super().get_filters_params(params)
        filters.pop("per_page", None)
        return filters

    def get_results(self, request):
        rows = request.GET.get("per_page")
        if rows in {str(size) for size in RECORD_PAGE_SIZES}:
            self.list_per_page = int(rows)
        return super().get_results(request)


class RecordsDataAdmin(ImportExportModelAdmin):
    formats = [SafeCSV]
    change_list_template = 'admin/board/records_change_list.html'
    import_template_name = 'admin/board/records_import.html'
    extra_columns = ()

    def get_changelist(self, request, **kwargs):
        return RecordsChangeList

    def has_import_permission(self, request):
        return self.has_add_permission(request) and self.has_change_permission(request)

    def has_export_permission(self, request):
        return self.has_view_permission(request)

    def available_columns(self):
        return tuple(dict.fromkeys((*self.list_display, *self.extra_columns)))

    def get_list_display(self, request):
        selected = request.session.get(f'ptjc-columns:{self.opts.label_lower}')
        allowed = self.available_columns()
        return ('id', *(x for x in selected if x in allowed and x != 'id')) if selected else super().get_list_display(request)

    def get_list_display_links(self, request, list_display):
        return tuple(x for x in self.list_display_links if x in list_display) or ('id',)

    def changelist_view(self, request, extra_context=None):
        chosen = self.get_list_display(request)
        options = []
        for name in self.available_columns():
            fn = getattr(self, name, None)
            label = getattr(fn, 'short_description', None)
            if label is None:
                try:
                    label = self.opts.get_field(name).verbose_name
                except Exception:
                    label = name.replace('_', ' ')
            options.append((name, str(label).capitalize(), name in chosen))
        return super().changelist_view(request, extra_context={
            **(extra_context or {}), 'column_options':options, 'row_sizes':RECORD_PAGE_SIZES,
            'column_save_url':reverse(f'admin:{self.opts.app_label}_{self.opts.model_name}_columns'),
        })

    def get_urls(self):
        return [
            path('columns/', self.admin_site.admin_view(require_POST(self.save_columns)),
                 name=f'{self.opts.app_label}_{self.opts.model_name}_columns'),
            *super().get_urls(),
        ]

    def save_columns(self, request):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        key = f'ptjc-columns:{self.opts.label_lower}'
        if 'reset' in request.POST:
            request.session.pop(key, None)
        else:
            selected = set(request.POST.getlist('columns'))
            request.session[key] = ['id', *(x for x in self.available_columns() if x in selected and x != 'id')]
        messages.success(request, 'Columns updated.')
        url = reverse(f'admin:{self.opts.app_label}_{self.opts.model_name}_changelist')
        query = QueryDict(request.POST.get('list_query', ''), mutable=True)
        for key in ('p', 'o', 'all', 'e'):
            query.pop(key, None)
        return HttpResponseRedirect(url + ('?' + query.urlencode() if query else ''))
