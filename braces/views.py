import datetime, json

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core import serializers
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.core.urlresolvers import reverse
from django.utils import simplejson as json
from django.http import HttpResponse, HttpResponseRedirect, Http404
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
        # First we check for a name to be provided on the view object.
        # If one is, we reverse it and finish running the method,
        # otherwise we raise a configuration error.
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
    def dispatch(self, request, *args, **kwargs):
        return super(LoginRequiredMixin, self).dispatch(request,
            *args, **kwargs)


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
    login_url = settings.LOGIN_URL  # LOGIN_URL from project settings
    permission_required = None  # Default required perms to none
    raise_exception = False  # Default whether to raise an exception to none
    redirect_field_name = REDIRECT_FIELD_NAME  # Set by django.contrib.auth

    def dispatch(self, request, *args, **kwargs):
        # Make sure that a permission_required is set on the view,
        # and if it is, that it only has two parts (app.action_model)
        # or raise a configuration error.
        if self.permission_required == None or len(
            self.permission_required.split(".")) != 2:
            raise ImproperlyConfigured("'PermissionRequiredMixin' requires "
                "'permission_required' attribute to be set.")

        # Check to see if the request's user has the required permission.
        has_permission = request.user.has_perm(self.permission_required)

        if not has_permission:  # If the user lacks the permission
            if self.raise_exception:  # *and* if an exception was desired
                raise PermissionDenied  # return a forbidden response.
            else:
                return redirect_to_login(request.get_full_path(),
                                         self.login_url,
                                         self.redirect_field_name)

        return super(PermissionRequiredMixin, self).dispatch(request,
            *args, **kwargs)


class MultiplePermissionsRequiredMixin(object):
    """
    View mixin which allows you to specify two types of permission
    requirements. The `permissions` attribute must be a dict which
    specifies two keys, `all` and `any`. You can use either one on
    it's own or combine them. Both keys values are required be a list or
    tuple of permissions in the format of
    <app label>.<permission codename>

    By specifying the `all` key, the user must have all of
    the permissions in the passed in list.

    By specifying The `any` key , the user must have ONE of the set
    permissions in the list.

    Class Settings
        `permissions` - This is required to be a dict with one or both
            keys of `all` and/or `any` containing a list or tuple of
            permissions in the format of <app label>.<permission codename>
        `login_url` - the login url of site
        `redirect_field_name` - defaults to "next"
        `raise_exception` - defaults to False - raise 403 if set to True

    Example Usage
        class SomeView(MultiplePermissionsRequiredMixin, ListView):
            ...
            #required
            permissions = {
                "all": (blog.add_post, blog.change_post),
                "any": (blog.delete_post, user.change_user)
            }

            #optional
            login_url = "/signup/"
            redirect_field_name = "hollaback"
            raise_exception = True
    """
    login_url = settings.LOGIN_URL  # LOGIN_URL from project settings
    permissions = None  # Default required perms to none
    raise_exception = False  # Default whether to raise an exception to none
    redirect_field_name = REDIRECT_FIELD_NAME  # Set by django.contrib.auth

    def dispatch(self, request, *args, **kwargs):
        self._check_permissions_attr()

        perms_all = self.permissions.get('all') or None
        perms_any = self.permissions.get('any') or None

        self._check_permissions_keys_set(perms_all, perms_any)
        self._check_perms_keys("all", perms_all)
        self._check_perms_keys("any", perms_any)

        # If perms_all, check that user has all permissions in the list/tuple
        if perms_all:
            if not request.user.has_perms(perms_all):
                if self.raise_exception:
                    raise PermissionDenied
                return redirect_to_login(request.get_full_path(),
                                         self.login_url,
                                         self.redirect_field_name)

        # If perms_any, check that user has at least one in the list/tuple
        if perms_any:
            has_one_perm = False
            for perm in perms_any:
                if request.user.has_perm(perm):
                    has_one_perm = True
                    break

            if not has_one_perm:
                if self.raise_exception:
                    raise PermissionDenied
                return redirect_to_login(request.get_full_path(),
                                         self.login_url,
                                         self.redirect_field_name)

        return super(MultiplePermissionsRequiredMixin, self).dispatch(request,
            *args, **kwargs)

    def _check_permissions_attr(self):
        """
        Check permissions attribute is set and that it is a dict.
        """
        if self.permissions is None or not isinstance(self.permissions, dict):
            raise ImproperlyConfigured("'PermissionsRequiredMixin' requires "
                "'permissions' attribute to be set to a dict.")

    def _check_permissions_keys_set(self, perms_all=None, perms_any=None):
        """
        Check to make sure the keys `any` or `all` are not both blank.
        If both are blank either an empty dict came in or the wrong keys
        came in. Both are invalid and should raise an exception.
        """
        if perms_all is None and perms_any is None:
            raise ImproperlyConfigured("'PermissionsRequiredMixin' requires"
                "'permissions' attribute to be set to a dict and the 'any' "
                "or 'all' key to be set.")

    def _check_perms_keys(self, key=None, perms=None):
        """
        If the permissions list/tuple passed in is set, check to make
        sure that it is of the type list or tuple.
        """
        if perms and not isinstance(perms, (list, tuple)):
            raise ImproperlyConfigured("'MultiplePermissionsRequiredMixin' "
                "requires permissions dict '%s' value to be a list "
                "or tuple." % key)


class UserFormKwargsMixin(object):
    """
    CBV mixin which puts the user from the request into the form kwargs.
    Note: Using this mixin requires you to pop the `user` kwarg
    out of the dict in the super of your form's `__init__`.
    """
    def get_form_kwargs(self):
        kwargs = super(UserFormKwargsMixin, self).get_form_kwargs()
        # Update the existing form kwargs dict with the request's user.
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
    success_list_url = None  # Default the success url to none

    def get_success_url(self):
        # Return the reversed success url.
        return reverse(self.success_list_url)


class SuperuserRequiredMixin(object):
    """
    Mixin allows you to require a user with `is_superuser` set to True.
    """
    login_url = settings.LOGIN_URL  # LOGIN_URL from project settings
    raise_exception = False  # Default whether to raise an exception to none
    redirect_field_name = REDIRECT_FIELD_NAME  # Set by django.contrib.auth

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:  # If the user is a standard user,
            if self.raise_exception:  # *and* if an exception was desired
                raise PermissionDenied  # return a forbidden response.
            else:
                return redirect_to_login(request.get_full_path(),
                                         self.login_url,
                                         self.redirect_field_name)

        return super(SuperuserRequiredMixin, self).dispatch(request,
            *args, **kwargs)


class SetHeadlineMixin(object):
    """
    Mixin allows you to set a static headline through a static property on the
    class or programmatically by overloading the get_headline method.
    """
    headline = None  # Default the headline to none

    def get_context_data(self, **kwargs):
        kwargs = super(SetHeadlineMixin, self).get_context_data(**kwargs)
        # Update the existing context dict with the provided headline.
        kwargs.update({"headline": self.get_headline()})
        return kwargs

    def get_headline(self):
        if self.headline is None:  # If no headline was provided as a view
                                   # attribute and this method wasn't overriden
                                   # raise a configuration error.
            raise ImproperlyConfigured(u"%(cls)s is missing a headline. "
                u"Define %(cls)s.headline, or override "
                u"%(cls)s.get_headline()." % {"cls": self.__class__.__name__
            })
        return self.headline


class SelectRelatedMixin(object):
    """
    Mixin allows you to provide a tuple or list of related models to
    perform a select_related on.
    """
    select_related = None  # Default related fields to none

    def get_queryset(self):
        if self.select_related is None:  # If no fields were provided,
                                         # raise a configuration error
            raise ImproperlyConfigured(u"%(cls)s is missing the "
                "select_related property. This must be a tuple or list." % {
                    "cls": self.__class__.__name__})

        if not isinstance(self.select_related, (tuple, list)):
            # If the select_related argument is *not* a tuple or list,
            # raise a configuration error.
            raise ImproperlyConfigured(u"%(cls)s's select_related property "
                "must be a tuple or list." % {"cls": self.__class__.__name__})

        # Get the current queryset of the view
        queryset = super(SelectRelatedMixin, self).get_queryset()

        return queryset.select_related(*self.select_related)


class StaffuserRequiredMixin(object):
    """
    Mixin allows you to require a user with `is_staff` set to True.
    """
    login_url = settings.LOGIN_URL  # LOGIN_URL from project settings
    raise_exception = False  # Default whether to raise an exception to none
    redirect_field_name = REDIRECT_FIELD_NAME  # Set by django.contrib.auth

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:  # If the request's user is not staff,
            if self.raise_exception:  # *and* if an exception was desired
                raise PermissionDenied  # return a forbidden response
            else:
                return redirect_to_login(request.get_full_path(),
                                         self.login_url,
                                         self.redirect_field_name)

        return super(StaffuserRequiredMixin, self).dispatch(request,
            *args, **kwargs)


class DownloadMixin(object):
    """
    Simple Mixin to send a downloadable content
    
    Inherits must have :
    
    * Filled the ``self.content_type`` attribute with the content content_type to send;
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
    content_type = None
    timestamp_format = "%Y-%m-%d"
    
    def get_filename_timestamp(self):
        return datetime.datetime.now().strftime(self.timestamp_format)
    
    def get_filename(self, context):
        raise ImproperlyConfigured("DownloadMixin requires an implementation of 'get_filename()' to return the filename to use in headers")
    
    def get_content(self, context):
        raise ImproperlyConfigured("DownloadMixin requires an implementation of 'get_content()' to return the downloadable content")
    
    def render_to_response(self, context, **response_kwargs):
        if getattr(self, 'content_type', None) is None:
            raise ImproperlyConfigured("DownloadMixin requires a definition of 'content_type' attribute")
        # Needed headers
        response = HttpResponse(content_type=self.content_type, **response_kwargs)
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
    content_type = 'application/ms-excel'
    filename_format = "file_{timestamp}.xls"
    
    def get_context_data(self, **kwargs):
        context = super(ExcelExportView, self).get_context_data(**kwargs)
        context.update({
            'timestamp': self.get_filename_timestamp(),
        })
        return context
    
    def get_filename(self, context):
        return self.filename_format.format(**context)

class JSONResponseMixin(object):
    """
    A mixin that allows you to easily serialize simple data such as a dict or
    Django models.
    """
    content_type = "application/json"

    def get_content_type(self):
        if self.content_type is None:
            raise ImproperlyConfigured(u"%(cls)s is missing a content type. "
                u"Define %(cls)s.content_type, or override "
                u"%(cls)s.get_content_type()." % {
                "cls": self.__class__.__name__
            })
        return self.content_type

    def render_json_response(self, context_dict):
        """
        Limited serialization for shipping plain data. Do not use for models
        or other complex or custom objects.
        """
        json_context = json.dumps(context_dict, cls=DjangoJSONEncoder, ensure_ascii=False)
        return HttpResponse(json_context, content_type=self.get_content_type())

    def render_json_object_response(self, objects, **kwargs):
        """
        Serializes objects using Django's builtin JSON serializer. Additional
        kwargs can be used the same way for django.core.serializers.serialize.
        """
        json_data = serializers.serialize("json", objects, **kwargs)
        return HttpResponse(json_data, content_type=self.get_content_type())

class JSONResponseExtendedMixin(JSONResponseMixin):
    """
    Simple Mixin to compile the context view as JSON
    
    This does not implement a direct response, you have to return it with the 
    ``json_to_response`` method in your view.
    """
    json_indent = None
    json_encoder = DjangoJSONEncoder
    json_ensure_ascii = False
    
    def encode_context(self, context):
        json_kwargs = {}
        if self.json_indent is not None:
            json_kwargs['indent'] = self.json_indent
        if self.json_encoder is not None:
            json_kwargs['encoder'] = self.json_encoder
        if self.json_ensure_ascii is not None:
            json_kwargs['ensure_ascii'] = self.json_ensure_ascii
        return json.dumps(context, **json_kwargs)

    def render_json_response(self, context_dict, **response_kwargs):
        """
        Limited serialization for shipping plain data. Do not use for models
        or other complex or custom objects.
        """
        if 'content_type' not in response_kwargs:
            response_kwargs['content_type'] = self.get_content_type()
        return HttpResponse(self.encode_context(context), **response_kwargs)


class JSONResponseViewMixin(JSONResponseExtendedMixin):
    """Mixin to directly return a JSON response"""
    def render_to_response(self, context, **response_kwargs):
        """
        Returns a response with a template rendered with the given context.
        """
        return self.json_to_response(context)

class AjaxResponseMixin(object):
    """
    Mixin allows you to define alternative methods for ajax requests. Similar
    to the normal get, post, and put methods, you can use get_ajax, post_ajax,
    and put_ajax.
    """
    def dispatch(self, request, *args, **kwargs):
        request_method = request.method.lower()

        if request.is_ajax() and request_method in self.http_method_names:
            handler = getattr(self, '%s_ajax' % request_method,
                self.http_method_not_allowed)
            self.request = request
            self.args = args
            self.kwargs = kwargs
            return handler(request, *args, **kwargs)

        return super(AjaxResponseMixin, self).dispatch(request, *args, **kwargs)

    def get_ajax(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def post_ajax(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)

    def put_ajax(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def delete_ajax(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)
