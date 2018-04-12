from xml.etree import cElementTree as et

from django.core.exceptions import ValidationError


def validate_svg(file):
    tag = None
    try:
        for event, el in et.iterparse(file, ('start',)):
            tag = el.tag
            break
    except et.ParseError:
        pass
    if tag != '{http://www.w3.org/2000/svg}svg':
        raise ValidationError("File is not svg")
