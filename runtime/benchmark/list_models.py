import boto3
import json

bedrock = boto3.client(service_name='bedrock', region_name='us-east-1')

response = bedrock.list_foundation_models()

for model in response['modelSummaries']:
    if "TEXT" in model['outputModalities'] and "ON_DEMAND" in model['inferenceTypesSupported']:
        print(f"{model['modelId']} | {model['modelName']}")
