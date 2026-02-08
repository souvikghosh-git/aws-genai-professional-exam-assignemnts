import json
import boto3
from botocore.exceptions import ClientError

bedrock = boto3.client('bedrock-runtime')
FALLBACK_MODEL = "amazon.titan-text-express-v1"

def lambda_handler(event, context):
    print("Fallback Invoked with event:", json.dumps(event))
    
    # Step Functions passes input as-is or inside a Payload wrapper depending on previous state
    # We expect 'prompt' in the event
    prompt = event.get('question') or event.get('prompt')
    if not prompt and 'Payload' in event:
        # Handle case where input might be wrapped
        prompt = event['Payload'].get('question') or event['Payload'].get('prompt')

    if not prompt:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "No prompt provided for fallback"})
        }

    try:
        # Simple Titan invocation
        body = json.dumps({
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 512,
                "temperature": 0.5,
                "topP": 0.9
            }
        })
        
        response = bedrock.invoke_model(
            body=body,
            modelId=FALLBACK_MODEL,
            accept='application/json',
            contentType='application/json'
        )
        
        response_body = json.loads(response.get('body').read())
        output_text = response_body['results'][0]['outputText']
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "answer": output_text,
                "model_used": f"FALLBACK:{FALLBACK_MODEL}"
            })
        }
    except Exception as e:
        print(f"Fallback Failed: {e}")
        # Re-raise to trigger next Step Function catch
        raise e
