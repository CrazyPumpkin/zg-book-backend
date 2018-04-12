from django import forms
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from . import models


class BookImageInline(admin.TabularInline):
    class Form(forms.ModelForm):
        "Override form to set default type"
        class Meta:
            model = models.Image
            fields = ("position", "file",)

        def save(self, commit=True):
            self.instance.type = "preview"
            return super().save(commit)

    model = models.Image
    extra = 0
    form = Form
    fields = ("position", "file", "preview",)
    readonly_fields = ("preview",)

    def preview(self, obj):
        return mark_safe(f'<img src="{obj.file.url}" style="max-width: 100px; max-height: 100px"/>')

    preview.short_description = _("Превью")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(type="preview")


class BookLangInline(admin.TabularInline):
    model = models.BookLanguage
    extra = 0


class BookTitleInline(admin.TabularInline):
    class Form(forms.ModelForm):
        "Override form to set default type and change text field type"
        text = forms.CharField(max_length=255, label=models.TextFragment._meta.get_field("text").verbose_name)

        class Meta:
            model = models.TextFragment
            fields = ['lang', 'text']

        def save(self, commit=True):
            self.instance.type = "title"
            return super().save(commit)

    model = models.TextFragment
    extra = 0
    form = Form
    verbose_name_plural = _("Название")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(type="title")


class BookAnnotationInline(admin.TabularInline):
    class Form(forms.ModelForm):
        "Override form to set default type"
        class Meta:
            model = models.TextFragment
            fields = ['lang', 'text']

        def save(self, commit=True):
            self.instance.type = "ann"
            return super().save(commit)

    model = models.TextFragment
    extra = 0
    form = Form
    verbose_name_plural = _("Аннотация")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(type="ann")


@admin.register(models.Book)
class BookAdmin(admin.ModelAdmin):
    inlines = (BookLangInline, BookTitleInline, BookAnnotationInline, BookImageInline)


@admin.register(models.Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("code", "name")


@admin.register(models.Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("name", "age", "country", "link")


@admin.register(models.Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ("id", "file", "book", "type")
    readonly_fields = ("id",)


@admin.register(models.TextFragment)
class TextFragmentAdmin(admin.ModelAdmin):
    list_display = ("book", "uuid", "lang", "type")
