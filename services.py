from database import Database

# Shared application services live outside main.py so extensions never import the entry point.
db = Database()
