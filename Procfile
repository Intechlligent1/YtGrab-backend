web: gunicorn yt_backend.wsgi --log-file - 
#or works good with external database
web: python manage.py migrate && gunicorn yt_backend.wsgi