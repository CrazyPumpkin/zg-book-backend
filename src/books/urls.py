from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api import api_views as views
from .api.admin import api_views as admin_views

admin_router = DefaultRouter()
admin_router.register("authors", admin_views.AuthorAdminViewSet, base_name="Admin authors")
admin_router.register("books", admin_views.BookAdminViewSet, base_name="Admin books")

admin_book_router = DefaultRouter()
admin_book_router.register("image", admin_views.ImageAdminViewSet, base_name="Admin books -> images")
admin_book_router.register("textfrags", admin_views.TextFragmentAdminViewSet, base_name="Admin books -> textframentes")
admin_book_router.register("langs", admin_views.BookLanguageViewSet, base_name="Admin books -> langs")

books_router = DefaultRouter()
books_router.register("lang", views.LanguageViewSet)

books_with_lang_router = DefaultRouter()
books_with_lang_router.register("", views.BookViewSet, base_name="Books with lang")

urlpatterns = [
    path('admin/', include(admin_router.urls)),
    path('admin/books/<int:book_id>/', include(admin_book_router.urls)),
    path('books/', include(books_router.urls)),
    path('books/<slug:lang>/', include(books_with_lang_router.urls))
]
