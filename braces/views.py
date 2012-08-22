import datetime, json

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect, Http404
from django.utils.decorators import method_decorator
from django.utils.http import urlquote
from django.views.generic import CreateView
from django.views.generic.base import TemplateResponseMixin, View
from django.views.generic.list import BaseListView
from django.views.generic.edit import BaseDeleteView, FormMixin


class CreateAndRedirectToEditView(CreateView):
    """
    Subclass of CreateView which redirects to the edit view.
    Requires property `success_url_name` to be set to a
    reversible url that uses the objects pk.
    """
    success_url_name = None

    def get_success_url(self):
        if self.success_url_name:
            self.success_url = reverse(self.success_url_name,
                kwargs={'pk': self.object.pk})
            return super(CreateAndRedirectToEditView, self).get_success_url()

        raise ImproperlyConfigured(
            "No URL to reverse. Provide a success_url_name.")


class LoginRequiredMixin(object):
    """
    View mixin which verifies that the user has authenticated.

    NOTE:
        This should be the left-most mixin of a view.
    """

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginRequiredMixin, self).dispatch(*args, **kwargs)


class AnonymousRequiredMixin(object):
    """
    Generic mixin to reserve a view only for anonymous user

    NOTE:
        This should be the left-most mixin of a view.
    """
    redirect_url = settings.LOGIN_URL
    
    def get_redirect_url(self):
        return self.redirect_url
    
    def get(self, *args, **kwargs):
        if not self.request.user.is_anonymous():
            return HttpResponseRedirect(self.get_redirect_url())
        return super(AnonymousRequiredMixin, self).get(*args, **kwargs)
    
    def post(self, *args, **kwargs):
        if not self.request.user.is_anonymous():
            return HttpResponseRedirect(self.get_redirect_url())
        return super(AnonymousRequiredMixin, self).post(*args, **kwargs)


class PermissionRequiredMixin(object):
    """
    View mixin which verifies that the logged in user has the specified
    permission.

    Class Settings
    `permission_required` - the permission to check for.
    `login_url` - the login url of site
    `redirect_field_name` - defaults to "next"
    `raise_exception` - defaults to False - raise 403 if set to True

    Example Usage

        class SomeView(PermissionRequiredMixin, ListView):
            ...
            # required
            permission_required = "app.permission"

            # optional
            login_url = "/signup/"
            redirect_field_name = "hollaback"
            raise_exception = True
            ...
    """
    login_url = settings.LOGIN_URL
    permission_required = None
    raise_exception = False
    redirect_field_name = REDIRECT_FIELD_NAME

    def dispatch(self, request, *args, **kwargs):
        # Verify class settings
        if self.permission_required == None or len(
            self.permission_required.split(".")) != 2:
            raise ImproperlyConfigured("'PermissionRequiredMixin' requires "
                "'permission_required' attribute to be set.")

        has_permission = request.user.has_perm(self.permission_required)

        if not has_permission:
            if self.raise_exception:
                return HttpResponseForbidden()
            else:
                path = urlquote(request.get_full_path())
                tup = self.login_url, self.redirect_field_name, path
                return HttpResponseRedirect("%s?%s=%s" % tup)

        return super(PermissionRequiredMixin, self).dispatch(request,
            *args, **kwargs)


class UserFormKwargsMixin(object):
    """
    CBV mixin which puts the user from the request into the form kwargs.
    Note: Using this mixin requires you to pop the `user` kwarg
    out of the dict in the super of your form's `__init__`.
    """
    def get_form_kwargs(self, **kwargs):
        kwargs = super(UserFormKwargsMixin, self).get_form_kwargs(**kwargs)
        kwargs.update({"user": self.request.user})
        return kwargs


class SuccessURLRedirectListMixin(object):
    """
    Simple CBV mixin which sets the success url to the list view of
    a given app. Set success_list_url as a class attribute of your
    CBV and don't worry about overloading the get_success_url.

    This is only to be used for redirecting to a list page. If you need
    to reverse the url with kwargs, this is not the mixin to use.
    """
    success_list_url = None

    def get_success_url(self):
        return reverse(self.success_list_url)


class SuperuserRequiredMixin(object):
    login_url = settings.LOGIN_URL
    raise_exception = False
    redirect_field_name = REDIRECT_FIELD_NAME

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            if self.raise_exception:
                return HttpResponseForbidden()
            else:
                path = urlquote(request.get_full_path())
                tup = self.login_url, self.redirect_field_name, path
                return HttpResponseRedirect("%s?%s=%s" % tup)

        return super(SuperuserRequiredMixin, self).dispatch(request,
            *args, **kwargs)


class SetHeadlineMixin(object):
    """
    Mixin allows you to set a static headline through a static property on the
    class or programmatically by overloading the get_headline method.
    """
    headline = None

    def get_context_data(self, **kwargs):
        kwargs = super(SetHeadlineMixin, self).get_context_data(**kwargs)
        kwargs.update({"headline": self.get_headline()})
        return kwargs

    def get_headline(self):
        if self.headline is None:
            raise ImproperlyConfigured(u"%(cls)s is missing a headline. Define "
                u"%(cls)s.headline, or override "
                u"%(cls)s.get_headline()." % {"cls": self.__class__.__name__
            })
        return self.headline


class SelectRelatedMixin(object):
    """
    Mixin allows you to provide a tuple or list of related models to
    perform a select_related on.
    """
    select_related = None

    def get_queryset(self):
        if self.select_related is None:
            raise ImproperlyConfigured(u"%(cls)s is missing the select_related "
                "property. This must be a tuple or list." % {
                    "cls": self.__class__.__name__})

        if not isinstance(self.select_related, (tuple, list)):
            raise ImproperlyConfigured(u"%(cls)s's select_related property "
                "must be a tuple or list." % {"cls": self.__class__.__name__})

        queryset = super(SelectRelatedMixin, self).get_queryset()
        return queryset.select_related(
            ", ".join(self.select_related)
        )


class JSONMixin(object):
    """
    Simple Mixin to compile the context view as JSON
    
    This does not implement a direct response, you have to return it with the 
    ``json_to_response`` method in your view.
    """
    mimetype = "application/json"
    json_indent = None
    json_encoder = None
    
    def encode_context(self, context):
        json_kwargs = {}
        if self.json_indent is not None:
            json_kwargs['indent'] = self.json_indent
        if self.json_encoder is not None:
            json_kwargs['encoder'] = self.json_encoder
        return json.dumps(context, **json_kwargs)
    
    def json_to_response(self, context, **response_kwargs):
        """
        Returns a response with a template rendered with the given context.
        """
        if 'mimetype' not in response_kwargs:
            response_kwargs['mimetype'] = self.mimetype
        return HttpResponse(self.encode_context(context), **response_kwargs)


class JSONResponseMixin(JSONMixin):
    """Mixin to directly return a JSON response"""
    def render_to_response(self, context, **response_kwargs):
        """
        Returns a response with a template rendered with the given context.
        """
        return self.json_to_response(context)


class DownloadMixin(object):
    """
    Simple Mixin to send a downloadable content
    
    Inherits must have :
    
    * Filled the ``self.mimetype`` attribute with the content mimetype to send;
    * Implementation of ``get_filename()`` that return the filename to use in response 
      headers;
    * Implementation of ``get_content()`` that return the content to send as downloadable.
    
    If the content is a not a string, it is assumed to be a fileobject to send as 
    the content with its ``read()`` method.
    
    Optionnaly implement a ``close_content()`` to close specifics objects linked to 
    content fileobject, if it does not exists a try will be made on a close() method 
    on the content fileobject;
    
    A "get_filename_timestamp" method is implemented to return a timestamp to use in your 
    filename if needed, his date format is defined in "timestamp_format" attribute (in a 
    suitable way to use with strftime on a datetime object).
    """
    mimetype = None
    timestamp_format = "%Y-%m-%d"
    
    def get_filename_timestamp(self):
        return datetime.datetime.now().strftime(self.timestamp_format)
    
    def get_filename(self, context):
        raise ImproperlyConfigured("DownloadMixin requires an implementation of 'get_filename()' to return the filename to use in headers")
    
    def get_content(self, context):
        raise ImproperlyConfigured("DownloadMixin requires an implementation of 'get_content()' to return the downloadable content")
    
    def render_to_response(self, context, **response_kwargs):
        if getattr(self, 'mimetype', None) is None:
            raise ImproperlyConfigured("DownloadMixin requires a definition of 'mimetype' attribute")
        # Needed headers
        response = HttpResponse(mimetype=self.mimetype, **response_kwargs)
        response['Content-Disposition'] = 'attachment; filename={0}'.format(self.get_filename(context))
        # Read the content file object or string, append it to response and close it
        content = self.get_content(context)
        if isinstance(content, basestring):
            response.write(content)
        else:
            response.write(content.read())
        # Conditionnal closing content object
        if hasattr(self, 'close_content'):
            self.close_content(context, content)
        elif hasattr(content, 'close'):
            content.close()
            
        return response

    def get_context_data(self, **kwargs):
        return {
            'params': kwargs
        }

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)


class ExtendTemplateVariableMixin(object):
    """
    Get the extend variable to use in the template
    
    Default behaviour is to switch on two templates depending on the request is an ajax 
    request or not, if ajax "base_modal.html" is used else the default extend will 
    simply be "base.html".
    
    This only put the "template_extend" variable in the template context, your template 
    have to use it, this does not modify itself the response nor the template.
    """
    default_extend_template = "base.html"
    modal_extend_template = "base_modal.html"
    
    def get_template_extend(self):
        if self.request.is_ajax():
            return self.modal_extend_template
        return self.default_extend_template
    
    def get_context_data(self, **kwargs):
        context = super(ExtendTemplateVariableMixin, self).get_context_data(**kwargs)
        context.update({
            'template_extend': self.get_template_extend(),
        })
        return context


class SimpleListView(TemplateResponseMixin, BaseListView):
    """
    Like generic.ListView but use only ``get_template`` to find template and not an 
    automatic process on ``get_template_names``
    """
    pass


class DirectDeleteView(BaseDeleteView):
    """
    To directly delete an object without template rendering on GET or POST methods
    
    "get_success_url" or "success_url" should be correctly filled
    """
    def get(self, *args, **kwargs):
        return self.delete(*args, **kwargs)


class ListAppendView(SimpleListView, FormMixin):
    """
    A view to display an object list with a form to append a new object
    
    This view re-use some code from FormMixin and SimpleListView, sadly it seem not 
    possible to simply mix them.
    
    Need "model" and "form_class" attributes for the form parts and the required one 
    by BaseListView. "get_success_url" method should be filled too.
    
    "locked_form" is used to disable form (like if your list object is closed to new 
    object)
    """
    model = None
    form_class = None
    template_name = None
    paginate_by = None
    locked_form = False
    
    def form_valid(self, form):
        self.object = form.save()
        return super(ListAppendView, self).form_valid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(object_list=self.object_list, form=form))

    def is_locked_form(self):
        return self.locked_form

    def get_form(self, form_class):
        """
        Returns an instance of the form to be used in this view.
        """
        if self.is_locked_form():
            return None
        return form_class(**self.get_form_kwargs())
        
    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        
        allow_empty = self.get_allow_empty()
        if not allow_empty and len(self.object_list) == 0:
            raise Http404(_(u"Empty list and '%(class_name)s.allow_empty' is False.")
                          % {'class_name': self.__class__.__name__})
        
        context = self.get_context_data(object_list=self.object_list, form=form)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        
        allow_empty = self.get_allow_empty()
        if not allow_empty and len(self.object_list) == 0:
            raise Http404(_(u"Empty list and '%(class_name)s.allow_empty' is False.")
                          % {'class_name': self.__class__.__name__})
        
        if form and form.is_valid():
            return self.form_valid(form)
        elif form:
            return self.form_invalid(form)
        else:
            context = self.get_context_data(object_list=self.object_list, form=form)
            return self.render_to_response(context)

    def put(self, *args, **kwargs):
        return self.post(*args, **kwargs)

class DetailListAppendView(ListAppendView):
    """
    A view to display a parent object details, list his "children" and display a form 
    to append a new child
    
    Have the same behaviours than "ListAppendView" but get the parent object before 
    doing anything.
    
    "model" and "form_class" attribute are for the children, "context_parent_object_name" 
    is used to name the parent variable in the template context.
    
    "get_parent_object" must be defined to return the parent instance. "get_queryset" 
    should be defined to make a queryset exclusively on the parent children.
    
    The parent object is also given to the append form, under the name defined with the 
    "context_parent_object_name" attribute. Your Form should be aware of this.
    """
    context_parent_object_name = 'parent_object'
    
    def get_parent_object(self):
        raise ImproperlyConfigured(u"%(cls)s's 'get_parent_object' method must be defined " % {"cls": self.__class__.__name__})

    def get_context_data(self, **kwargs):
        kwargs.update({
            self.context_parent_object_name: self.parent_object,
        })
        return super(DetailListAppendView, self).get_context_data(**kwargs)
        
    def get_form_kwargs(self):
        """
        Returns an instance of the form to be used in this view.
        """
        kwargs = super(DetailListAppendView, self).get_form_kwargs()
        kwargs.update({
            self.context_parent_object_name: self.parent_object,
        })
        return kwargs
        
    def get(self, request, *args, **kwargs):
        self.parent_object = self.get_parent_object()
        return super(DetailListAppendView, self).get(request, *args, **kwargs)
        
    def post(self, request, *args, **kwargs):
        self.parent_object = self.get_parent_object()
        return super(DetailListAppendView, self).post(request, *args, **kwargs)


class ExcelExportView(DownloadMixin, View):
    """
    Generic view to export Excel file
    
    Inherits must implement at least the ``get_content()`` method to return the content 
    fileobject
    """
    mimetype = 'application/ms-excel'
    filename_format = "file_{timestamp}.xls"
    
    def get_context_data(self, **kwargs):
        context = super(ExcelExportView, self).get_context_data(**kwargs)
        context.update({
            'timestamp': self.get_filename_timestamp(),
        })
        return context
    
    def get_filename(self, context):
        return self.filename_format.format(**context)
