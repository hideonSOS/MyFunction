from django.contrib import admin

from .models import LineNotification, LineTarget


@admin.register(LineTarget)
class LineTargetAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'target_id', 'created')
    list_filter  = ('kind',)
    search_fields = ('name', 'target_id')


@admin.register(LineNotification)
class LineNotificationAdmin(admin.ModelAdmin):
    list_display = ('date', 'time', 'message', 'target', 'sent', 'sent_at', 'error')
    list_filter  = ('sent', 'target')
    search_fields = ('message',)
