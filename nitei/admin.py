from django.contrib import admin
from .models import Title, WorkEntry


@admin.register(Title)
class TitleAdmin(admin.ModelAdmin):
    list_display = ('id', 'date_from', 'date_to', 'venue', 'title')
    list_filter  = ('venue',)
    ordering     = ('date_from',)


@admin.register(WorkEntry)
class WorkEntryAdmin(admin.ModelAdmin):
    list_display = ('sheet_index', 'section_index', 'day_index', 'status')
    list_filter  = ('status',)
