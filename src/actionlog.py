from __future__ import print_function
import requests
import json
import time
import settings
import re
import random
import twitter

#twitter oAuth credentials -- SHOULD BE MOVED TO SETTINGS
api=twitter.Api(consumer_key='',consumer_secret='',access_token_key='',access_token_secret='')

#Variable Initialization
#list of passcodes 
pclist=[]
SLEEP_SECONDS = 1

class UnexpectedResultException(Exception):
    pass

class IngressActionMonitor():
    def __init__(self):
        self.minTimestampMs = -1
        
        if settings.CSRF_TOKEN == '':
            raise ValueError("Please specify valid csrf token setting")
        if settings.SESSION_ID == '':
            raise ValueError("Please specify valid session id setting")
        
    def write_state(self):
        f=open(settings.STATEFILE, 'w+')
        try:
            f.write(str(self.minTimestampMs))
        finally:
            f.close()
    
    def load_state(self):
        f=open(settings.STATEFILE, 'r+')
        try:
            text = f.read()
            if text:
                self.minTimestampMs = int(text)
                print('Starting at time: ', text)
        finally:
            f.close()

    def getChat(self, minTimestampMs):
        url='http://www.ingress.com/rpc/dashboard.getPaginatedPlextsV2'
        cookies = dict(csrftoken=settings.CSRF_TOKEN,
                         ACSID=settings.SESSION_ID,
                         )
        cookies['ingress.intelmap.type'] = '0'
        cookies['ingress.intelmap.lat'] = '83.79204408779546'
        cookies['ingress.intelmap.lng'] = '-85.95703125'
        cookies['ingress.intelmap.zoom'] = '1'
        headers = {"X-Requested-With": "XMLHttpRequest",
                   "X-CSRFToken": settings.CSRF_TOKEN,
                   "Referer": r"http://ingress.com/intel",
                   "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.95 Safari/537.11"}
        print (minTimestampMs)
        data = {"desiredNumItems":150,"minLatE6":-30448674,"minLngE6":-180000000,"maxLatE6":89566639,"maxLngE6":180000000,"minTimestampMs":minTimestampMs,"maxTimestampMs":-1,"method":"dashboard.getPaginatedPlextsV2"}
        #data['ascendingTimestampOrder'] = True
		
        try:
            r = requests.post(url, data=json.dumps(data), headers=headers, cookies=cookies)
            return r.text
        except requests.ConnectionError:
            print ("Connection Error")
			
    def messagegen(self):
        jsonStr = self.getChat(self.minTimestampMs)
        try:
            responseItems = json.loads(jsonStr)
        #print(responseItems)
            if 'result' not in responseItems:
                if 'error' in responseItems:
                    print(str(responseItems))
                else:
                    print(responseItems)
                    #pass
            else:
                responseItemsOrderedAsc = responseItems['result']
                responseItemsOrderedAsc.reverse()
                for message in responseItemsOrderedAsc:
                    yield message
                    self.minTimestampMs = message[1] + 1
        except (ValueError, TypeError):
            responseItems = jsonStr
            print(responseItems.encode('ascii', 'ignore'))
    
    def actiongen(self):
        messages = self.messagegen()
        for message in messages:
			if message[2]['plext']['plextType'] == 'PLAYER_GENERATED': #Extract plaintext message out of update
				txt=message[2]['plext']['text']
				print (txt.encode('ascii', 'ignore'))
				re1='(\\d+)'	# Integer Number 1
				re2='([p-z])'	# Any Single Word Character (Not Whitespace) 1
				re3='([a-h])'	# Any Single Word Character (Not Whitespace) 2
				re4='(\\d+)'	# Integer Number 2
				re5='((?:[a-z][a-z]+))'	# Word 1
				re6='(\\d+)'	# Integer Number 3
				re7='(.)'	# Any Single Word Character (Not Whitespace) 3 CHANGED FROM P-z
				re8='(.)'	# Any Single Character 1
				re9='([p-z])'	# Any Single Word Character (Not Whitespace) 4
				
				## Regex search for passcodes ## Thanks to Pierluigi Failla
				rg = re.compile(re1+re2+re3+re4+re5+re6+re7+re8+re9,re.IGNORECASE|re.DOTALL)
				m = rg.search(txt)
				if m:
					int1=m.group(1)
					w1=m.group(2)
					w2=m.group(3)
					int2=m.group(4)
					word1=m.group(5)
					int3=m.group(6)
					w3=m.group(7)
					c1=m.group(8)
					w4=m.group(9)
					txt2='"'+int1+w1+w2+int2+word1+int3+w3+c1+w4+'"'
					return [txt2]
        return ["no comm"]
					
    def monitor(self):
        self.load_state()
        while True:
            for action in self.actiongen():
                yield action
            self.write_state()
            time.sleep(SLEEP_SECONDS)

def log_lines():
    global pclist
    f = open(settings.LOGFILE, 'r')
    try:
        f.seek(0,2)
        while True:
            line = f.readline()
            yield line #None if no new line
    finally:
        f.close()

def postCode(passcode):
    url='http://www.ingress.com/rpc/dashboard.redeemReward'
    
    cookies = dict(csrftoken=settings.CSRF_TOKEN,
                     ACSID=settings.SESSION_ID,
                     )
    cookies['ingress.intelmap.type'] = '0'
    cookies['ingress.intelmap.lat'] = '83.79204408779546'
    cookies['ingress.intelmap.lng'] = '-85.95703125'
    cookies['ingress.intelmap.zoom'] = '1'
    headers = {"X-Requested-With": "XMLHttpRequest",
               "X-CSRFToken": settings.CSRF_TOKEN,
               "Referer": r"http://ingress.com/intel",
               "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.95 Safari/537.11"}
    data = {"method":"dashboard.redeemReward", "passcode":passcode}
    
    r = requests.post(url, data=json.dumps(data), headers=headers, cookies=cookies)
    return r.text

if __name__ == '__main__':
    monitor = IngressActionMonitor()
    f = open(settings.LOGFILE, 'a', 0)
    try:
        for action in monitor.monitor():
            jsonStr = json.dumps(action)
            if str(jsonStr).strip('"') != 'no comm': #no comm indicates message is player data, not chat data
                curpc = str(jsonStr).strip('"').strip('\\').strip('"')
                print(curpc, file=f) # print to logfile
                if curpc not in pclist: #Has code already been posted?
					response = postCode(curpc) #post code to own account
					coderesponse = json.loads(response)
					curtime = time.ctime()
					try:
						error = coderesponse['error'] #if any error 
						print (curtime + ' - ' + curpc + ' - ' + coderesponse['error'])
						print (curtime + ' - ' + curpc + ' - ' + coderesponse['error'], file=f)
					except KeyError:
						print ('SUCESS' + curtime + ' - ' + curpc + ' - ' + str(coderesponse['result']))# if no error, log in console and post to twitter
						print ('SUCESS' + curtime + ' - ' + curpc + ' - ' + str(coderesponse['result']), file=f) #post response to logfile
						status = api.PostUpdate(curpc) # post to twitter
					pclist.append(curpc) # add to list of current passcodes to prevent duplication
					
    finally:
        f.close()
        
    