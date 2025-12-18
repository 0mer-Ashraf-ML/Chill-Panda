import sqlite3

def get_conn():
    return sqlite3.connect('chillpanda.db')