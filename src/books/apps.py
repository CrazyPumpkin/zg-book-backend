import logging
import os
from typing import Callable

import django.dispatch
import psutil
from django.apps import AppConfig
from django.db import DatabaseError
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

logger = logging.getLogger(__name__)
f_none = lambda *args, **kwargs: None

# sender - Book model
# book - Book instance
# lang - Language instance or lang code
# source - Model which cause book update
book_changed = django.dispatch.Signal(providing_args=["book", "lang", "source"])


class BooksConfig(AppConfig):
    name = 'books'
    verbose_name = _("Книги")

    def get_run_type(self):
        """
        Get type of django instance

        :return: server | <manage command> | <celery command>
        """
        p = psutil.Process(os.getpid())
        cmdline = p.cmdline()
        if cmdline[0].endswith("wsgi"):
            return "server"
        if cmdline[1].endswith("manage.py"):
            if cmdline[2] == "runserver":
                return "server"
            return cmdline[2].strip()
        if cmdline[1].endswith("celery"):
            return cmdline[2]
        return None

    def ready(self):
        from books.tasks import update_book
        from books.validators import BookValidator

        Book = self.get_model('Book')
        Image = self.get_model('Image')
        TextFragment = self.get_model('TextFragment')
        BookLanguage = self.get_model('BookLanguage')

        @receiver(book_changed, weak=False, dispatch_uid="on_book_changed")
        def on_book_changed(sender, book, lang, source, **kwargs):
            logger.info(f"<Signal (book_changed) sender='{sender}' book='{book}' lang='{lang}'>")
            if book is None:
                return
            if lang:
                lang_code = lang if isinstance(lang, str) else lang.code
                book_lang = BookLanguage.objects.get(book=book, lang__code=lang_code)
                if not book_lang.hidden:
                    update_book.delay(book.id, lang_code)
            else:
                for code in book.languages.filter(booklanguage__hidden=False).values_list("code", flat=True):
                    update_book.delay(book.id, code)

        run_type = self.get_run_type()

        # Enable signals and cache only on wsgi and runserver
        if run_type == "server":
            self.connect(
                Book,
                signals=(post_save,),
                book_getter=lambda self: self,
                lang_getter=f_none
            )
            self.connect(
                Image,
                book_getter=lambda self: self.book,
                lang_getter=f_none
            )
            self.connect(
                TextFragment,
                book_getter=lambda self: self.book,
                lang_getter=lambda self: self.lang
            )

            # Initialize cache
            try:
                for book in Book.objects.all():
                    for book_lang in book.book_languages.all():
                        code = book_lang.lang.code
                        book_lang.validation_errors = [error.to_json() for error in BookValidator(book, code)]
                        book_lang.save()
                        msg = f'Book "{book.get_title(code)}" ({code}) validated.' \
                              f' {len(book_lang.validation_errors)} errors found.'
                        if book_lang.validation_errors:
                            logger.warning(msg)
                        else:
                            logger.info(msg)

                        update_book.delay(book.id, code, keep_timestamp=True)
            except DatabaseError:
                pass

    def connect(
            self, model,
            book_getter: Callable[[object], object], lang_getter: Callable[[object], object],
            condition: Callable[[object], bool] = None, signals=(post_save, pre_delete)
    ):
        Book = self.get_model('Book')

        @receiver(signals, sender=model, weak=False, dispatch_uid=f"book_update:{model._meta.model_name}:on_change")
        def on_change(sender, instance, *args, **kwargs):
            logger.info(f"<Signal {signals}> sender='{sender}' instance='{instance}'")
            if not (condition is None or condition(instance)):
                return
            book = book_getter(instance)
            if book:
                lang = lang_getter(instance)
                book_changed.send(sender=Book, book=book, lang=lang, source=model)
