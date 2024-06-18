import json
import boto3
import urllib3
import os
from botocore.response import StreamingBody
from botocore.client import Config
from botocore.exceptions import ClientError
import argparse
import shlex
import base64
import time    


#- bedrock setup
session = boto3.session.Session()
region = session.region_name
bedrock = boto3.client(service_name="bedrock-runtime")
bedrock_config = Config(connect_timeout=120, read_timeout=120, retries={"max_attempts": 0})
bedrock_client = boto3.client('bedrock-runtime', region_name = region)
#-

#- could get this from secrets manager
slackToken=os.environ.get('token')

http = urllib3.PoolManager()

#------------------------------------------------------------------------------        
def getUniqueFileName(suffix):
    """
    Helper function to create a unique filename from (seconds since)epoch + suffix
    
    :param suffix: suffix to add to the filename
    :returns: unique filename
    """
    epoch_time = int(time.time())
    fileName=str(epoch_time)+'.'+suffix
    
    return fileName
#------------------------------------------------------------------------------
def postMessageToSlack(channel_id, data):
    """
    post a message to Slack

    :param channel_id: Slack channel id
    :param msg: message
    """
    try:
        slackUrl = 'https://slack.com/api/chat.postMessage'
        headers = {
            "Authorization": f"Bearer {slackToken}",
            "Content-Type": "application/json"
        }
        response = http.request('POST', slackUrl, headers=headers, body=json.dumps(data))
    except:
        print ('postMessageToSlack:Exception from SLACK')
    
#------------------------------------------------------------------------------        
def sendCodeBlockToSlack(channel_id, msg):
    """
    send text formatted as a code block to Slack

    :param channel_id: Slack channel id
    :param msg: message
    """
    data = {
        "channel" : channel_id, 
        "blocks": [ 
            {
            "type": "section",
            "text": {
    			"type": "mrkdwn",
    			"text": f"`{msg}`"
    			}
    		}
        ]
    }
    postMessageToSlack(channel_id, data)

 #------------------------------------------------------------------------------        
def sendTextToSlack(channel_id, msg):
    """
    send text to Slack

    :param channel_id: Slack channel id
    :param msg: message
    """
    data = {
        "channel": channel_id, 
        "text": msg
    }
    postMessageToSlack(channel_id, data)

#------------------------------------------------------------------------------
def sendImageToSlack(channel_id, filename, img, elapsed_time):
    """
    send image to Slack. 3 step process used to upload_imagesv2 (which doesn't seem to work)

    :param channel_id: Slack channel id
    :param filename: filename
    :param img: img
    """
    try:
        headers = {
            "Authorization": f"Bearer {slackToken}",
            "Content-Type": "application/json"
        }
    
        #------------------------------------------------------------------------------
        #-- Step1, get the URL to upload
        img_len=len(img)
        slackUrl = f"https://slack.com/api/files.getUploadURLExternal?filename={filename}&length={img_len}"
        data = {}

        res = http.request('GET', slackUrl, headers=headers, body=json.dumps(data))
        #print(res)
        #print('-->', res.status, res.reason, res.data)
        resdata=json.loads(res.data.decode())

        #------------------------------------------------------------------------------
        #-- Step2 upload the image
        if resdata['ok']: 
            upload_url=resdata["upload_url"]
            file_id=resdata["file_id"]
            #print('1-->', resdata)
            #print('1-->', upload_url, '\n')
            #print('1-->', file_id, '\n')
        
            res = http.request("POST", upload_url, headers=headers, body=img)
            #resdata=res.data.decode()
            #resdata=json.loads(res.data.decode())
            #print('2-->',res.status, res.data)
            #if resdata['ok']: 
            #    print('-->', resdata)
        
        #------------------------------------------------------------------------------
            #-- Step3 complete the upload
            data = { 
                "channel_id" : channel_id, 
#               "initial_comment": "Created using Amazon Bedrock",
                "files": [
                    { 
                        "id": file_id, 
                        "title": f"{filename} [generated in {elapsed_time} seconds]"
                    } 
                ]
            } 

            slackUrl = "https://slack.com/api/files.completeUploadExternal"
            res = http.request("POST", slackUrl, headers=headers,  body=json.dumps(data).encode("utf-8"))
            #print('3-->',res.status, res.data)

            resdata=json.loads(res.data.decode())
            
#            permalink = resdata['files'][0]['permalink']
#           sendTextToSlack(channel_id, permalink)
    except:
        print ("sendImageToSlack:Exception from SLACK")

#------------------------------------------------------------------------------    
def parseSlackMessage(channel_id, message0):
    """
    Helper function to break down the message as if it were a command line, basic value checks and defaults
    :param channel_id:  
    :param message:  
    :returns 
    """
    try:
        #- in case the user does -p = text.
        # i could also split on -, then skip the keywords, then double quote any strings.
        message = message0.replace("=", " ")

        data = {}

        parser = argparse.ArgumentParser(prog="prog", description='Text2Image Slackbot suing Amazon Titan Image Generator G1')
        parser.add_argument ('-prompt', type=str, default='smiley face', help='text prompt to generate the image')
        parser.add_argument ('-negative', type=str, default='', help=' text prompt to define what not to include in the image')
        parser.add_argument ('-seed', type=str, default='0', help='seed (0 - 2,147,483,646')
        parser.add_argument ('-cfgscale', type=str, default='8', help=' Specifies how strongly the generated image should adhere to the prompt. Use a lower value to introduce more randomness in the generation. (1.1-10)')
#        parser.add_argument ('-num', type=int, default=1, choices=range(1, 5), help='numberOfImages')
#        parser.add_argument ('-height', type=int, default=512, help='height')
#        parser.add_argument ('-width', type=int, default=512, help='width')
 
#        args=parser.parse_args(args_list)
        args_list=shlex.split(message)
        args, unknown_args=parser.parse_known_args(args_list)

        if unknown_args:
	         sendCodeBlockToSlack(channel_id, f'Unknown arguments in message')

        data["prompt"] = None
        if (args.prompt):
            prompt=args.prompt
            if (len(prompt) > 2):
                data["prompt"] = prompt[0:512]

        data["negativePrompt"] = None
        if (args.negative):
            negativePrompt=args.negative
            if (len(negativePrompt) > 2):
                data["negativePrompt"] = negativePrompt[0:512]

        if (args.seed):
            data["seed"] = args.seed
        else: 
            data["seed"] = 0

        if (args.cfgscale):
            data["cfgscale"] = args.cfgscale
        else:
            data["cfgscale"] = 8

#        if (args.num):
#            data["num"] = args.num
#        if (args.height):
#            data["height"] = args.height
#        if (args.width):
#            data["width"] = args.width

        return data
        
    except ClientError as err:
        print(f"parseSlackMessage:parse_args failed, {err.response["Error"]["Code"]}:{err.response["Error"]["Message"]}")
        return {}    

#------------------------------------------------------------------------------
def promptImageBedrockTitan(modelId, prompt, negativePrompt, seed, numberOfImages, cfgScale, height, width):
    """
    Invokes the Titan Image model to create an image using the input provided in the request body.

    :param prompt: The prompt that you want Amazon Titan to use for image generation.
    :param negativePrompt: 
    :param seed: Random noise seed (range: 0 to 2147483647)
    :numberOfImages: 
    :cfgscale:
    :height:
    :width:
    :return: Base64-decoded inference response from the model.
    """
    try:
        # The different model providers have individual request and response formats.
        # For the format, ranges, and default values for Titan Image models refer to:
        # https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-titan-image.html

#        modelId = "amazon.titan-image-generator-v1" 
        #- prompt cannot be > 512
        
        data = {
            "taskType": "TEXT_IMAGE",
            "textToImageParams": { 
                "text": prompt
#                "negativeText" : negativePrompt
            },
            "imageGenerationConfig": {
                "numberOfImages": numberOfImages,
#                "quality": quality,
                "cfgScale": cfgScale,
                "height": height,
                "width": width,
                "seed": seed
            },
        }

        #- negative prompt cannot be greater than 512
        if (negativePrompt):
                data["textToImageParams"]["negativeText"] = negativePrompt 

        #response = self.bedrock_runtime_client.invoke_model(modelId=modelId, body=data)
        response = bedrock_client.invoke_model(modelId=modelId, body=json.dumps(data))
        
        response_body = json.loads(response["body"].read())
        imageBase64 = response_body["images"][0]
        #- from 0..4 I can grab the images and put them in a structure
        imageBytes=base64.b64decode(imageBase64)

        return imageBytes
            
    except ClientError as err:
        print(f"promptImageBedrockTitan:Couldn't invoke {modelId}, {err.response["Error"]["Code"]}:{err.response["Error"]["Message"]}")
        return None
#------------------------------------------------------------------------------        
def invokeImageBedrockTitan(channel_id, data):
#-- call TITAN

    #- if there is a prompt, continue
    if (data["prompt"]):
        prompt=data["prompt"]
        negativePrompt=data["negativePrompt"]
        cfgscale=data["cfgscale"]
        seed=data["seed"]
#       quality=data["quality"]
#       height=data["height"]
#       width=data["width"]
    
        modelId = "amazon.titan-image-generator-v1"
        numberOfImages=1
        height=512
        width=512

        sendCodeBlockToSlack(channel_id, f"modelId:{modelId}, prompt:{prompt}, negativePrompt:{negativePrompt}, seed:{seed}, numberOfImages:{numberOfImages}, cfgscale:{cfgscale}, height:{height}, width:{width}")    

        epoch_time_start = int(time.time())
        imageBytes=promptImageBedrockTitan(modelId, prompt, negativePrompt, int(seed), numberOfImages, float(cfgscale), height, width)
        epoch_time_end = int(time.time())
        if imageBytes is not None:
            imageFileName=getUniqueFileName("png")
            sendImageToSlack(channel_id, imageFileName, imageBytes, (epoch_time_end-epoch_time_start))

#------------------------------------------------------------------------------        
def lambda_handler(event, context):
    #--
    #-- Here is where the body of work should be done. check for signature and !is_bot already done
    #--
    #-- need a try block
    
    print (f"S1:event---> {event}")    
    print (f"S1:context---> {context}")    
    # event payload = { "channel_id": C06R6PYR62X, "user_id": U06RVLX3D24, "message": '-prompt "what is a mobile phone"'}

    #- text2text prompt from slack to AI21
    slackChannelID = event["channel_id"]
    slackUserID = event["user_id"]
    slackMessage = event["message"]
    
    data = parseSlackMessage(slackChannelID, slackMessage)
    invokeImageBedrockTitan(slackChannelID, data)




