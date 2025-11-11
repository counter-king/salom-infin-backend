import os
import cx_Oracle

from django.db import connection

HOST = os.getenv('IABS_DB_HOST')
PORT = os.getenv('IABS_DB_PORT')
SID = os.getenv('IABS_DB_NAME')
USER = os.getenv('IABS_DB_USER')
PASSWORD = os.getenv('IABS_DB_PASSWORD')
dsn_tns = cx_Oracle.makedsn(HOST, PORT, SID)


def oracle_connection():
    connection = cx_Oracle.connect(user=USER, password=PASSWORD, dsn=dsn_tns)

    return connection


def django_connection():
    return connection


def db_column_name(cursor):
    """ Given a DB QUERY cursor object that has been executed, returns
    a dictionary that maps each field name to a column index; 0 and up. """
    results = {}
    column = 0
    for d in cursor.description:
        results[d[0]] = column
        column = column + 1

    return results
