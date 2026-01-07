release: python manage.py migrate && python manage.py collectstatic --noinput
web: gunicorn pt_jobs.wsgi:application --bind 0.0.0.0:$PORT





