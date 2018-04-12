from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from . import serializers, KwargsContextMixin
from ..models import Language, Book

PERMISSION_CLASSES = ()


class LanguageViewSet(ReadOnlyModelViewSet):
    queryset = Language.objects.all()
    lookup_field = "code"
    pagination_class = None
    permission_classes = ()
    serializer_class = serializers.LanguageSerializer


class BookViewSet(KwargsContextMixin, ReadOnlyModelViewSet):
    pagination_class = None
    permission_classes = PERMISSION_CLASSES

    def get_queryset(self):
        lang = self.kwargs["lang"]
        return Book.objects.filter(languages__code=lang, book_languages__hidden=False)

    def get_serializer_class(self):
        return {
            "list": serializers.BookListSerializer,
            "retrieve": serializers.BookDetailSerializer
        }.get(self.action, serializers.BookListSerializer)

    @action(detail=True, methods=['GET'])
    def content(self, request, lang, **kwargs):
        book = self.get_object()
        return Response(book.get_or_render_content(lang)[0])
