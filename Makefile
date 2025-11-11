run:
	@echo "Running the server..."
	python manage.py runserver

migrate:
	@echo "Migrating the database..."
	python manage.py makemigrations
	python manage.py migrate

check:
	@echo "Checking the code..."
	flake8 .

test:
	@echo "Running the tests..."
	python manage.py test

install:
	@echo "Installing the requirements..."
	pip install -r requirements.txt

freeze:
	@echo "Freezing the requirements..."
	pip freeze > requirements.txt

dump:
	@echo "Dumping the doc types, journals, doc sub types..."
	python manage.py dumpdata --output json_files/doc_types.json reference.DocumentType
	python manage.py dumpdata --output json_files/journals.json reference.Journal
	python manage.py dumpdata --output json_files/doc_sub_types.json reference.DocumentSubType