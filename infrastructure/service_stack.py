from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_appconfig as appconfig,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    RemovalPolicy
)
from constructs import Construct
import json

class ServiceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Part 2: AppConfig ---
        app = appconfig.CfnApplication(self, "ModelSelectionApp",
            name="ModelSelectionApp"
        )

        env = appconfig.CfnEnvironment(self, "ModelSelectionEnv",
            application_id=app.ref,
            name="Production"
        )

        # Initial Config Content
        initial_config = {
            "default_model": "anthropic.claude-3-sonnet-20240229-v1:0",
            "overrides": {
                "finance_deep": "anthropic.claude-3-sonnet-20240229-v1:0",
                "general_chat": "meta.llama3-8b-instruct-v1:0"
            }
        }
        
        config_profile = appconfig.CfnConfigurationProfile(self, "ModelConfigProfile",
            application_id=app.ref,
            name="ModelConfig",
            location_uri="hosted",
            type="AWS.Freeform"
        )

        hosted_cfg = appconfig.CfnHostedConfigurationVersion(self, "InitialConfigVersion",
            application_id=app.ref,
            configuration_profile_id=config_profile.ref,
            content=json.dumps(initial_config),
            content_type="application/json"
        )

        deployment = appconfig.CfnDeployment(self, "InitialDeployment",
            application_id=app.ref,
            configuration_profile_id=config_profile.ref,
            configuration_version=hosted_cfg.ref,
            deployment_strategy_id="AppConfig.AllAtOnce",
            environment_id=env.ref
        )

        # --- Part 2: Lambda Model Router ---
        router_fn = lambda_.Function(self, "ModelRouterFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("runtime/model_router"),
            timeout=Duration.seconds(60),
            environment={
                "APPCONFIG_APP_ID": app.ref,
                "APPCONFIG_ENV_ID": env.ref,
                "APPCONFIG_PROFILE_ID": config_profile.ref
            }
        )

        # Permissions
        router_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=["*"] # Ideally scoped to specific models
        ))
        
        router_fn.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "appconfig:StartConfigurationSession",
                "appconfig:GetLatestConfiguration"
            ],
            resources=["*"] # Ideally scoped to the AppConfig resources
        ))


        # --- Part 3: Step Functions (Circuit Breaker Pattern) ---
        
        # 1. Primary Model (The Router)
        primary_task = tasks.LambdaInvoke(self, "TryPrimaryModel",
            lambda_function=router_fn,
            output_path="$.Payload"
        )

        # 2. Fallback Model
        fallback_fn = lambda_.Function(self, "FallbackFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="fallback_handler.lambda_handler",
            code=lambda_.Code.from_asset("runtime/workflow"),
            timeout=Duration.seconds(30),
            environment={}
        )
        fallback_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=["*"]
        ))
        
        fallback_task = tasks.LambdaInvoke(self, "TryFallbackModel",
            lambda_function=fallback_fn,
            output_path="$.Payload"
        )

        # 3. Graceful Degradation
        degradation_fn = lambda_.Function(self, "DegradationFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="degradation_handler.lambda_handler",
            code=lambda_.Code.from_asset("runtime/workflow"),
            timeout=Duration.seconds(5)
        )
        
        degradation_task = tasks.LambdaInvoke(self, "GracefulDegradation",
            lambda_function=degradation_fn,
            output_path="$.Payload"
        )

        # Wiring the Circuit Breaker
        # Primary -> (Catch) -> Fallback -> (Catch) -> Degradation
        
        fallback_task.add_catch(degradation_task, errors=["States.ALL"], result_path="$.error")
        primary_task.add_catch(fallback_task, errors=["States.ALL"], result_path="$.error")

        chain = primary_task

        state_machine = sfn.StateMachine(self, "ModelServiceStateMachine",
            definition=chain,
            timeout=Duration.minutes(2),
            state_machine_type=sfn.StateMachineType.EXPRESS
        )

        # --- API Gateway ---
        # REST API backing the Step Function
        api = apigw.StepFunctionsRestApi(self, "AssistantApi",
            state_machine=state_machine,
            deploy=True
        )

