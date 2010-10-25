#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import logging
import StringIO
import urllib
import base64

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api import urlfetch
from google.appengine.ext.webapp import template

from google.appengine.api import memcache

from django.utils import simplejson

import feedparser

##
# This app performs PubSubHubbub subscriptions in javascript.
# It must be called with a GET request (GET subscription, mostly to avoid SOP)  
# You just need to provide :
# - hub.callback REQUIRED. The subscriber's callback URL where notifications should be delivered.
# - hub.mode REQUIRED. The literal string "subscribe" or "unsubscribe", depending on the goal of the request.
# - hub.topic REQUIRED. The topic URL that the subscriber wishes to subscribe to.
# - hub.verify REQUIRED. Keyword describing verification modes supported by this subscriber, as described below. This parameter may be repeated to indicate multiple supported modes.
# - hub.lease_seconds OPTIONAL. Number of seconds for which the subscriber would like to have the subscription active. If not present or an empty value, the subscription will be permanent (or active until automatic refreshing removes the subscription). Hubs MAY choose to respect this value or not, depending on their own policies. This parameter MAY be present for unsubscription requests and MUST be ignored by the hub in that case.
# - hub.secret OPTIONAL. A subscriber-provided secret string that will be used to compute an HMAC digest for authorized content distribution. If not supplied, the HMAC digest will not be present for content distribution requests. This parameter SHOULD only be specified when the request was made over HTTPS [RFC2818]. This parameter MUST be less than 200 bytes in length.
# - hub.verify_token OPTIONAL. A subscriber-provided opaque token that will be echoed back in the verification request to assist the subscriber in identifying which subscription request is being verified. If this is not included, no token will be included in the verification request.
# - superfeedr.login OPTIONAL. Used if no hub was found
# - superfeedr.password OPTIONAL. Used if no hub was found

class MainHandler(webapp.RequestHandler):
  
  def extract_hub(self, url):
    hub = memcache.get(url)
    if hub is not None:
      # good
      return hub
    else:
      hub = None
      try:
        result = urlfetch.fetch(url=url, deadline=10)
        feed = feedparser.parse(result.content)
        for link in feed['feed']['links']:
          if link.rel == "hub" :
            hub = link.href
        if not memcache.add(url, hub, 604800):
          logging.error("Memcache set failed.")
        return hub
      except:
        raise Exception("NotAFeed")

  def subscribe(self, hub, topic, callback, mode="subscribe", verify="sync", lease_seconds=7776000, secret=None, verify_token="", login=None, password=None):
    form_fields = {
      "hub.topic": topic,
      "hub.callback": callback,
      "hub.lease_seconds": lease_seconds
    }
    if mode is None or mode == "":
      form_fields['hub.mode'] = "subscribe"

    if verify is None or verify == "":
      form_fields['hub.verify'] = "sync"
    
    if secret is not None and secret != "" :
      form_fields['hub.secret'] = secret

    if verify_token is not None and verify_token != "" :
      form_fields['hub.verify_token'] = verify_token
    
    headers= {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    if login is not None and login is not "" :
      hub = "http://superfeedr.com/hubbub"
      headers["Authorization"] = "Basic %s" % base64.encodestring('%s:%s' % (login, password))[:-1] 
    
    if hub is None :
      return '{"code": "%s", "body": "%s"}' % ("500", "This feed (is this actually a feed?) doesn't have a hub; If it's a feed, try using http://superfeedr.com")
    else :
     result = urlfetch.fetch(url=hub, payload=urllib.urlencode(form_fields), method=urlfetch.POST, headers = headers)
     return '{"code": "%s", "body": "%s"}' % (result.status_code, result.content.rstrip())
    
    
  def get(self):
    # First thing first : extract the hub url!
    if self.request.get("hub.topic") :
      hub_url = None;
      
      if self.request.get("hub.url") :
        hub_url = self.request.get("hub.url")
      else :
        try :
          hub_url = self.extract_hub(url=self.request.get("hub.topic"))
        except : 
          hub_url = None
      
      result = None
      
      if hub_url is None :
        result = '{"code": "500", "body": "Not a feed!"}'
      else:
        result = self.subscribe(hub=hub_url, topic=self.request.get("hub.topic"), callback=self.request.get("hub.callback"), mode=self.request.get("hub.mode"), verify=self.request.get("hub.verify"), lease_seconds=self.request.get("hub.lease_seconds"), secret=self.request.get("hub.secret"), verify_token=self.request.get("hub.verify_token"), login=self.request.get("superfeedr.login"), password=self.request.get("superfeedr.password"))

      if self.request.get("callback"):
        self.response.out.write(self.request.get("callback") + "(" + result + ")")
      else:
        self.response.out.write(result)
    else :
      self.response.out.write(template.render(os.path.join(os.path.dirname(__file__), 'templates', "index.html"), {}))

def main():
  logging.getLogger().setLevel(logging.INFO) 
  
  application = webapp.WSGIApplication([('/', MainHandler)],
                                         debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
