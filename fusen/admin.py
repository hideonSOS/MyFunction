from django.contrib import admin

from .models import Note, Task, Attachment


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    readonly_fields = ('name', 'content_type', 'size', 'uploaded')


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display  = ('__str__', 'user', 'tone', 'pinned', 'archived', 'updated')
    list_filter   = ('tone', 'pinned', 'archived', 'user')
    search_fields = ('body',)
    inlines       = [AttachmentInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display  = ('title', 'user', 'status', 'priority', 'due_at', 'remind_at', 'reminded')
    list_filter   = ('status', 'priority', 'tone', 'reminded', 'user')
    search_fields = ('title', 'detail')
    date_hierarchy = 'due_at'
