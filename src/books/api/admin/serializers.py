import operator
from typing import Optional, List

from rest_framework import serializers

from ... import models


class AuthorSerializer(serializers.ModelSerializer):
    country_list = serializers.JSONField()

    class Meta:
        model = models.Author
        fields = ("id", "name", "country_list", "link", "age")


class BookLanguageSerializer(serializers.ModelSerializer):
    class LangCodesField(serializers.RelatedField):
        field = "code"

        def to_representation(self, lang: models.Language):
            return lang.code

        def to_internal_value(self, code):
            return models.Language.objects.get(code=code)

    lang = LangCodesField(queryset=models.BookLanguage.objects.all())

    class Meta:
        model = models.BookLanguage
        fields = ("id", "lang", "last_modified", "hidden", "is_valid")
        read_only_fields = ("id", "last_modified", "is_valid")


class BookAdminListSerializer(serializers.ModelSerializer):
    langs = serializers.JSONField(read_only=True, source="languages_list")
    title = serializers.SerializerMethodField()
    preview = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()

    def get_title(self, book: models.Book) -> str:
        return book.get_title("en")

    def get_preview(self, book: models.Book) -> Optional[dict]:
        preview = book.preview_images.first()
        if preview is None:
            return None
        return {
            "id": preview.id,
            "file": preview.file.url
        }

    def get_is_valid(self, book: models.Book):
        """
        True if ALL languages is valid
        """
        return all(map(operator.not_, book.book_languages.values_list("validation_errors", flat=True)))

    class Meta:
        model = models.Book
        fields = ("id", "title", "position", "langs", "author", "preview", "is_valid")


class BookAdminDetailSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    previews = serializers.SerializerMethodField()
    langs = BookLanguageSerializer(read_only=True, source="book_languages", many=True)

    get_title = BookAdminListSerializer.get_title

    def get_previews(self, book: models.Book) -> List[dict]:
        return [
            {
                "id": img.id,
                "file": img.file.url
            } for img in book.preview_images.all()
        ]

    class Meta:
        model = models.Book
        fields = ("id", "title", "position", "langs", "structure", "author", "previews")


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Image
        exclude = ("book",)


class TextFragmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TextFragment
        exclude = ("book",)
