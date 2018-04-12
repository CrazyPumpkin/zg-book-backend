import operator
from functools import reduce
from pathlib import Path
from random import choice, randint, sample
from typing import Iterable, Tuple, Union, List
from uuid import UUID

import requests
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .. import models

TESTS_PATH = (Path(__file__) / "..").resolve()

# Get words list from online dict
word_site = "http://svnweb.freebsd.org/csrg/share/dict/words?view=co&content-type=text/plain"
response = requests.get(word_site)
WORDS = [w.lower() for w in response.content.decode().splitlines() if len(w) > 2]


def _random_word():
    "Deprecated"
    chars = [chr(i) for i in range(ord('a'), ord('z') + 1)]
    return "".join(choice(chars) for _ in range(randint(3, randint(3, 20))))


def random_word():
    return choice(WORDS)


def random_sentences(words=100, rates=None):
    """
    Generate random pseudo-sentences with given params

    :param words: words count +- 10%
    :param rates: separators rates, higher rate => higher chance of picking that separator
    :return:
    """
    rates = rates or {
        " ": 100,
        ". ": 20,
        ", ": 15,
        "? ": 15,
        "! ": 4,
        ".\n": 2
    }
    chars = reduce(operator.add, map(lambda x: [x[0]] * x[1], rates.items()))
    return ("".join(
        random_word() + choice(chars)
        for _ in range(randint(words - words // 10, words + words // 10))
    )).strip()


def random_text():
    return " ".join([random_sentences() for _ in range(randint(2, 10))])


def test_image(path: Path = TESTS_PATH / "ad.png"):
    return SimpleUploadedFile(name=path.name, content=path.open("rb").read(), content_type='image/png')


def test_svg(path: Path = TESTS_PATH / "ad.svg"):
    return SimpleUploadedFile(name=path.name, content=path.open("rb").read(), content_type='image/svg')


class BookTest(TestCase):
    LANG_COUNT = 6
    author: models.Author = None

    @classmethod
    def setUpTestData(cls):
        cls.author, created = models.Author.objects.get_or_create(name="Author", age=18)
        cls.author.country_list = ["ru", "gb"]
        cls.author.save()

        if not models.Language.objects.exists():
            # Pick random langs + english as default
            langs = set((l[0], l[1].split(" - ")[1]) for l in models.Language.LANG_CHOICES if l[0] != "en")
            for code, name in sample(langs, cls.LANG_COUNT) + [("en", "English")]:
                models.Language.objects.create(code=code, name=name, flag=test_svg())

        for i in range(randint(2, 5)):
            book = models.Book.objects.create(author=cls.author)

            for j in range(randint(4, 6)):
                models.Image.objects.create(book=book, file=test_image(), type="preview", position=j)

            langs: List[models.Language] = sample(
                list(models.Language.objects.exclude(code="en")),
                k=randint(2, cls.LANG_COUNT)
            ) + [models.Language.objects.get(code="en")]
            for lang in langs:
                models.BookLanguage.objects.create(lang=lang, book=book, hidden=False)

            lang = langs.pop(0)
            title, annotation, textfrags, images = cls.createTranslation(book, lang)
            book.structure = cls.genStructure(textfrags, images)
            book.save()

            for lang in langs:
                cls.createTranslation(book, lang, first=False)

    @classmethod
    def createTranslation(cls, book: models.Book, lang: models.Language, first=True):
        """
        Create book translation and return it's data (only if first==True)

        :param book: Book
        :param lang: Language
        :param first: create structure if True else only create TextFragments
        :return: title, annotation, textfrags, images or None
        """
        title = models.TextFragment.objects.create(
            text=random_word() + " " + random_word(),
            type="title", book=book, lang=lang,
            **{} if first else {
                "uuid": models.TextFragment.objects.filter(book=book, type="title").first().uuid
            }
        )
        annotation = models.TextFragment.objects.create(
            text=random_text(),
            type="ann", book=book, lang=lang,
            **{} if first else {
                "uuid": models.TextFragment.objects.filter(book=book, type="ann").first().uuid
            }
        )
        if first:
            textfrags = [
                models.TextFragment.objects.create(text=random_text(), type="body", book=book, lang=lang)
                for _ in range(randint(1, 20))
            ]
            images = []
            for _ in range(len(textfrags)):
                image = models.Image.objects.create(file=test_image(), book=book, author=cls.author, type="body")
                image_title = models.TextFragment.objects.create(text=random_word(), type="body", book=book, lang=lang)
                body = []
                for i in range(randint(2, 10)):
                    if i % 2:
                        body.append(models.Image.objects.create(file=test_image(), book=book, type="body"))
                    else:
                        body.append(models.TextFragment.objects.create(text=random_text(), type="body", book=book,
                                                                       lang=lang))
                images.append((image, image_title, body))
            return title, annotation, textfrags, images
        else:
            for item in book.structure:
                if item["type"] == "textfragment":
                    uuid = UUID(item["id"])
                    models.TextFragment.objects.create(text=random_text(),
                                                       uuid=uuid, type="body", book=book, lang=lang)
                elif item["type"] == "image":
                    uuid = UUID(item["title"])
                    models.TextFragment.objects.create(text=random_word(),
                                                       uuid=uuid, type="body", book=book, lang=lang)
                    for subitem in item["content"]:
                        if subitem["type"] == "textfragment":
                            uuid = UUID(subitem["id"])
                            models.TextFragment.objects.create(text=random_text(),
                                                               uuid=uuid, type="body", book=book, lang=lang)

    @classmethod
    def genStructure(
            cls, textfrags: Iterable[models.TextFragment],
            images: Iterable[Tuple[
                models.Image, models.TextFragment,
                Iterable[Union[models.TextFragment, models.Image]]
            ]]
    ) -> Iterable[dict]:
        """
        Generate book.structure from given book content

        :param textfrags:
        :param images:
        :return:
        """
        struct = []
        for textfrag, (image, image_title, image_body) in zip(textfrags, images):
            struct.append({"type": "textfragment", "id": str(textfrag.uuid).replace("-", "")})
            struct.append({
                "type": "image",
                "id": image.id,
                "title": str(image_title.uuid).replace("-", ""),
                "content": [
                    {
                        "type": "textfragment",
                        "id": str(item.uuid).replace("-", "")
                    } if isinstance(item, models.TextFragment) else {
                        "type": "image",
                        "id": item.id,
                    }
                    for item in image_body
                ]
            })
        return struct

    @classmethod
    def tearDownClass(cls):
        """
        Clear saved media-garbage
        """
        image: models.Image
        for image in models.Image.objects.all():
            image.file.delete()
        lang: models.Language
        for lang in models.Language.objects.all():
            lang.flag.delete()
        super().tearDownClass()
