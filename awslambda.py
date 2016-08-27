import boto3
import logging
import json
import gzip
import re
from StringIO import StringIO

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# dictionary for loggroup name to sns topics, one for email antoher one for sms
lg2sns = {u'/app1/awscloudwatch/log/loggroups_name':
              {u'email': u'arn:aws:sns:us-east-1:xxxxxxxxx:ops-alarm-app1-email',
               u'sms': u'arn:aws:sns:us-east-1:xxxxxxxxx:ops-alarm-app1-sms'},
          u'/app2/awscloudwatch/log/loggroups_name':
              {u'email': u'arn:aws:sns:us-east-1:xxxxxxxxx:ops-alarm-app2-email',
               u'sms': u'arn:aws:sns:us-east-1:xxxxxxxxx:ops-alarm-app2-sms'},
          u'/app3/awscloudwatch/log/loggroups_name':
              {u'email': u'arn:aws:sns:us-east-1:xxxxxxxxx:ops-alarm-app3-email',
               u'sms': u'arn:aws:sns:us-east-1:xxxxxxxxx:ops-alarm-app3-sms'},
          u'/app4/awscloudwatch/log/loggroups_name':
              {u'email': u'arn:aws:sns:us-east-1:xxxxxxxxx:ops-alarm-app4-email',
               u'sms': u'arn:aws:sns:us-east-1:xxxxxxxxx:ops-alarm-app4-sms'}
          }

# dictionary for loggroup name to a list of triggering regex
lg2rules = {u'/app1/awscloudwatch/log/loggroups_name': ['.*[E|e]rror.*','.*ERROR.*','.*[F|f]ailed','.*OutOfMemory.*','.*SEVERE.*'],
            u'/app2/awscloudwatch/log/loggroups_name': ['.*[E|e]rror.*','.*ERROR.*','.*[F|f]ailed','.*OutOfMemory.*'],
            u'/app3/awscloudwatch/log/loggroups_name': ['.*[E|e]rror.*','.*ERROR.*','.*[F|f]ailed','.*OutOfMemory.*'],
            u'/app4/awscloudwatch/log/loggroups_name': ['.*[E|e]rror.*','.*ERROR.*','.*[F|f]ailed','.*OutOfMemory.*']
            }

log_sec_before_trigger = 60
log_sec_after_trigger = 10
logs_in_email = 100
chars_in_email = 500000
chars_in_sms = 300

def lambda_handler(event, context):

    #capture the CloudWatch log data
    outEvent = str(event['awslogs']['data'])

    #decode and unzip the log data
    outEvent = gzip.GzipFile(fileobj=StringIO(outEvent.decode('base64','strict'))).read()

    #convert the log data from JSON into a dictionary
    cleanEvent = json.loads(outEvent)
    #print cleanEvent

    logGroup = cleanEvent['logGroup']
    #print logGroup

    snsarnemail = ''
    try:
        snsarnemail = lg2sns[logGroup]['email']
    except:
        pass

    snsarnsms = ''
    try:
        snsarnsms = lg2sns[logGroup]['sms']
    except:
        pass

    filters = lg2rules[logGroup]

    triggered = False
    #loop through the events line by line
    for t in cleanEvent['logEvents']:
        print t['message']
        if testlog(t['message'],filters):
            triggered = True
            timestamp = t['timestamp']

    if triggered :
        print cleanEvent
        instanceinfo = getEC2info(cleanEvent['logStream'])
        relatedlog = getRelatedLogs(cleanEvent['logGroup'], cleanEvent['logStream'],timestamp-(log_sec_before_trigger * 1000),timestamp+( log_sec_after_trigger * 1000), logs_in_email)
        emaillog = relatedlog[(len(relatedlog)-chars_in_email if len(relatedlog)>chars_in_email else 0) : ]
        striptimestamplog = re.sub(r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.*\d{4}\]: ', '', relatedlog)
        shortrelatedlog = striptimestamplog[(len(striptimestamplog)-chars_in_sms if len(striptimestamplog)>chars_in_sms else 0) : ]

        print '------ logs in email --------'
        emailtext = instanceinfo + "\n" + emaillog
        print emailtext

        print '------ logs in sms --------'
        smstext = instanceinfo + "\n" + shortrelatedlog
        print smstext

        subject = 'Alert! error log found on: ' + instanceinfo
        if len(snsarnsms) > 5:
            SendToSNS(snsarnsms, smstext, subject)

        if len(snsarnemail) > 5:
            SendToSNS(snsarnemail, emailtext, subject)


def getEC2info(instanceid):
    client = boto3.client('ec2')
    priip = ''
    name = ''

    try:
        instances = client.describe_instances(
            InstanceIds=[
                instanceid
            ]
        )
        priip = instances['Reservations'][0]['Instances'][0]['PrivateIpAddress']
    except:
        pass

    try:
        tags = client.describe_tags(
            Filters=[
                {
                    'Name': 'resource-id',
                    'Values': [
                        instanceid
                    ]
                },{
                    'Name': 'key',
                    'Values': [
                        'Name'
                    ]
                }
            ],
            MaxResults=10
        )
        name = tags['Tags'][0]['Value']
    except:
        pass

    return name + '-' + priip



def getRelatedLogs(logGroupName, logStreamName,startTime,endTime,limit):
    logtest = ''
    client = boto3.client('logs')
    response = client.get_log_events(
        logGroupName=logGroupName,
        logStreamName=logStreamName,
        startTime=startTime,
        endTime=endTime,
        limit=limit,
        startFromHead=False
    )
    # print response

    if response['events'] :
        for t in response['events']:
            logtest = logtest + "\n" + t['message']
    return logtest


def testlog(logtext, filters):
    #print logtext, filters
    # Make a regex that matches if any of our regexes match.
    combined = "(" + ")|(".join(filters) + ")"
    return re.match(combined, logtext)



#function to send record to Kinesis Firehose
def SendToSNS(snsarn, message,subject):
    snsc = boto3.client('sns')

    response = snsc.publish(
        TopicArn=snsarn,
        Message=message,
        Subject=subject,
    )

    print response


# please update to your testdata
#testdata = {u'awslogs': {u'data': u'H4sIAAAAAAAAAK1UW0/bMBT+K16e2/juOJH2UG0FMcE2qX1DCJnUBE9JnNkprEL89x03sBtDPBRZceJzfPkux7nPOhujaex6N9isyj4u1ovLs+VqtTheZrPM3/U2QJhKqgslCi61gHDrm+PgtwNksB9G7PrRhnjjB2yjDbc2UNz62rTQN9gMwxQkOQyn1asxWNPBcjenJbsWWheQiNurWAc3jM73R65Ne2bVeXZququNmZZcnvq7o2C/b21f70598zX4Ggj4kF3sN17e2n5Mq+4zt4H9OSsANKGECQkvXUKTECm41oSoEohJrUrOaSEgRyQhtNSCAJrRgTSj6YAlFapU0FFOCJk9SQbbnzNC1ZwUc1YgoiqqKslzrQWaE0HIRYU+bVvEihlK89DjBLQ4Qz40uRlMfWPz2oymdb3Jax9svhpNvzFhswLJXG0RIAjjSdK3N232MDuMFz2Ml/zF6+Tz0ZcKrRI41zcoPqL98MjlYKDsMKDqcAOWfeP6t9afvxWtf/RP1dLaEU2gK7TYM0Nr3wE5XOQkB0Wfg9/jVJqwUioudDqUU0Gk1pQzxhIpwA1Nw/0X4gXw8nXwMuf896WoKtR6s5kKZ0wEYoptQ4veo28mVNeutdVLf5Z4Y4LFcRdH2+EaBAhu09iIW3cVcbCtNdGmAf7DYne7S8+c5QK0gCPepSyeshgyOHmPn9CkyNN3/qN77jtnZcmYYqCOAJsLygWnqqBMUMnLgihFhJYl+A71AdLJ/0pXvCqdrjhIp/lfviM03xtuw1Sd2wG5HlGwk0nUxezh4uEnxxPYvdcFAAA='}}
#lambda_handler(testdata, 2)