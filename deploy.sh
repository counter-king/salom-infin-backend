#!/bin/bash

echo "Salom"
echo "Start deploy"
echo "Get changes from git"
git pull
echo "Activate virtualenv"
source venv/bin/activate
echo "Install requirements"
pip install --proxy=http://172.25.42.94:8181  -r requirements.txt
echo "Migration if needed"
python manage.py migrate
echo "Load message to database"
python manage.py loaddata json_files/error_messages.json
python manage.py loaddata json_files/journals.json
python manage.py loaddata json_files/doc_types.json
python manage.py loaddata json_files/doc_sub_types.json
python manage.py loaddata json_files/action_text.json
python manage.py loaddata json_files/compose_statuses.json
echo "Restart gunicorn"
sudo systemctl restart gunicorn
echo "Restart Celery"
sudo systemctl restart celery
echo "Restart Celery service"
sudo systemctl restart celery.service
echo "Restart daphne"
sudo systemctl restart daphne
echo "Enjoy your deployment"
