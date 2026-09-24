import yaml

# Add constructors for CloudFormation intrinsic functions
cfn_tags = ['!Ref', '!Sub', '!GetAtt', '!Join', '!Select', '!Split', '!If', '!Equals', '!Not', '!And', '!Or', '!Condition', '!FindInMap', '!Base64', '!Cidr', '!GetAZs', '!ImportValue', '!Transform']

for tag in cfn_tags:
    yaml.SafeLoader.add_constructor(tag, lambda loader, node: None)
    yaml.SafeLoader.add_multi_constructor(tag, lambda loader, suffix, node: None)

with open('cloudformation/A360-Analytics.yaml') as f:
    data = yaml.safe_load(f)

resources = data.get('Resources', {})
if 'MetricCollectorFunction' in resources:
    print('MetricCollectorFunction found in Resources')
    props = resources['MetricCollectorFunction'].get('Properties', {})
    print(f"  Runtime: {props.get('Runtime')}")
    print(f"  MemorySize: {props.get('MemorySize')}")
    print(f"  Timeout: {props.get('Timeout')}")
    print(f"  ReservedConcurrentExecutions: {props.get('ReservedConcurrentExecutions')}")
    env_vars = props.get('Environment', {}).get('Variables', {})
    print(f"  Environment variables: {list(env_vars.keys())}")
    print(f"  Handler: {props.get('Handler')}")
else:
    print('MetricCollectorFunction NOT found')

if 'Outputs' in data:
    print('Outputs section present')
else:
    print('WARNING: Outputs section missing')
