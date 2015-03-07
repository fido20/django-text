import re

from django.template.response import SimpleTemplateResponse
from django.template import Template, Context, RequestContext
from django.template.loader import get_template
from django.utils.translation import get_language
from django.utils.encoding import force_text
from django.conf import settings as django_settings

from .conf import settings
from .models import Text
from .forms import TextForm
from .utils import access_toolbar


def build_context(texts, defaults, types):
    placeholder = "text_placeholder_{0}"
    context = {placeholder.format(t.name): t.render() for t in texts}
    for name, text in defaults.iteritems():
        pname = placeholder.format(name)
        if pname not in context:
            context[pname] = create_text(name, text, types[name]).render()
    return context


def create_text(name, body, text_type):
    if text_type is None or text_type not in dict(Text.TYPES).keys():
        text_type = Text._meta.get_field('type').get_default()

    language = get_language()
    text = Text(
        name=name,
        body=body,
        language=language,
        type=text_type)
    if settings.AUTOPOPULATE_TEXT:
        text.save()
    return text


class TextMiddleware(object):
    def process_template_response(self, request, response):
        template = Template(response.render().content)
        if not hasattr(request, 'text_register'):
            return response
        language = get_language()
        texts = Text.objects.filter(
            name__in=request.text_register,
            language=language)
        if hasattr(request, 'text_default_register'):
            defaults = request.text_default_register
        else:
            defaults = {}
        if hasattr(request, 'text_type_register'):
            types = request.text_type_register
        else:
            types = {}
        context = Context(build_context(texts, defaults, types))
        return SimpleTemplateResponse(template, context)


class ToolbarMiddleware(object):
    def process_response(self, request, response):
        texts = getattr(request, 'text_register', None)
        if request.is_ajax() or not texts or not access_toolbar(request):
            return response
        toolbar = get_template('text/text_toolbar.html')
        form = TextForm(prefix=settings.TOOLBAR_FORM_PREFIX)
        context = RequestContext(request, {
            'texts': texts,
            'language': get_language(),
            'form': form,
            'inline_wrapper_class': settings.INLINE_WRAPPER_CLASS,
        })
        insert_before = '</body>'
        pattern = re.escape(insert_before)
        content = force_text(
            response.content, encoding=django_settings.DEFAULT_CHARSET)
        bits = re.split(pattern, content, flags=re.IGNORECASE)

        if len(bits) > 1:
            bits[-2] += toolbar.render(context)
            response.content = insert_before.join(bits)
            if response.get('Content-Length', None):
                response['Content-Length'] = len(response.content)
        return response
