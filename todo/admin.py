from django.contrib import admin

from .models import TodoItem


@admin.register(TodoItem)
class TodoItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'importance', 'progress', 'done', 'updated')
    list_filter  = ('done', 'importance', 'user')
    search_fields = ('title', 'memo')
