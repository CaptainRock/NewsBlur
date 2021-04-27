import datetime
from django.conf import settings
from django.shortcuts import render
from django.views import View

class TasksCodes(View):

    def get(self, request):
        data = dict((("_%s" % s['_id'], s['feeds']) for s in self.stats))
        
        return render(request, 'monitor/prometheus_data.html', {"data": data})
    
    @property
    def stats(self):        
        stats = settings.MONGOANALYTICSDB.nbanalytics.feed_fetches.aggregate([{
            "$match": {
                "date": {
                    "$gt": datetime.datetime.now() - datetime.timedelta(minutes=5),
                },
            },
        }, {
            "$group": {
                "_id"   : "$feed_code",
                "feeds" : {"$sum": 1},
            },
        }])
        
        return list(stats)
        