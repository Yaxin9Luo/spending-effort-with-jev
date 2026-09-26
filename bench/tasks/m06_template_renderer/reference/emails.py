from minitemplate import render

WELCOME = "<p>Hi {{ user.first_name|default:\"there\" }}, welcome to {{ site|upper }}!</p>"


def welcome_email(user, site):
    return render(WELCOME, {"user": user, "site": site})
