from typing import List, Optional

from rest_framework import serializers

from books.models import Language, Book


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = "__all__"


class BookBaseSerializer(serializers.ModelSerializer):
    # languages = serializers.JSONField(source="languages_list", read_only=True)
    title = serializers.SerializerMethodField()
    last_modified = serializers.SerializerMethodField()

    def get_title(self, book: Book) -> str:
        lang = self.context['kwagrs']['lang']
        return book.get_title(lang)

    def get_last_modified(self, book: Book) -> dict:
        return {
            book_lang.lang.code: book_lang.last_modified
            for book_lang in book.book_languages.all()
        }

    class Meta:
        model = Book


class BookListSerializer(BookBaseSerializer):
    preview = serializers.SerializerMethodField()

    def get_preview(self, book: Book) -> Optional[dict]:
        preview = book.preview_images.first()
        if preview is None:
            return None
        return {
            "id": preview.id,
            "file": preview.file.url
        }

    class Meta:
        model = Book
        fields = ("id", "title", "preview", "last_modified")


class BookDetailSerializer(BookBaseSerializer):
    annotation = serializers.SerializerMethodField()
    previews = serializers.SerializerMethodField()

    def get_annotation(self, book: Book) -> str:
        lang = self.context['kwagrs']['lang']
        return book.get_annotation(lang)

    def get_previews(self, book: Book) -> List[dict]:
        return [
            {
                "id": img.id,
                "file": img.file.url
            } for img in book.preview_images.all()
        ]

    class Meta:
        model = Book
        fields = ("id", "title", "annotation", "previews", "last_modified")
