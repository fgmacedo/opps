#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.contrib import admin


class PublishableAdmin(admin.ModelAdmin):
    """
    Overrides standard admin.ModelAdmin save_model method
    It sets user (author) based on data from requet.
    """
    list_display = ['title', 'date_available', 'published']
    list_filter = ['date_available', 'published']
    search_fields = ['title', 'slug', 'headline']
    exclude = ('user',)

    def save_model(self, request, obj, form, change):
        if getattr(obj, 'pk', None) is None:
            obj.user = request.user
        obj.save()
