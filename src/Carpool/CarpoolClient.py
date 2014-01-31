import Carpool.ranking
from ConfigParser import ConfigParser
from Examples.ListenerClient import WhatsappListenerClient
from datetime import datetime
import lxml.etree, os

class WhatsappCarpoolClient( WhatsappListenerClient ):

   def __init__( self, keepAlive=False, sendReceipts=False ):
      super( WhatsappCarpoolClient, self ).__init__( keepAlive, sendReceipts )
      self.signalsInterface.registerListener( "group_messageReceived",
                                              self.onGroupMessageReceived )
      config = ConfigParser()
      config.read( os.path.expanduser( "~" ) + "/.yowsup/carpool" )
      self.users = config._sections[ 'Users' ]
      generalConfig = config._sections[ 'General' ]
      self.startTime = datetime.now()
      self.meetingTime = [ int( t ) \
                           for t in generalConfig[ 'meeting_time' ].split( ':' ) ]
      self.meetingLocations = generalConfig[ 'meeting_locations' ]
      self.group = generalConfig[ 'group' ]
      trafficToken = generalConfig.get( 'traffic_token' )
      trafficOrigin = generalConfig.get( 'traffic_origin' )
      trafficDestination = generalConfig.get( 'traffic_destination' )
      self.trafficUrl = None
      if trafficToken and trafficOrigin and trafficDestination:
         self.trafficUrl = 'http://services.my511.org/traffic/getpathlist.aspx?'
         self.trafficUrl += 'token=%s' % trafficToken
         self.trafficUrl += '&o=%s&d=%s' % ( trafficOrigin, trafficDestination )

   def ranking( self ):
      ranking = Carpool.ranking.Ranking( readonly=False )
      msgs = []
      for u in ranking.ranking:
         if u.name not in ranking.today.absents:
            msg = '%s has %s points' % ( u.name, u.score.points )
            if u.name in ranking.today.drivers:
               msg += ' and is driving'
            msgs.append( msg )
      if ranking.today.notes:
         msgs.append( ranking.today.notes )
      ranking.email( broadcast=True )
      if msgs:
         msgs = [ 'Hello carpoolers,' ] + msgs + [ 'Drive safe!' ]
         self.methodsInterface.call( "message_send",
                                     ( self.group, '\n'.join( msgs ) ) )

   def traffic( self ):
      if not self.trafficUrl:
         return
      tree = lxml.etree.parse( self.trafficUrl )
      travelTime = tree.getroot().xpath( "//currentTravelTime/text()" )[ 0 ]
      msg = "The current travel time is %s minutes" % travelTime
      self.methodsInterface.call( "message_send", ( self.group, msg ) )

   def login( self, username, password, ranking=False, traffic=False, message=None ):
      self.username = username
      self.methodsInterface.call( "auth_login", ( username, password ) )
      if ranking:
         self.ranking()
      if traffic:
         self.traffic()
      if message:
         self.methodsInterface.call( "message_send", ( self.group, message ) )

   def onGroupMessageReceived( self, msgId, fromAttribute, author, msgData,
                               timestamp, wantsReceipt, pushName ):
      date = datetime.fromtimestamp( timestamp )
      if date < self.startTime:
         return
      try:
         user = self.users[ author.split( '@' )[ 0 ] ]
      except KeyError:
         user = author
      msgData = msgData.lower()
      if msgData == 'version':
         response = 'See https://github.com/7AC/yowsup'
         self.methodsInterface.call( "message_send", ( fromAttribute, response ) )
      elif msgData in self.meetingLocations:
         now = datetime.now()
         meetingTime = datetime( now.year, now.month, now.day, self.meetingTime[ 0 ],
                                 self.meetingTime[ 1 ] )
         delay = ( date - meetingTime )
         if delay.days == 0 and delay.seconds < 1800 and delay.seconds > 60:
            response = "%s is %d minutes late" % ( user, delay.seconds / 60 )
            self.methodsInterface.call( "message_send", ( fromAttribute, response ) )
      elif msgData == 'ranking':
         response = Carpool.ranking.Ranking().renderAscii( brief=True )
         self.methodsInterface.call( "message_send", ( fromAttribute, response ) )
