
## Models 
- Language
    - code - see [ISO-639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)
    - name
    - flag - SvgField
- BookLanguage
    - lang - fk[Language]
    - book - fk[Book]
    - last_modified - datetime
    - hidden - bool
- Book
    - title
    - languages - m2m[Language, through=BookLanguage]
    - languages_list - (property) List of lang codes 
    - structure - JSON
    - preview_images - (property) queryset[Image]
    - content_images - (property) queryset[Image]
    - author - fk[Author]
- Author
    - name
    - link - url
    - country - string_list[country_code] see [ISO-3166-1](https://ru.wikipedia.org/wiki/ISO_3166-1)
    - age
- Image
    - file
    - position - (for previews) order
    - type - one of: `preview`, `body`
    - book - fk[Book]
    - author - fk[Author]
- TextFragment
    - uuid - UUID
    - text
    - type - one of: `title`, `ann`, `body` (`ann[otation]`)
    - book - fk[Book]
    - lang - fk[Language]
    
## Notes
### note1
Structure in client (requested with lang)
```
[
    {
        "type": "textfragment",
        "text": "..."
    },
    {
        "type": "image",
        "id": 1,
        "url": "...",
        "title": "string",
        "author": {
            "name": "...",
            "country": ["ru", "gb"],
            "link": "url"
        },
        "content": [
            {
                "type": "textfragment",
                "text": "..."
            },
            {
                "type": "image",
                "id": 1,
                "url": "..."
            }
        ]
    },
]
```

Structure on server/admin
```
[
    {
        "type": "textfragment",
        "id": "<uuid>"
    },
    {
        "type": "image",
        "id": 1,
        "title": "<uuid>",
        "content": [
            {
                "type": "textfragment",
                "id": "<uuid>"
            },
            {
                "type": "image",
                "id": 1
            }
        ]
    }
]
```
> `title` is UUID because of it should be translated as well as other book text fragments

### `/api/v1/admin/books/{id}/validate/`
```
{
    "lang": {
        "source": "Preview",
        "code": "NotFound",
        "object": {
            "id": null,
            "type": "TextTitle"
        },
        "index": null,
        "other": {}
    }
}
```
- source
    - `Preview` not bought book data (title, annotation, previews)
    - `Content` book body
    - `SubContent` text and images bellow the image in body
- code
    - `NotFound` Object not found in db or attribute is null
    - `Empty` Image content or text is blank
- object
    - `id` image id/textfragment uuid
    - type
        - `TextFragment` General textfragment
        - `Image`
        - `ImageTitle` (TextFragment) 
        - `ImageAuthor` Author field of the image 
        - `TextTitle` Book title
        - `TextAnnotation` Book annotation
    - `index` Index of the element in book/image body. Is null for `Preview` source

### Book structure (server-side) JSON Schema
```
{
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "array",
    "items": {
        "anyOf": [
            {
                "$ref": "#/definitions/textfragment"
            },
            {
                "$ref": "#/definitions/image_lvl1"
            }
        ]
    },
    "definitions": {
        "textfragment": {
            "type": "object",
            "properties": {
                "type": {
                    "enum": [
                        "textfragment"
                    ]
                },
                "id": {
                    "type": "string"
                }
            },
            "required": [
                "type",
                "id"
            ]
        },
        "image_lvl2": {
            "properties": {
                "type": {
                    "enum": [
                        "image"
                    ]
                },
                "id": {
                    "type": "integer"
                }
            },
            "required": [
                "type",
                "id"
            ]
        },
        "image_lvl1": {
            "properties": {
                "type": {
                    "enum": [
                        "image"
                    ]
                },
                "id": {
                    "type": "integer"
                },
                "title": {
                    "type": "string"
                },
                "content": {
                    "type": "array",
                    "items": {
                        "anyOf": [
                            {
                                "$ref": "#/definitions/textfragment"
                            },
                            {
                                "$ref": "#/definitions/image_lvl2"
                            }
                        ]
                    }
                }
            },
            "required": [
                "type",
                "id",
                "title",
                "content"
            ]
        }
    }
}
```