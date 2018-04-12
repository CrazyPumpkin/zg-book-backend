import logging
from itertools import chain
from pathlib import Path
from typing import Iterable, Optional, List, Any, Dict, Tuple
from uuid import uuid4

import iso639
from django.contrib.postgres.fields import JSONField
from django.core.cache import cache
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from .utils import validate_svg
from .validators import JsonSchemaValidator

SCHEMA_DIR = (Path(__file__) / ".." / "schemes").resolve()

logger = logging.getLogger(__name__)


class Language(models.Model):
    LANG_CHOICES = sorted(
        (
            (lang.alpha2, f"{lang.alpha2} - {lang.name}")
            for lang in iso639.languages
            if lang.alpha2
        ),
        key=lambda item: item[0]
    )

    code = models.CharField(max_length=2, choices=LANG_CHOICES, unique=True, verbose_name=_("Код ISO-639-1"))
    name = models.CharField(max_length=255, verbose_name=_("Название"))
    flag = models.FileField(upload_to="flag/", validators=[validate_svg], verbose_name=_("Флаг"),
                            help_text=_("*.svg"))

    class Meta:
        verbose_name = _("Язык")
        verbose_name_plural = _("Языки")
        ordering = ("code",)

    def __str__(self):
        return f"{self.code} - {self.name}"


class BookLanguage(models.Model):
    """
    :param validation_errors: Results of last BookValidator call
    """
    lang = models.ForeignKey('Language', on_delete=models.CASCADE, verbose_name=_("Язык"))
    book = models.ForeignKey('Book', on_delete=models.CASCADE, related_name="book_languages", verbose_name=_("Книга"))
    last_modified = models.DateTimeField(default=timezone.now, verbose_name=_("Дата последнего изменения"))
    hidden = models.BooleanField(default=True, blank=True, verbose_name=_("Скрыт"))
    validation_errors = JSONField(default=[], blank=True, verbose_name=_("Ошибки валидации"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.old_hidden = self.hidden
        self.old_last_modified = self.last_modified

    @property
    def is_valid(self):
        return not self.validation_errors

    class Meta:
        verbose_name = _("Перевод")
        verbose_name_plural = _("Переводы")
        ordering = ("-last_modified",)
        unique_together = ("lang", "book")

    def __str__(self):
        return f"{self.book} ({self.lang.name})"


class Book(models.Model):
    position = models.IntegerField(default=0, blank=True, verbose_name=_("Позиция"))

    structure = JSONField(default=[], blank=True, validators=[JsonSchemaValidator(SCHEMA_DIR / "book_structure.json")],
                          verbose_name=_("Структура"))

    author = models.ForeignKey('Author', on_delete=models.SET_NULL, null=True, verbose_name=_("Автор"))

    languages = models.ManyToManyField('Language', through='BookLanguage', verbose_name=_("Доступные языки"))

    @property
    def languages_list(self) -> Iterable[str]:
        return list(self.languages.values_list("code", flat=True))

    @languages_list.setter
    def languages_list(self, value: Iterable[str]):
        BookLanguage.objects.filter(book=self).delete()
        for lang in value:
            BookLanguage.objects.create(lang=Language.objects.get(code=lang), book=self)

    @property
    def preview_images(self):
        return self.images.filter(type="preview")

    @property
    def content_images(self):
        return self.images.filter(type="body")

    languages_list.fget.short_description = _("Список доступных языков")

    class Meta:
        verbose_name = _("Книга")
        verbose_name_plural = _("Книги")
        ordering = ("position", "id")

    def __str__(self):
        return self.get_title("en") or "?"

    def get_title(self, lang: str) -> str:
        return getattr(self.textfragment_set.filter(type="title", lang__code=lang).first(), 'text', None)

    def get_annotation(self, lang: str) -> str:
        return getattr(self.textfragment_set.filter(type="ann", lang__code=lang).first(), 'text', None)

    def get_cache_key(self, lang: str) -> str:
        return f"django:books:book:{self.id}:{lang}"

    def get_or_render_content(self, lang: str, cache_read=True, cache_write=True) -> Tuple[Optional[List[dict]], bool]:
        """
        Return cached result of render_content()

        :return: (content_list, read_from_cache)
        """
        assert not (cache_read and not cache_write), "Cannot use cache without write access"
        if not self.languages.filter(code=lang).exists():
            return None, False

        key = self.get_cache_key(lang)
        if cache_read:
            item = cache.get(key)
            if item:
                return item, True

        content = self.render_content(lang)
        if content and cache_write:
            cache.set(key, content)
        return content, False

    def render_content(self, lang, cleanup=False) -> Optional[List[dict]]:
        structure: List[Dict[str, Any]] = self.structure
        text_fragments: Dict[str, TextFragment] = {
            str(tf.uuid).replace("-", ""): tf
            for tf in self.textfragment_set.filter(type="body", lang__code=lang)
        }
        images: Dict[int, Image] = {
            img.id: img
            for img in self.content_images.all()
        }

        content = []
        for item in structure:
            if item["type"] == "textfragment":
                fragment = text_fragments.pop(item["id"], None)
                if fragment is None:
                    logger.warning(f"Fragment {item['id']}:{lang} not found for book {self.id}")
                    continue
                content.append({
                    "type": "textfragment",
                    "text": fragment.text
                })

            elif item["type"] == "image":
                image = images.pop(item["id"], None)
                if image is None:
                    logger.warning(f"Image {item['id']} not found for book {self.id}")
                    continue

                title = text_fragments.pop(item["title"], None)
                if title is None:
                    logger.warning(f"Title of image {item['id']} not found for book {self.id}")
                    continue

                author = image.author
                data = {
                    "type": "image",
                    "id": image.id,
                    "url": image.file.url,
                    "title": title.text,
                    "author": {
                        "name": author.name,
                        "country": author.country_list,
                        "link": author.link
                    } if author else None,
                    "content": []
                }

                for subitem in item["content"]:
                    if subitem["type"] == "textfragment":
                        fragment = text_fragments.pop(subitem["id"], None)
                        if fragment is None:
                            logger.warning(f"Fragment {item['id']}:{lang} not found for book {self.id}")
                            continue
                        data["content"].append({
                            "type": "textfragment",
                            "text": fragment.text
                        })

                    elif item["type"] == "image":
                        image = images.pop(subitem["id"], None)
                        if image is None:
                            logger.warning(f"Image {item['id']} not found for book {self.id}")
                            continue
                        data["content"].append({
                            "type": "image",
                            "id": image.id,
                            "url": image.file.url
                        })

                content.append(data)
        if text_fragments or images:
            if cleanup:
                for item in chain(text_fragments.values(), images.values()):
                    item.delete()
            else:
                logger.warning(f'Book #{self.id} "{self.get_title(lang)}" (lang {lang}) has unused content items.'
                               ' Run .render_content(..., cleanup=True) to delete them.')
        return content


class Author(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Имя"))
    country = models.CharField(max_length=255, verbose_name=_("Страна(ы)"),
                               help_text=_("Список через запятую [ISO-3166-1]"))
    link = models.URLField(blank=True, verbose_name=_("Страница на сайте"))
    age = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name=_("Возраст"))

    @property
    def country_list(self) -> Iterable[str]:
        return sorted(filter(None, map(str.strip, self.country.split(","))))

    @country_list.setter
    def country_list(self, value: Iterable[str]):
        self.country = ",".join(sorted(filter(None, map(str.strip, value))))

    country_list.fget.short_description = _("Список стран")

    class Meta:
        verbose_name = _("Автор")
        verbose_name_plural = _("Авторы")

    def __str__(self):
        return _("{},  {} лет").format(self.name, self.age)


class Image(models.Model):
    TYPES = (
        ("preview", _("Превью книги")),
        ("body", _("Содержимое")),
    )

    file = models.ImageField(upload_to="img/", verbose_name=_("Файл изображения"))
    position = models.IntegerField(default=0, blank=True, verbose_name=_("Позиция"))
    type = models.CharField(max_length=10, choices=TYPES, verbose_name=_("Тип"))

    book = models.ForeignKey('Book', on_delete=models.CASCADE, related_name="images", verbose_name=_("Книга"))
    author = models.ForeignKey('Author', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Автор"))

    class Meta:
        verbose_name = _("Изображение")
        verbose_name_plural = _("Изображения")

    def __str__(self):
        a = f'{self.book.get_title("eng")}: ' if self.book else ""
        b = _("изобр. от {}").format(self.author.name) if self.author else str(self.file)
        return a + b


class TextFragment(models.Model):
    TYPES = (
        ("title", _("Заглавие")),
        ("ann", _("Анотация")),
        ("body", _("Содержимое")),
    )

    uuid = models.UUIDField(unique=False, default=uuid4, blank=True, verbose_name=_("UUID"))
    text = models.TextField(verbose_name=_("Текст"))

    type = models.CharField(max_length=10, choices=TYPES, default="body", verbose_name=_("Тип"))

    lang = models.ForeignKey('Language', on_delete=models.CASCADE, verbose_name=_("Язык"))
    book = models.ForeignKey('Book', on_delete=models.CASCADE, verbose_name=_("Книга"))

    class Meta:
        verbose_name = _("Фрагмент текста")
        verbose_name_plural = _("Фрагменты текста")
        ordering = ("book", "lang", "uuid")
        unique_together = (("lang", "uuid"),)

    def __str__(self):
        return f"{self.book.get_title(self.lang.code)}: {self.get_type_display()} <{self.lang}> #{str(self.uuid)[:8]}..."
