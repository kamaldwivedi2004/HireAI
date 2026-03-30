import certifi
from flask_pymongo import PyMongo
from flask_caching import Cache

mongo = PyMongo()
cache = Cache()


def init_mongo(app):
    try:
        mongo.init_app(
            app,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
        )
    except Exception:
        mongo.init_app(
            app,
            tlsAllowInvalidCertificates=True,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
        )
