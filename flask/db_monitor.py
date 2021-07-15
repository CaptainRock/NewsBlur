from flask import Flask, abort
import flask_settings as settings
import psycopg2
try:
    import MySQLdb
except ImportError:
    pass
import pymongo
import redis
import pyes
app = Flask(__name__)

PRIMARY_STATE = 1
SECONDARY_STATE = 2

@app.route("/db_check/postgres")
def db_check_postgres():
    connect_params = "dbname='%s' user='%s' password='%s' host='%s' port='%s'" % (
        settings.DATABASES['default']['NAME'],
        settings.DATABASES['default']['USER'],
        settings.DATABASES['default']['PASSWORD'],
        settings.DATABASES['default']['HOST'],
        settings.DATABASES['default']['PORT'],
    )
    try:
        conn = psycopg2.connect(connect_params)
    except:
        print " ---> Postgres can't connect to the database: %s" % connect_params
        abort(502)

    cur = conn.cursor()
    cur.execute("""SELECT id FROM feeds ORDER BY feeds.id DESC LIMIT 1""")
    rows = cur.fetchall()
    for row in rows:
        return unicode(row[0])
    
    abort(404)

@app.route("/db_check/mysql")
def db_check_mysql():
    connect_params = "dbname='%s' user='%s' password='%s' host='%s' port='%s'" % (
        settings.DATABASES['default']['NAME'],
        settings.DATABASES['default']['USER'],
        settings.DATABASES['default']['PASSWORD'],
        settings.DATABASES['default']['HOST'],
        settings.DATABASES['default']['PORT'],
    )
    try:

        conn = MySQLdb.connect(host=settings.DATABASES['default']['HOST'],
                               port=settings.DATABASES['default']['PORT'],
                               user=settings.DATABASES['default']['USER'],
                               passwd=settings.DATABASES['default']['PASSWORD'],
                               db=settings.DATABASES['default']['NAME'])
    except:
        print " ---> Mysql can't connect to the database: %s" % connect_params
        abort(502)

    cur = conn.cursor()
    cur.execute("""SELECT id FROM feeds ORDER BY feeds.id DESC LIMIT 1""")
    rows = cur.fetchall()
    for row in rows:
        return unicode(row[0])
    
    abort(404)

@app.route("/db_check/mongo")
def db_check_mongo():
    try:
        client = pymongo.MongoClient('mongodb://%s' % settings.MONGO_DB['host'])
        db = client.newsblur
    except:
        abort(502)
    
    stories = db.stories.count()
    if not stories:
        abort(503)
    
    status = client.admin.command('replSetGetStatus')
    members = status['members']
    # primary_optime = None
    # oldest_secondary_optime = None
    # for member in members:
    #     member_state = member['state']
    #     optime = member['optime']
    #     if member_state == PRIMARY_STATE:
    #         primary_optime = optime.time
    #     elif member_state == SECONDARY_STATE:
    #         if not oldest_secondary_optime or optime.time < oldest_secondary_optime:
    #             oldest_secondary_optime = optime.time

    # if not primary_optime or not oldest_secondary_optime:
    #     abort(505)

    # if primary_optime - oldest_secondary_optime > 100:
    #     abort(506)

    return unicode(stories)

@app.route("/db_check/redis")
def db_check_redis():
    redis_host = getattr(settings, 'REDIS', {'host': 'db_redis'})
    try:
        r = redis.Redis(redis_host['host'], db=0)
    except:
        abort(502)
    
    randkey = r.randomkey()
    if randkey:
        return unicode(randkey)
    else:
        abort(404)

@app.route("/db_check/redis_story")
def db_check_redis_story():
    redis_host = getattr(settings, 'REDIS_STORY', {'host': 'db_redis_story'})
    try:
        r = redis.Redis(redis_host['host'], db=1)
    except:
        abort(502)
    
    randkey = r.randomkey()
    if randkey:
        return unicode(randkey)
    else:
        abort(404)

@app.route("/db_check/redis_sessions")
def db_check_redis_sessions():
    redis_host = getattr(settings, 'REDIS_SESSIONS', {'host': 'db_redis_sessions'})
    try:
        r = redis.Redis(redis_host['host'], db=5)
    except:
        abort(502)
    
    randkey = r.randomkey()
    if randkey:
        return unicode(randkey)
    else:
        abort(404)

@app.route("/db_check/redis_pubsub")
def db_check_redis_pubsub():
    redis_host = getattr(settings, 'REDIS_PUBSUB', {'host': 'db_redis_pubsub'})
    try:
        r = redis.Redis(redis_host['host'], db=1)
    except:
        abort(503)
    
    try:
        pubsub_numpat = r.pubsub_numpat()
    except:
        abort(504)

    if isinstance(pubsub_numpat, long):
        return str(pubsub_numpat)
    else:
        abort(505)

@app.route("/db_check/elasticsearch")
def db_check_elasticsearch():
    es_host = getattr(settings, 'ELASTICSEARCH_FEED_HOSTS', ['db_search_feed:9200'])
    try:
        conn = pyes.ES(es_host)
    except:
        abort(502)
    
    if conn.indices.exists_index('feeds-index'):
        return unicode("Index exists, but didn't try search")
        # query = pyes.query.TermQuery("title", "daring fireball")
        # results = conn.search(query=query, size=1, doc_types=['feeds-type'], sort="num_subscribers:desc")
        # for result in results:
        #     return unicode(result)
        # else:
        #     abort(404)
    else:
        abort(404)    

if __name__ == "__main__":
    app.run(host="0.0.0.0")
