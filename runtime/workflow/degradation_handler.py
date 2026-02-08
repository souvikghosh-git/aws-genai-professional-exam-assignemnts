import json

def lambda_handler(event, context):
    print("Degradation Invoked")
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "answer": "I'm sorry, system is currently under high load. Please try again later.",
            "model_used": "DEGRADED_SERVICE"
        })
    }
