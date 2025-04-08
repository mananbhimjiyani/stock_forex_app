from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse

def dynamodb_login_required(view_func):
    """
    Custom decorator to ensure the user is authenticated using DynamoDB session-based auth.
    Redirects unauthenticated users to the login page with the 'next' parameter.
    """
    def wrapped_view(request, *args, **kwargs):
        # Check if the user is authenticated via session
        user = request.session.get('user')
        if not user or not user.get('is_authenticated'):
            # Redirect to login page with 'next' parameter
            next_url = request.get_full_path()  # Get the current URL
            login_url = f"{reverse('login')}?next={next_url}"
            return HttpResponseRedirect(login_url)
        return view_func(request, *args, **kwargs)
    return wrapped_view