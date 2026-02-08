#!/usr/bin/env python3
import os
import aws_cdk as cdk
from infrastructure.service_stack import ServiceStack
from infrastructure.ml_ops_stack import MLOpsStack

app = cdk.App()

# Part 4: ML Ops & Lifecycle (Optional - Uncomment to deploy)
# MLOpsStack(app, "MLOpsStack",
#     env=cdk.Environment(account="570484142060", region="us-east-1"),
# )

# Part 2 & 3: Service Architecture
# Deployed to Primary Region (US East 1)
ServiceStack(app, "ServiceStack-Primary",
    env=cdk.Environment(account="570484142060", region="us-east-1"),
)

# Part 3: Cross-Region Failover (Secondary Region)
# Deployed to Secondary Region (US West 2)
ServiceStack(app, "ServiceStack-Secondary",
    env=cdk.Environment(account="570484142060", region="us-west-2"),
)

app.synth()
