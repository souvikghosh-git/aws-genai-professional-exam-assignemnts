import json
import boto3
import os
import time
from botocore.exceptions import ClientError

appconfig = boto3.client('appconfigdata')
bedrock = boto3.client('bedrock-runtime')

# Cache configuration
CONFIG_CACHE = {
    "data": None,
    "token": None,
    "last_updated": 0
}
CACHE_TTL = 60 # seconds

def get_config():
    global CONFIG_CACHE
    now = time.time()
    
    app_id = os.environ.get('APPCONFIG_APP_ID')
    env_id = os.environ.get('APPCONFIG_ENV_ID')
    profile_id = os.environ.get('APPCONFIG_PROFILE_ID')
    
    if not (app_id and env_id and profile_id):
        # Fallback if env vars missing
        return {"default_model": "anthropic.claude-3-sonnet-20240229-v1:0"}

    if CONFIG_CACHE['data'] and (now - CONFIG_CACHE['last_updated'] < CACHE_TTL):
        return CONFIG_CACHE['data']
        
    try:
        if not CONFIG_CACHE['token']:
            # Initial session
            response = appconfig.start_configuration_session(
                ApplicationIdentifier=app_id,
                EnvironmentIdentifier=env_id,
                ConfigurationProfileIdentifier=profile_id,
                RequiredMinimumPollIntervalInSeconds=60
            )
            CONFIG_CACHE['token'] = response['InitialConfigurationToken']
            
        # Get latest config
        response = appconfig.get_latest_configuration_profile(
            ConfigurationToken=CONFIG_CACHE['token']
        )
        
        CONFIG_CACHE['token'] = response['NextPollConfigurationToken']
        
        if 'Configuration' in response:
            content = response['Configuration'].read().decode('utf-8')
            if content:
                CONFIG_CACHE['data'] = json.loads(content)
                CONFIG_CACHE['last_updated'] = now
                
        return CONFIG_CACHE['data'] or {}
        
    except Exception as e:
        print(f"Error fetching config: {e}")
        return {"default_model": "anthropic.claude-3-sonnet-20240229-v1:0"}

def invoke_bedrock(model_id, prompt):
    print(f"Invoking {model_id}")
    
    # Simple adapter logic for different models
    body = ""
    if "claude" in model_id:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}]
        })
    elif "llama3" in model_id:
        body = json.dumps({
            "prompt": prompt,
            "max_gen_len": 512,
            "temperature": 0.5,
            "top_p": 0.9
        })
    elif "mistral" in model_id:
        body = json.dumps({
            "prompt": f"<s>[INST] {prompt} [/INST]",
            "max_tokens": 512,
            "temperature": 0.5
        })
    else:
        # Default fallback (Titan or generic)
        body = json.dumps({
            "inputText": prompt
        })

    response = bedrock.invoke_model(
        body=body,
        modelId=model_id,
        accept='application/json',
        contentType='application/json'
    )
    
    response_body = json.loads(response.get('body').read())
    
    # Extract text
    if "claude" in model_id:
        return response_body['content'][0]['text']
    elif "llama3" in model_id:
        return response_body['generation']
    elif "mistral" in model_id:
        return response_body['outputs'][0]['text']
    else:
        return str(response_body)

def lambda_handler(event, context):
    print("Event:", json.dumps(event))
    
    try:
        # Parse input
        body = event
        if 'body' in event:
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            elif isinstance(event['body'], dict):
                body = event['body']
        
        question = body.get('question')
        req_type = body.get('type', 'general')
        
        if not question:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing question', 'received': event})
            }

        # Get Config
        config = get_config()
        
        # Determine Model
        overrides = config.get('overrides', {})
        model_id = overrides.get(req_type, config.get('default_model', 'anthropic.claude-3-sonnet-20240229-v1:0'))
        
        # Invoke
        answer = invoke_bedrock(model_id, question)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'answer': answer,
                'model_used': model_id
            })
        }
        
    except Exception as e:
        print(f"Error: {e}")
        raise e

