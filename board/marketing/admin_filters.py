from django.contrib import admin
from django.db.models import Q
from .generator import PROVINCES

class EmployerProvinceFilter(admin.SimpleListFilter):
    title='province / territory';parameter_name='province'
    def lookups(self,request,model_admin):return tuple(PROVINCES.items())
    def queryset(self,request,queryset):
        if self.value() in PROVINCES:return queryset.filter(_marketing_province=PROVINCES[self.value()])
        return queryset

class EmployerCommunityFilter(admin.SimpleListFilter):
    title='community category';parameter_name='community'
    def lookups(self,request,model_admin):
        from board.models import EmployerMarketingProfile
        return [('rural_remote','Rural and remote')]+EmployerMarketingProfile.SETTLEMENT
    def queryset(self,request,queryset):
        value=self.value()
        if value=='rural_remote':return queryset.filter(marketing_profile__settlement__in=['rural','remote'])
        if value=='unknown':return queryset.filter(Q(marketing_profile__isnull=True)|Q(marketing_profile__settlement='unknown'))
        if value in ('rural','remote','small_city','urban'):return queryset.filter(marketing_profile__settlement=value)
        return queryset

class EmployerHiringFilter(admin.SimpleListFilter):
    title='hiring activity';parameter_name='hiring'
    def lookups(self,request,model_admin):return [('active','Has active jobs'),('inactive','No active jobs')]
    def queryset(self,request,queryset):
        if self.value()=='active':return queryset.filter(_active_jobs__gt=0)
        if self.value()=='inactive':return queryset.filter(_active_jobs=0)
        return queryset
