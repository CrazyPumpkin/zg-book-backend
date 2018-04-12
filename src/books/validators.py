import json
from enum import Enum
from pathlib import Path
from typing import Union, Dict, Iterable

import collections.abc
from django.apps import apps
from django.db import models
from django.utils.translation import ugettext_lazy as _
from jsonschema import validate


class JsonSchemaValidator:
    """
    Validate JSONField by given JSON Schema
    See http://json-schema.org/ for details
    """

    def __init__(self, schema):
        """

        :param schema: Any of: Path-like obj, file-like obj, path string (*.json), JSON string, dict
        """
        if isinstance(schema, Path):
            with schema.open('r') as f:
                schema = json.load(f)
        elif isinstance(schema, str):
            if hasattr(schema, 'read'):
                schema = json.load(schema)
            elif schema.endswith(".json") or "/" in schema:
                with open(schema) as f:
                    schema = json.load(f)
            else:
                schema = json.loads(schema)

        self.schema = schema

    def __call__(self, value: Union[list, dict, str, int, float, bool, type(None)]):
        validate(value, schema=self.schema)

    def __eq__(self, other):
        return isinstance(other, JsonSchemaValidator) and self.schema == other.schema

    def deconstruct(self):
        path = 'books.validators.JsonSchemaValidator'
        args = ()
        kwargs = {"schema": self.schema}
        return path, args, kwargs


class BookValidateError:
    """
    Data container with JSON (de)serialization methods
    """
    CodeMsgs = {
        404: _("Элемент не найден в базе данных, вы скорее всего должны удалить и заново создать его"),
        405: _("Элемент не заполнен")
    }

    class Code(Enum):
        NotFound = 404
        Empty = 405

    class Source(Enum):
        Preview = 0
        Content = 1
        SubContent = 2

    class ObjType(Enum):
        TextFragment = 0
        Image = 1
        ImageTitle = 2
        ImageAuthor = 3
        TextTitle = 4
        TextAnnotation = 5

    def __init__(self, source: Source, code: Code, obj_type: ObjType, index=None, obj_id=None, **kwargs):
        self.source = source
        self.code = code
        self.obj_type = obj_type
        self.index = index
        self.obj_id = obj_id
        self.kwargs = kwargs

    def __repr__(self):
        return f"<BookValidateError ({self.source.name}, {self.code.name}, {self.obj_type.name})>"

    def to_json(self):
        return {
            "source": self.source.name,
            "code": self.code.name,
            "object": {
                "id": self.obj_id,
                "type": self.obj_type.name
            },
            "index": self.index,
            "other": self.kwargs
        }

    @classmethod
    def from_json(cls, data: dict):
        return cls(
            source=cls.Source[data.pop("source")],
            code=cls.Code[data.pop("code")],
            obj_type=cls.ObjType[data["object"].pop("type")],
            index=data.pop("index"),
            obj_id=data.pop("object").pop("id"),
            **data.pop("other"),
            **data
        )


class BookValidator(collections.Iterable):
    """
    Iterable object, that contains errors of given pair (book, lang_code)
    """

    def __init__(self, book, lang: str):
        self.book = book
        self.lang = lang

    def __iter__(self) -> Iterable[BookValidateError]:
        lang = apps.get_model('books', 'Language').objects.get(code=self.lang)
        text_fragments: Dict[str, models.Model] = {
            str(tf.uuid).replace("-", ""): tf
            for tf in self.book.textfragment_set.filter(type="body", lang=lang)
        }
        images: Dict[int, models.Model] = {
            img.id: img
            for img in self.book.content_images.all()
        }

        title = self.book.get_title(self.lang)
        if title is None:
            yield BookValidateError(
                BookValidateError.Source.Preview,
                BookValidateError.Code.NotFound,
                BookValidateError.ObjType.TextTitle
            )
        elif title == "":
            yield BookValidateError(
                BookValidateError.Source.Preview,
                BookValidateError.Code.Empty,
                BookValidateError.ObjType.TextTitle
            )

        annotation = self.book.get_annotation(self.lang)
        if annotation is None:
            yield BookValidateError(
                BookValidateError.Source.Preview,
                BookValidateError.Code.NotFound,
                BookValidateError.ObjType.TextAnnotation
            )
        elif annotation == "":
            yield BookValidateError(
                BookValidateError.Source.Preview,
                BookValidateError.Code.Empty,
                BookValidateError.ObjType.TextAnnotation
            )

        # Validate structure
        item: dict
        for i, item in enumerate(self.book.structure):
            if item["type"] == "textfragment":
                fragment = text_fragments.pop(item["id"], None)
                if fragment is None:
                    yield BookValidateError(
                        BookValidateError.Source.Content,
                        BookValidateError.Code.NotFound,
                        BookValidateError.ObjType.TextFragment,
                        index=i, obj_id=item["id"]
                    )
                    continue

                if not fragment.text.strip():
                    yield BookValidateError(
                        BookValidateError.Source.Content,
                        BookValidateError.Code.Empty,
                        BookValidateError.ObjType.TextFragment,
                        index=i, obj_id=item["id"]
                    )

            elif item["type"] == "image":
                image = images.pop(item["id"], None)
                if image is None:
                    yield BookValidateError(
                        BookValidateError.Source.Content,
                        BookValidateError.Code.NotFound,
                        BookValidateError.ObjType.Image,
                        index=i, obj_id=item["id"]
                    )

                if image and not image.file:
                    yield BookValidateError(
                        BookValidateError.Source.Content,
                        BookValidateError.Code.Empty,
                        BookValidateError.ObjType.Image,
                        index=i, obj_id=item["id"]
                    )

                title = text_fragments.pop(item["title"], None)
                if title is None:
                    yield BookValidateError(
                        BookValidateError.Source.Content,
                        BookValidateError.Code.Empty,
                        BookValidateError.ObjType.ImageTitle,
                        index=i, obj_id=item["title"]
                    )

                if image and not image.author:
                    yield BookValidateError(
                        BookValidateError.Source.Content,
                        BookValidateError.Code.Empty,
                        BookValidateError.ObjType.ImageAuthor,
                        index=i, obj_id=image.author_id
                    )

                # Validate structure of image page
                subitem: dict
                for j, subitem in enumerate(item["content"]):
                    if subitem["type"] == "textfragment":
                        fragment = text_fragments.pop(subitem["id"], None)
                        if fragment is None:
                            yield BookValidateError(
                                BookValidateError.Source.SubContent,
                                BookValidateError.Code.NotFound,
                                BookValidateError.ObjType.TextFragment,
                                index=(i, j), obj_id=subitem["id"]
                            )
                            continue

                        if not fragment.text.strip():
                            yield BookValidateError(
                                BookValidateError.Source.SubContent,
                                BookValidateError.Code.Empty,
                                BookValidateError.ObjType.TextFragment,
                                index=(i, j), obj_id=subitem["id"]
                            )

                    elif subitem["type"] == "image":
                        image = images.pop(subitem["id"], None)
                        if image is None:
                            yield BookValidateError(
                                BookValidateError.Source.SubContent,
                                BookValidateError.Code.NotFound,
                                BookValidateError.ObjType.Image,
                                index=(i, j), obj_id=subitem["id"]
                            )

                        if image and not image.file:
                            yield BookValidateError(
                                BookValidateError.Source.SubContent,
                                BookValidateError.Code.Empty,
                                BookValidateError.ObjType.Image,
                                index=(i, j), obj_id=subitem["id"]
                            )
