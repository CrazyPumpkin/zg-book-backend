import logging

from celery.utils.log import get_task_logger
from django.utils import timezone

from books.models import Book
from zg_book_project.celery import app

logger = get_task_logger('celery.tasks')  # type: logging.Logger


@app.task(bind=True, max_retries=1)
def update_book(self, book_id, lang_code, keep_timestamp=False):
    # TODO: Add redis lock
    book = Book.objects.get(id=book_id)
    content, from_cache = book.get_or_render_content(lang_code, cache_read=False)
    if keep_timestamp:
        logger.info(f'Book "{book.get_title(lang_code)}" ({lang_code}) loaded')
    else:
        book_lang = book.book_languages.get(lang__code=lang_code)
        book_lang.last_modified = timezone.now()
        book_lang.save()
        logger.info(f'Book "{book.get_title(lang_code)}" ({lang_code}) updated')
    return content
