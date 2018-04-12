from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from books.tasks import update_book
from books.validators import BookValidator
from . import serializers
from ... import models

PERMISSION_CLASSES = (IsAdminUser,)


class AuthorAdminViewSet(ModelViewSet):
    """
    Get/create/update/delete author(s)
    """
    permission_classes = PERMISSION_CLASSES
    pagination_class = None
    queryset = models.Author.objects.all()
    serializer_class = serializers.AuthorSerializer


class BookAdminViewSet(ModelViewSet):
    """
    Get/create/update/delete book(s)
    """
    permission_classes = PERMISSION_CLASSES
    pagination_class = None
    queryset = models.Book.objects.all()

    def get_serializer_class(self):
        return {
            "list": serializers.BookAdminListSerializer,
            "create": serializers.BookAdminListSerializer,

            "retrieve": serializers.BookAdminDetailSerializer,
            "update": serializers.BookAdminDetailSerializer,
            "partial_update": serializers.BookAdminDetailSerializer,
        }.get(self.action, serializers.BookAdminListSerializer)

    @action(detail=True, methods=['GET'])
    def validate(self, request, **kwargs):
        """
        Validate BookLanguage and save and return results of valdiation
        """
        book: models.Book = self.get_object()
        res = {}
        book_lang: models.BookLanguage
        for book_lang in book.book_languages.all():
            code = book_lang.lang.code
            book_lang.validation_errors = res[code] = [error.to_json() for error in BookValidator(book, code)]
            book_lang.save()

        return Response(res)


class BookLanguageViewSet(ModelViewSet):
    """
    Get/create/update/delete language metadata of book
    """
    permission_classes = PERMISSION_CLASSES
    pagination_class = None
    queryset = models.BookLanguage.objects.all()
    serializer_class = serializers.BookLanguageSerializer

    def filter_queryset(self, queryset):
        return queryset.filter(book_id=self.kwargs["book_id"])

    def perform_create(self, serializer):
        return serializer.save(book_id=int(self.kwargs["book_id"]))

    def perform_update(self, serializer):
        instance: models.BookLanguage = serializer.save()
        # If book is published
        if not instance.hidden and instance.hidden != instance.old_hidden:
            update_book.delay(instance.book_id, instance.lang.code)


class ImageAdminViewSet(ModelViewSet):
    """
    Get/create/update/delete image(s) of book
    """
    permission_classes = PERMISSION_CLASSES
    parser_classes = (MultiPartParser, FormParser,)
    pagination_class = None
    queryset = models.Image.objects.all()
    serializer_class = serializers.ImageSerializer

    def filter_queryset(self, queryset):
        return queryset.filter(book_id=self.kwargs["book_id"])

    def perform_create(self, serializer):
        return serializer.save(book_id=int(self.kwargs["book_id"]))


class TextFragmentAdminViewSet(ModelViewSet):
    """
    Get/create/update/delete TextFragment(s) of book (title, annotation, content)
    """
    permission_classes = PERMISSION_CLASSES
    parser_classes = (MultiPartParser, FormParser,)
    pagination_class = None
    queryset = models.TextFragment.objects.all()
    serializer_class = serializers.TextFragmentSerializer

    def filter_queryset(self, queryset):
        return queryset.filter(book_id=self.kwargs["book_id"])

    def perform_create(self, serializer):
        return serializer.save(book_id=int(self.kwargs["book_id"]))
