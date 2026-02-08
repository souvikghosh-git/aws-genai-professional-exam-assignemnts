import boto3
import json
import time
import datetime
from botocore.exceptions import ClientError

# Configuration
MODELS = [
    "anthropic.claude-3-sonnet-20240229-v1:0",
    "meta.llama3-8b-instruct-v1:0",
    "mistral.mistral-7b-instruct-v0:2"
]

QUESTIONS = [
    "What are the key features of your high-yield savings account?",
    "Explain the difference between a Roth IRA and a Traditional IRA.",
    "How can I dispute a transaction on my credit card?",
    "What should I do if I suspect fraudulent activity on my account?"
]

# Pricing (Approximate per 1M tokens for estimation)
PRICING = {
    "anthropic.claude-3-sonnet-20240229-v1:0": {"input": 3.00, "output": 15.00},
    "meta.llama3-8b-instruct-v1:0": {"input": 0.40, "output": 0.60},
    "mistral.mistral-7b-instruct-v0:2": {"input": 0.15, "output": 0.20}
}

bedrock = boto3.client(service_name='bedrock-runtime', region_name='us-east-1')

def invoke_model(model_id, prompt):
    print(f"Invoking {model_id}...")
    
    body = ""
    if "claude" in model_id:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}]
        })
    elif "llama3" in model_id:
        formatted_prompt = f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        body = json.dumps({
            "prompt": formatted_prompt,
            "max_gen_len": 512,
            "temperature": 0.5,
            "top_p": 0.9
        })
    elif "mistral" in model_id:
        formatted_prompt = f"<s>[INST] {prompt} [/INST]"
        body = json.dumps({
            "prompt": formatted_prompt,
            "max_tokens": 512,
            "temperature": 0.5,
            "top_p": 0.9,
            "top_k": 50
        })

    start_time = time.time()
    try:
        response = bedrock.invoke_model(
            body=body,
            modelId=model_id,
            accept='application/json',
            contentType='application/json'
        )
        end_time = time.time()
        latency = end_time - start_time
        
        response_body = json.loads(response.get('body').read())
        output_text = ""
        input_tokens = 0
        output_tokens = 0
        
        # Parse response based on model
        if "claude" in model_id:
            output_text = response_body['content'][0]['text']
            input_tokens = response_body['usage']['input_tokens']
            output_tokens = response_body['usage']['output_tokens']
        elif "llama3" in model_id:
            output_text = response_body['generation']
            input_tokens = response_body['prompt_token_count']
            output_tokens = response_body['generation_token_count']
        elif "mistral" in model_id:
            output_text = response_body['outputs'][0]['text']
            # Mistral might not return token counts in headers, estimating if missing
            # Checking headers if available usually `x-amzn-bedrock-input-token-count`
            headers = response.get('ResponseMetadata', {}).get('HTTPHeaders', {})
            input_tokens = int(headers.get('x-amzn-bedrock-input-token-count', len(prompt.split()) * 1.3))
            output_tokens = int(headers.get('x-amzn-bedrock-output-token-count', len(output_text.split()) * 1.3))

        # Cost Calculation
        price_cfg = PRICING.get(model_id, {"input": 0, "output": 0})
        cost = (input_tokens / 1_000_000 * price_cfg['input']) + (output_tokens / 1_000_000 * price_cfg['output'])

        # Guardrail Check (Simple keyword check simulation)
        compliance_check = "PASS"
        if "error" in output_text.lower() or "sorry" in output_text.lower():
            compliance_check = "FLAGGED"

        return {
            "model": model_id,
            "latency": round(latency, 4),
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "cost": round(cost, 6),
            "compliance": compliance_check,
            "response_preview": output_text[:50].replace("\n", " ") + "..."
        }

    except ClientError as e:
        print(f"Error invoking {model_id}: {e}")
        return {
            "model": model_id,
            "error": str(e)
        }
    except Exception as e: # Catch fallback for parsing errors
        print(f"Error parsing {model_id}: {e}")
        return {
            "model": model_id,
            "error": str(e)
        }

def run_benchmark():
    results = []
    print("Starting Benchmark...")
    print("-" * 60)
    
    for model in MODELS:
        for question in QUESTIONS:
            result = invoke_model(model, question)
            result['question'] = question[:30] + "..."
            results.append(result)
            time.sleep(1) # Rate limit nice-ness
            
    # Generate Report
    print("-" * 60)
    print(f"{'Model':<40} | {'Latency':<8} | {'Cost':<8} | {'Compliance':<10}")
    print("-" * 60)
    for r in results:
        if 'error' in r:
            print(f"{r['model']:<40} | ERROR    | -        | -")
        else:
            print(f"{r['model']:<40} | {r['latency']:<8} | ${r['cost']:<8} | {r['compliance']:<10}")

    # Save to file
    with open('benchmark_report.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\nBenchmark complete. Report saved to benchmark_report.json")

if __name__ == "__main__":
    run_benchmark()
