#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.contrib import admin
from django.utils import timezone
from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _

from opps.images.generate import image_url

from .models import Config
from .filters import ChildClassListFilter, ChannelListFilter


class MassPublishMixin(admin.ModelAdmin):
    actions = ['publish']

    def publish(modeladmin, request, queryset):
        for obj in queryset:
            obj.published = not obj.published
            obj.save()
    publish.short_description = _(u'Publish/Unpublish')


class PublisherAdmin(MassPublishMixin):
    list_display = ['title', 'channel_long_slug',
                    'date_available', 'published', 'preview_url']
    list_filter = ['date_available', 'published', ChildClassListFilter]
    search_fields = ['title', 'slug', 'channel_name']

    def in_containerboxes(self, obj):
        articleboxes = obj.articlebox_articles.all()
        if articleboxes:
            html = [u"<ul>"]
            for box in articleboxes:
                li = (u"<li><a href='/admin/articles/articlebox/{box.id}/'"
                      u" target='_blank'>{box.slug}</a></li>")
                html.append(li.format(box=box))
            html.append(u"</ul>")
            return u"".join(html)
        return _(u"This item is not in a box")
    in_containerboxes.allow_tags = True
    in_containerboxes.short_description = _(u'Article boxes')

    def image_thumb(self, obj):
        if obj.main_image:
            return u'<img width="60px" height="60px" src="{0}" />'.format(
                image_url(obj.main_image.archive.url, width=60, height=60))
        return _(u'No Image')
    image_thumb.short_description = _(u'Thumbnail')
    image_thumb.allow_tags = True

    def images_count(self, obj):
        if obj.images:
            return obj.images.count()
        else:
            return 0
    images_count.short_description = _(u'Images')

    def preview_url(self, obj):
        html = (u'<a target="_blank" href="{href}" class="viewsitelink">'
                u'<i class="icon-eye-open icon-alpha75"></i>{text}</a>')
        return html.format(
            href=obj.get_absolute_url(),
            text=_(u"View on site")
        )
    preview_url.short_description = _(u"View on site")
    preview_url.allow_tags = True


class NotUserPublishableAdmin(PublisherAdmin):
    pass


class PublishableAdmin(PublisherAdmin):
    """
    Overrides standard admin.ModelAdmin save_model method
    It sets user (author) based on data from requet.
    """
    exclude = ('user',)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = get_user_model().objects.get(pk=request.user.pk)
            obj.date_insert = timezone.now()
            obj.site = Site.objects.get(pk=settings.SITE_ID)
        obj.date_update = timezone.now()
        obj.save()


class BaseBoxAdmin(PublishableAdmin):

    prepopulated_fields = {"slug": ["name"]}
    list_display = ['name', 'channel_name', 'date_available', 'published']
    list_filter = [ChannelListFilter, 'date_available', 'published']
    raw_id_fields = ['channel', 'article']
    search_fields = ['name', 'slug', 'channel_name']

    fieldsets = (
        (_(u'Identification'), {
            'fields': ('site', 'name', 'slug')}),
        (_(u'Relationships'), {
            'fields': (('channel', 'article'),)}),
        (_(u'Publication'), {
            'classes': ('extrapretty',),
            'fields': ('published', 'date_available')}),
    )

    def queryset(self, request):
        qs = super(BaseBoxAdmin, self).queryset(request)
        try:
            # only supersusers can see queryset boxes
            if not request.user.is_superuser:
                qs = qs.filter(queryset__isnull=True)
        except:
            pass  # admin model soes not have the queryset field
        return qs


class ConfigAdmin(PublishableAdmin):
    list_display = ['key', 'app_label', 'key_group', 'channel', 'date_insert',
                    'date_available', 'published']
    list_filter = ["key", 'app_label', 'key_group', "channel", "published"]
    search_fields = ["key", "app_label", "key_group", "value"]

    raw_id_fields = ['channel', 'container']

admin.site.register(Config, ConfigAdmin)


def apply_rules(admin_class, app):
    """
    To allow overrides of admin rules for opps apps
    it uses the settings.py to load the values

    example of use:

    your project's settings.py

    OPPS_ADMIN_RULES = {
        'appname.ModelNameAdmin': {
            'fieldsets': (
                (u'Identification', {
                    'fields': ('site', 'title', 'slug')}),
            ),
            'list_display': (...),
            'list_filter': (...),
            'search_fields': (...),
            ...
        }
    }

    On appname/admin.py

    as a factory:

    from opps.core.admin import apply_rules
    ModelNameAdmin = apply_rules(ModelNameAdmin, 'appname')

    as a decorator:

    from opps.core.admin import apply_opps_rules

    @apply_opps_rules('appname')
    class ModelNameAdmin(admin.ModelAdmin):
        ...
    """

    key = "{0}.{1}".format(app, admin_class.__name__)
    OPPS_ADMIN_RULES = getattr(settings, 'OPPS_ADMIN_RULES', {})
    rules = OPPS_ADMIN_RULES.get(key)

    if not rules:
        return admin_class

    fieldsets = rules.get('fieldsets')
    if fieldsets:
        new_items = [(_(item[0]), item[1]) for item in fieldsets]
        admin_class.fieldsets = new_items

    attrs = ('list_display', 'list_filter',
             'search_fields', 'exclude', 'raw_id_fields',
             'prepopulated_fields', 'readonly_fields')

    for attr in attrs:
        to_apply = rules.get(attr)
        if to_apply:
            setattr(admin_class, attr, to_apply)

    field_overrides = rules.get('field_overrides')
    """
    Allow field attr overrides before form is rendered
    'images.ImagesAdmin': {
        'field_overrides': {
            "slug": {"help_text": "banana"}
        }
    }
    """
    if field_overrides:
        def get_form(self, request, obj=None, **kwargs):
            form = super(self.__class__, self).get_form(request, obj, **kwargs)
            if hasattr(form, 'base_fields'):
                for field, attrs in field_overrides.iteritems():
                    for attr, value in attrs.iteritems():
                        if isinstance(value, (str, unicode)):
                            value = _(value)
                        try:
                            setattr(form.base_fields[field], attr, value)
                        except:
                            pass  # KeyError base_fields[field]
            return form
        admin_class.get_form = get_form

    """
    Allow custom form for admin
    'articles.PostAdmin': {
        ...
        'form': 'yourapp.forms.PostAdminForm'
    },
    """
    form = rules.get('form')
    if form:
        try:
            _module = '.'.join(form.split('.')[:-1])
            _form = form.split('.')[-1]
            _temp = __import__(_module, globals(), locals(), [_form], -1)
            admin_class.form = getattr(_temp, _form)
        except:
            pass

    inlines = rules.get('inlines')
    if inlines:
        admin_class.inlines = []
        for inline in inlines:
            try:
                _module = '.'.join(inline.split('.')[:-1])
                _inline = inline.split('.')[-1]
                _temp = __import__(_module, globals(), locals(), [_inline], -1)
                admin_class.inlines.append(getattr(_temp, _inline))
            except:
                pass

    # TODO:
    # actions
    # override methods

    # load generic attributes
    specific_keys = list(attrs) + ['form', 'field_overrides',
                                   'fieldsets', 'inlines']
    for k, v in rules.iteritems():
        if not k in specific_keys:
            setattr(admin_class, k, v)

    return admin_class


def apply_opps_rules(app):

    def wrap(admin_class):
        admin_class = apply_rules(admin_class, app)
        return admin_class

    return wrap

apply_opps_rules.__doc__ = apply_rules.__doc__
