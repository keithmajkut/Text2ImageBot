import json
import boto3
import hmac
import hashlib
import os
import base64
import urllib3

lambda_fn = boto3.client('lambda')
#------------------------------------------------------------------------------    
def invokeSlackHandler(event, message):
    """
    Asynchronously invokes the core SlackBot handler that will do all the work. This
        lambda needs to return without a few hundred ms due to slack requirements.

    :param event: the event from the lambda invocation. 
    :param message: the text that the user entered into slack
    """    
    channel_id = event["event"]["channel"]
    user_id = event["event"]["user"]
    #message = event["event"]["text"]
    
    print(f"SH0:channel_id: {channel_id}, user_id: {user_id}, message: {message}")
    
    payload = { 
        "channel_id": channel_id, 
        "user_id": user_id, 
        "message": message}
        
    lambda_fn.invoke(FunctionName='slackHandler',
                     InvocationType='Event',
                     Payload=json.dumps(payload))
#------------------------------------------------------------------------------    
def isCommand(text):
    #-- after removing the !, need to make sure there is some text left 
    if text.startswith("!"):
        return text.replace(text[0], "")
    return None
#------------------------------------------------------------------------------    
def isBot(event):
    return "bot_profile" in event["event"]
#------------------------------------------------------------------------------    
def isValidSignature(event):
    """
    Checks to see if the signature coming from the slack event is valid
        per https//: [NEED TO FIND THE URL]
        lambda needs to return without a few hundred ms due to slack requirements.

    :param event: the event from the lambda invocation
    """    

    signing_secret = os.environ["SIGNING_SECRET"]
    slack_signature = event["headers"]["X-Slack-Signature"]
    request_timestamp = event["headers"]["X-Slack-Request-Timestamp"]
    request_body = event["body"]
    sig_basestring = 'v0:' + request_timestamp + ':' + request_body
    hmac_object = hmac.new(signing_secret.encode(), sig_basestring.encode(), hashlib.sha256).hexdigest()
    my_signature = 'v0=' +   hmac_object

    if (slack_signature == my_signature):
        return True
    else: 
        return False

#------------------------------------------------------------------------------    
def lambda_handler(event, context):
    #--
    try:
        if isValidSignature(event):
            event = json.loads(event["body"])
            print(f"SH0 event --> {event}")
            print(f"SH0 context --> {context}")
            if not isBot(event):
                message = isCommand(event["event"]["text"])
                if message:
                    #-- all check good, invoke action lambda
                    invokeSlackHandler(event, message)
            print("SH0: isValidSignature Passed")       
            return {
                "statusCode": 200,
                "body": "OK"
            }
        else:
            print(f"SH0: isValidSignature Failed")       
            return {
                "x-slack-no-retry": 1,
                "statusCode": 401,
                "body": 'FAILED'
            }

        print('SH0: final good reply')       
        return {
            "statusCode": 200,
            "body": "OK"
        }
    except:
        print (f"SH0:Exception, probably cannot invoke SH1")
        return {
            "x-slack-no-retry": 1,
            "statusCode": 500,
            "body": "OK"
        }


#    slack_body = event.get("body")
#    slack_event = json.loads(slack_body)
#    challenge_answer = slack_event.get("challenge")
#    return {
#        "statusCode": 200,
#        "body":  challenge_answer
#    }


