import datetime
import enum
import pymongo
import redis
import mongoengine as mongo
from django.conf import settings
from django.contrib.auth.models import User
from apps.rss_feeds.models import MStory, Feed
from apps.reader.models import UserSubscription
from apps.analyzer.models import MClassifierTitle, MClassifierAuthor, MClassifierFeed, MClassifierTag
from apps.analyzer.models import compute_story_score
from utils import log as logging
from utils import mongoengine_fields


class NotificationFrequency(enum.Enum):
    immediately = 1
    hour_1 = 2
    hour_6 = 3
    hour_12 = 4
    hour_24 = 5


class MUserFeedNotification(mongo.Document):
    '''A user's notifications of a single feed.'''
    user_id                  = mongo.IntField()
    feed_id                  = mongo.IntField()
    frequency                = mongoengine_fields.IntEnumField(NotificationFrequency)
    is_focus                 = mongo.BooleanField()
    last_notification_date   = mongo.DateTimeField(default=datetime.datetime.now)
    is_email                 = mongo.BooleanField()
    is_web                   = mongo.BooleanField()
    is_ios                   = mongo.BooleanField()
    is_android               = mongo.BooleanField()
    
    meta = {
        'collection': 'notifications',
        'indexes': ['feed_id',
                    {'fields': ['user_id', 'feed_id'], 
                     'unique': True,
                     'types': False, }],
        'allow_inheritance': False,
    }
    
    def __unicode__(self):
        notification_types = []
        if self.is_email: notification_types.append('email')
        if self.is_web: notification_types.append('web')
        if self.is_ios: notification_types.append('ios')
        if self.is_android: notification_types.append('android')

        return "%s/%s: %s -> %s" % (
            User.objects.get(pk=self.user_id).username,
            Feed.get_feed_by_id(self.feed_id),
            ','.join(notification_types),
            self.last_notification_date,
        )
    
    @classmethod
    def users_for_feed(cls, feed_id):
        notifications = cls.objects.filter(feed_id=feed_id)
    
        return notifications
    
    @classmethod
    def feeds_for_user(cls, user_id):
        notifications = cls.objects.filter(user_id=user_id)
        notifications_by_feed = {}

        for feed in notifications:
            notifications_by_feed[feed.feed_id] = {
                'notification_types': [],
                'notification_filter': "focus" if feed.is_focus else "unread",
            }
            if feed.is_email: notifications_by_feed[feed.feed_id]['notification_types'].append('email')
            if feed.is_web: notifications_by_feed[feed.feed_id]['notification_types'].append('web')
            if feed.is_ios: notifications_by_feed[feed.feed_id]['notification_types'].append('ios')
            if feed.is_android: notifications_by_feed[feed.feed_id]['notification_types'].append('android')
            
        return notifications_by_feed
    
    @classmethod
    def push_feed_notifications(cls, feed_id, new_stories, force=False):
        feed = Feed.get_by_id(feed_id)
        notifications = MUserFeedNotification.users_for_feed(feed.pk)
        logging.debug("   ---> [%-30s] ~FCPushing out ~SB%s notifications~SN for ~FB~SB%s stories" % (
                      feed, len(notifications), new_stories))
        r = redis.Redis(connection_pool=settings.REDIS_STORY_HASH_POOL)
        
        latest_story_hashes = r.zrange("zF:%s" % feed.pk, -1 * new_stories, -1)
        mstories = MStory.objects.filter(story_hash__in=latest_story_hashes).order_by('-story_date')
        stories = Feed.format_stories(mstories)
        
        for feed_notification in notifications:
            last_notification_date = feed_notification.last_notification_date
            classifiers = feed_notification.classifiers()
            if not classifiers:
                continue
            for story in stories:
                if story['story_date'] < last_notification_date and not force:
                    continue
                if story['story_date'] > feed_notification.last_notification_date:
                    feed_notification.last_notification_date = story['story_date']
                    feed_notification.save()
                feed_notification.push_notifications(story, classifiers)
    
    def classifiers(self):
        try:
            usersub = UserSubscription.objects.get(user=self.user_id, feed=self.feed_id)
        except UserSubscription.DoesNotExist:
            return None
            
        classifiers = {}
        if usersub.is_trained:
            user = User.objects.get(pk=self.user_id)
            classifiers['feeds']   = list(MClassifierFeed.objects(user_id=self.user_id, feed_id=self.feed_id,
                                                                 social_user_id=0))
            classifiers['authors'] = list(MClassifierAuthor.objects(user_id=self.user_id, feed_id=self.feed_id))
            classifiers['titles']  = list(MClassifierTitle.objects(user_id=self.user_id, feed_id=self.feed_id))
            classifiers['tags']    = list(MClassifierTag.objects(user_id=self.user_id, feed_id=self.feed_id))
            
        return classifiers
        
    def push_notifications(self, story, classifiers):
        story_score = self.story_score(story, classifiers)
        if self.is_focus and story_score <= 0:
            return
        elif story_score < 0:
            return
        
        user = User.objects.get(pk=self.user_id)
        logging.user(user, "~FCSending push notification: %s/%s (score: %s)" % (story['story_title'][:40], story['story_hash'], story_score))
        
        self.send_web(story)
        self.send_ios(story)
        self.send_android(story)
        self.send_email(story)
    
    def send_web(self, story):
        if not self.is_web: return
        
        user = User.objects.get(pk=self.user_id)
        r = redis.Redis(connection_pool=settings.REDIS_PUBSUB_POOL)
        r.publish(user.username, 'notification:%s,%s' % (story['story_hash'], story['story_title']))
    
    def send_ios(self, story):
        if not self.is_ios: return
        
        
    def send_android(self, story):
        if not self.is_android: return
        
        
    def send_email(self, story):
        if not self.is_email: return
        
    def story_score(self, story, classifiers):
        score = compute_story_score(story, classifier_titles=classifiers['titles'], 
                                    classifier_authors=classifiers['authors'], 
                                    classifier_tags=classifiers['tags'],
                                    classifier_feeds=classifiers['feeds'])
        
        return score
                
