from django.http import HttpResponseForbidden
from django.shortcuts import redirect

def dynamodb_login_required(view_func):
    """
    Custom decorator to ensure the user is authenticated using DynamoDB session-based auth.
    """
    def wrapped_view(request, *args, **kwargs):
        # Check if the user is authenticated via session
        user = request.session.get('user')
        if not user or not user.get('is_authenticated'):
            # Redirect to login page if not authenticated
            return redirect('login')  # Replace 'login' with the name of your login URL
        return view_func(request, *args, **kwargs)
    return wrapped_view