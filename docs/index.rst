.. django-braces documentation master file, created by
   sphinx-quickstart on Mon Apr 30 10:31:44 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to django-braces's documentation!
=========================================

You can view the code of our project or fork it and add your own mixins (please, send them back to us), on `Github`_.

LoginRequiredMixin
==================

This mixin is rather simple and is generally the first inherited class in any of our views. If we don't have an authenticated user 
there's no need to go any further. If you've used Django before you are probably familiar with the ``login_required`` decorator. 
All we are doing here is requiring a user to be authenticated to be able to get to this view.

While this doesn't look like much, it frees us up from having to manually overload the dispatch method on every single view that 
requires a user to be authenticated. If that's all that is needed on this view, we just saved 3 lines of code. Example usage below.

::

    from django.views.generic import TemplateView

    from braces.views import LoginRequiredMixin


    class SomeSecretView(LoginRequiredMixin, TemplateView):
        template_name = "path/to/template.html"

        def get(self, request):
            return self.render_to_response({})

AnonymousRequiredMixin
======================

Simple mixin to restrict views for anonymous users only, authenticated users will be 
redirected on the content of ``settings.LOGIN_URL`` by default. Use the ``redirect_url`` 
class attribute or ``get_redirect_url`` to change the redirect.

::

    from django.views.generic import TemplateView

    from braces.views import LoginRequiredMixin


    class PublicForNonAuthenticadUserView(AnonymousRequiredMixin, TemplateView):
        template_name = "path/to/template.html"

        def get(self, request):
            return self.render_to_response({})

PermissionRequiredMixin
=======================

This mixin was originally written, I believe, by `Daniel Sokolowski`_ (`code here`_), but we have updated it to eliminate an unneeded render if the permissions check fails.

The permission required mixin has been very handy for our client's custom CMS. Again, rather than overloading the 
dispatch method manually on every view that needs to check for the existence of a permission, we inherit this class 
and set the ``permission_required`` class attribute on our view. If you don't specify ``permission_required`` on 
your view, an ``ImproperlyConfigured`` exception is raised reminding you that you haven't set it.

The one limitation of this mixin is that it can **only** accept a single permission. It would need to be modified to 
handle more than one. We haven't needed that yet, so this has worked out well for us.

In our normal use case for this mixin, ``LoginRequiredMixin`` comes first, then the ``PermissionRequiredMixin``. If we 
don't have an authenticated user, there is no sense in checking for any permissions.

    .. role:: info-label
        :class: "label label-info"

    :info-label:`note` If you are using Django's built in auth system, ``superusers`` automatically have all permissions in your system.

::

    from braces.views import LoginRequiredMixin, PermissionRequiredMixin


    class SomeProtectedView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
        permission_required = "auth.change_user"
        template_name = "path/to/template.html"

SuperuserRequiredMixin
======================

Another permission-based mixin. This is specifically for requiring a user to be a superuser. Comes in handy for tools that only privileged 
users should have access to.

::

    from braces.views import LoginRequiredMixin, SuperuserRequiredMixin


    class SomeSuperuserView(LoginRequiredMixin, SuperuserRequiredMixin, TemplateView):
        template_name = "path/to/template.html"

UserFormKwargsMixin
===================

In our clients CMS, we have a lot of form-based views that require a user to be passed in for permission-based form tools. For example, 
only superusers can delete or disable certain objects. To custom tailor the form for users, we have to pass that user instance into the form 
and based on their permission level, change certain fields or add specific options within the forms ``__init__`` method.

This mixin automates the process of overloading the ``get_form_kwargs`` (this method is available in any generic view which handles a form) method 
and stuffs the user instance into the form kwargs. We can then pop the user off in the form and do with it what we need. **Always** remember 
to pop the user from the kwargs before calling ``super`` on your form, otherwise the form gets an unexpected keyword argument and everything 
blows up. Example usage:

::

    from django.views.generic import CreateView

    from braces.views import LoginRequiredMixin, UserFormKwargsMixin
    from next.example import UserForm


    class SomeSecretView(LoginRequiredMixin, UserFormKwargsMixin,
        TemplateView):

        form_class = UserForm
        model = User
        template_name = "path/to/template.html"

This obviously pairs very nicely with the following ``Form`` mixin.


UserKwargModelFormMixin
=======================

The ``UserKwargModelFormMixin`` is a new form mixin we just implemented this week to go along with our ``UserFormKwargsMixin``. 
This becomes the first inherited class of our forms that receive the user keyword argument. With this mixin, we have automated 
the popping off of the keyword argument in our form and no longer have to do it manually on every form that works this way. 
While this may be overkill for a weekend project, for us, it speeds up adding new features. Example usage:

::

    from braces.forms import UserKwargModelFormMixin

    class UserForm(UserKwargModelFormMixin, forms.ModelForm):
        class Meta:
            model = User

        def __init__(self, *args, **kwargs):
            super(UserForm, self).__init__(*args, **kwargs):

            if not self.user.is_superuser:
                del self.fields["group"]


SuccessURLRedirectListMixin
===========================

The ``SuccessURLRedirectListMixin`` is a bit more tailored to how we handle CRUD_ within our CMS. Our CMS's workflow, by design, 
redirects the user to the ``ListView`` for whatever model they are working with, whether they are creating a new instance, editing 
an existing one or deleting one. Rather than having to override ``get_success_url`` on every view, we simply use this mixin and pass it 
a reversible route name. Example:

::

    # urls.py
    url(r"^users/$", UserListView.as_view(), name="cms_users_list"),

    # views.py
    from braces.views import (LoginRequiredMixin, PermissionRequiredMixin,
        SuccessURLRedirectListMixin)


    class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin,
        SuccessURLRedirectListMixin, CreateView):

        form_class = UserForm
        model = User
        permission_required = "auth.add_user"
        success_list_url = "cms_users_list"
        ...


SetHeadlineMixin
================

The ``SetHeadlineMixin`` is a newer edition to our client's CMS. It allows us to *statically* or *programmatically* set the headline of any 
of our views. We like to write as few templates as possible, so a mixin like this helps us reuse generic templates. Its usage is amazingly 
straightforward and works much like Django's built-in ``get_queryset`` method. This mixin has two ways of being used.

Static Example
--------------

::

    from braces.views import SetHeadlineMixin


    class HeadlineView(SetHeadlineMixin, TemplateView):
        headline = "This is our headline"
        template_name = "path/to/template.html"


Dynamic Example
---------------

::

    from datetime import date

    from braces.views import SetHeadlineMixin


    class HeadlineView(SetHeadlineMixin, TemplateView):
        template_name = "path/to/template.html"

        def get_headline(self):
            return u"This is our headline for %s" % date.today().isoformat()

In both usages, in the template, just print out ``{{ headline }}`` to show the generated headline.


CreateAndRedirectToEditView
===========================

Mostly used for CRUD, where you're going to create an object and then move direct to the update view for that object. Your URL for the update view has to accept a PK for the object.

::

    # urls.py
    ...
    url(r"^users/create/$", UserCreateView.as_view(), name="cms_users_create"),
    url(r"^users/edit/(?P<pk>\d+)/$", UserUpdateView.as_view(), name="cms_users_update"),
    ...

    # views.py
    from braces.views import CreateAndRedirectToEditView


    class UserCreateView(CreateAndRedirectToEditView, CreateView):
        model = User
        ...


SelectRelatedMixin
==================

A simple mixin which allows you to specify a list or tuple of foreign key fields to perform a select_related on.

::

    # views.py
    from django.views.generic import DetailView

    from braces.views import SelectRelatedMixin

    from profiles.models import Profile


    class UserProfileView(SelectRelatedMixin, DetailView):
        model = Profile
        select_related = ["user"]
        template_name = "profiles/detail.html"

StaffuserRequiredMixin
======================

A mixin to support those cases where you want to give staff access to a view.

::

    # views.py
    from django.views.generic import DetailView

    from braces.views import StaffuserRequiredMixin

    class SomeStaffuserView(LoginRequiredMixin, StaffuserRequiredMixin, TemplateView):
        template_name = "path/to/template.html"


SimpleListView
==============

This view is like the generic ``ListView`` but use only ``get_template`` to find template and 
not an automatic process on ``get_template_names``.

Use it like ``ListView`` but you only have to define the ``template_name`` class attribute.

DirectDeleteView
================

This inherit from the generic ``BaseDeleteView`` to directly delete an object without 
template rendering on GET or POST methods and redirect to an URL.

Like ``BaseDeleteView`` this is using the ``get_object`` method to retrieve the objet to 
delete.

The  ``success_url`` class attribute or ``get_success_url`` method or must be correctly 
filled.

::

    # views.py
    from braces.views import DirectDeleteView
    from myguestbook.models import Post
    
    class PostDeleteView(DirectDeleteView):
        """
        Directly delete a post and redirect to the guestbook index
        """
        model = Post
        success_url = '/guestbook/'

DownloadMixin
==============

Simple Mixin to send a downloadable content.

Inherits must :

* Fill the ``mimetype`` class attribute with the mimetype content to send;
* Implement the ``get_filename`` method to return the filename to use in the 
  response headers;
* Implement the ``get_content`` method to return the content to send as 
  downloadable.

If the content is a not a string, it is assumed to be a file object to send as 
the content with its ``read`` method and to close with its ``close`` method.

Optionnaly implement a ``close_content`` to close specifics objects linked to 
content file object, if it does not exists a try will be made on a ``close`` method 
on the content file object.

A ``get_filename_timestamp`` method is included to return a timestamp to use in your 
filename if needed, his date format is defined in the ``timestamp_format`` class 
attribute (in a suitable way to use with ``strftime`` on a datetime object).

Finally the content is sended from the ``render_response`` method and as like 
in a ``TemplateView`` the context kwargs are given to the method so you can prepare some 
*stuff* in the ``get_context_data`` method.

::
    
    # views.py
    from django.views.generic.base import TemplateResponseMixin, View
    
    from braces import DownloadMixin
    
    class ReportPdfView(DownloadMixin, View):
        """
        Generic view to download a pdf file
        """
        mimetype = 'application/pdf'
        filename_format = "report_{timestamp}.pdf"
        
        def get_context_data(self, **kwargs):
            context = super(ReportPdfView, self).get_context_data(**kwargs)
            context.update({
                'timestamp': self.get_filename_timestamp(),
            })
            return context
        
        def get_filename(self, context):
            return self.filename_format.format(**context)
        
        def get_content(self, context):
            return open("myfile.pdf", "r")

JSONMixin
=========

Simple Mixin to compile data as JSON
    
This does not implement a direct response, you have to return it with the ``json_to_response`` method in your view.

Additionally you have some class attributes to change some behaviours :

* ``mimetype`` if you want to return a different mimetype than the default 
  one : ``application/json``;
* ``json_indent`` (an integer) to indent your JSON if needed;
* ``json_encoder`` to give a special encoder to use to dump your JSON if you have some 
  objects (like a datetime) not supported by the ``json`` Python module.

JSONResponseMixin
=================

Mixin to directly return a JSON response.

This inherit from the `JSONMixin`_ behaviours and options.

It uses the context as the object to serialize in JSON, so your view should implement 
the ``get_context_data`` method to return what you want to dump as JSON.

::
    
    # views.py
    from django.views.generic.base import View
    
    from braces import JSONResponseMixin
    
    class MyJsonView(JSONResponseMixin, View):
        json_indent = 4
        
        def get_context_data(self, **kwargs):
            return {
                'mylist': range(0, 42),
                'mystring': "foobar",
            }
    
        def get(self, request, *args, **kwargs):
            context = self.get_context_data(**kwargs)
            return self.render_to_response(context)

DownloadMixin
=============

Simple Mixin to send a downloadable content

Inherits must have :

* Filled the ``mimetype`` class attribute with the content mimetype to send;
* Implementation of ``get_filename()`` that return the filename to use in response headers;
* Implementation of ``get_content()`` that return the content to send as downloadable.

If the content is a not a string, it is assumed to be a fileobject to send as the content with its ``read()`` method.

Optionnaly implement a ``close_content()`` to close specifics objects linked to content fileobject, if it does not exists a try will be made on a close() method on the content fileobject;

A ``get_filename_timestamp`` method is implemented to return a timestamp to use in your filename if needed, his date format is defined in the ``timestamp_format`` class attribute (in a suitable way to use with strftime on a datetime object).

ExtendTemplateVariableMixin
===========================

Get the extend variable to use in the template.

Default behaviour is to switch on two templates depending on the request is an Ajax request or not. If it's Ajax the ``modal_extend_template`` class attribute is used else the default extend will be the content of ``default_extend_template``.

This mixin only put a ``template_extend`` variable in the template context, your template have to use it, this does not modify itself the response nor the template.

ListAppendView
==============

A view to display an object list with a form to append a new object to the list. 

An example usage is a message list in a guestbook where you would want to display a form after the list to append a new message.

This view re-use some code from FormMixin and SimpleListView, because it does not seems possible to simply mix them.

Need the ``model`` and ``form_class`` class attributes for the form parts and the required ones by ``BaseListView``. The ``get_success_url`` method should be filled too.

The additional ``locked_form`` method class is used to disable form (like if your list object is closed to new object), also you can implement the ``is_locked_form`` method if needed.

::
    
    # views.py
    
    from braces import ListAppendView
    
    from myguestbook.models import Post
    from myguestbook.forms import PostCreateForm
    
    class ThreadView(ListAppendView):
        """
        Message list with a form to append a new message, after validated form the user 
        is redirected on the list
        """
        model = Post
        form_class = PostCreateForm
        template_name = 'guestbook/message_list.html'
        paginate_by = 42
        context_object_name = 'object_list'
        success_url = '/guestbook/'
        queryset = Post.objects.all()

DetailListAppendView
====================

A view to display a parent object details, list his "children" and display a form to append a new child

Have the same behaviours than `ListAppendView`_ but get the parent object before doing anything.

``model`` and ``form_class`` class attributes are for the children, ``context_parent_object_name`` is used to name the parent variable in the template context.

The ``get_parent_object`` method must be defined to return the parent instance and the ``get_queryset`` method should be defined to make a queryset exclusively on the parent children.

The parent object is also given to the append form, under the name defined with the ``context_parent_object_name`` class attribute. Your Form should be aware of this.

ExcelExportView
===============

A generic view to export an Excel file.

Inherits must implement at least the ``get_content()`` method to return the content file 
object. This is where you have to build your excel file object to send 
(``ExcelExportView`` does not contain any specific methods to build an Excel file).

::
    
    # views.py
    from braces import ExcelExportView
    
    class ReportExcelView(ExcelExportView):
        filename_format = "worksheet-{timestamp}.xls"
        
        def get_content(self, context, **response_kwargs):
            # build your excel file here
            content = ...
            return content

.. _Daniel Sokolowski: https://github.com/danols
.. _code here: https://github.com/lukaszb/django-guardian/issues/48
.. _CRUD: http://en.wikipedia.org/wiki/Create,_read,_update_and_delete

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. _Github: https://github.com/brack3t/django-braces
