web: python manage.py check_repair_readiness && python manage.py migrate && python manage.py collectstatic --noinput && gunicorn pt_jobs.wsgi:application --bind 0.0.0.0:$PORT
