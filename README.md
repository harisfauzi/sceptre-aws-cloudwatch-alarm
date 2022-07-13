# README

This repo allows you to quickly deploy CloudWatch alarms
for your selected EC2 instance using CloudFormation
and predefined metrics selection.

## TL;DR; Quickly Deploy CloudWatch Alarms

Follow these steps:

 1. Authenticate to your AWS account in your CLI
    (bash, PowerShell is not suported).

    - If you use IAM User API key, either save the API key in your your
      AWS credentials file, or export them as environment variables
      (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY).
      Use `--long-term-profile` for calling `deploy-cwalarm.sh` script
      below.
    - If you assume a role via SSO, either save the API key in your
      AWS credentials file, or export the as environment variables
      (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_SESSION_TOKEN).
      Use `--short-term-profile` for calling `deploy-cwalarm.sh` script
      below.

 2. Get the `tag:Name` for your EC2 instance. This needs to be a unique
    in the AWS Account/Region combination, as of not part of
    AutoScalingGroup.

 3. Get the SNS Topic ARN for the CloudWatch alarm, to notify you
    when the state is In Alarm or OK.

 4. If you save your AWS credentials to the ~/.aws/credentials file,
    run:

    ```bash
    AWS_PROFILE=<your profile>;export AWS_PROFILE
    ```

 5. Run:

    ```bash
    # Set AWS default region environment variable,
    # e.g. ap-southeast-2 (Sydney)
    AWS_DEFAULT_REGION=ap-southeast-2;export AWS_DEFAULT_REGION
    # Set instance name, e.g. MyInstance
    INSTANCE_NAME=MyInstance
    # Set SNS Topic ARN, e.g.
    #   arn:aws:sns:ap-southeast-2:123456789012:notify-me
    SNS_TOPIC_ARN=arn:aws:sns:ap-southeast-2:123456789012:notify-me
    # Deploy the CloudWatch alarm
    ./deploy-cwalarm.sh -s "${AWS_PROFILE}" \
      --short-term-profile "${AWS_PROFILE}" \
      --action deploy \
      --instance-name "${INSTANCE_NAME}" \
      --sns-topic-arn "${SNS_TOPIC_ARN}"
    ```

## Requirements

- Python3
- Python virtualenv
- Pip
- Bash
- AWS account with proper privilege to deploy CloudWatch Alarm
  via CloudFormation

## More Options

### To Delete the CloudWatch Alarm

Similar with deploying the CloudWatch Alarm but change the action to `destroy`:

```bash
# Set AWS default region environment variable,
# e.g. ap-southeast-2 (Sydney)
AWS_DEFAULT_REGION=ap-southeast-2;export AWS_DEFAULT_REGION
# Set instance name, e.g. MyInstance
INSTANCE_NAME=MyInstance
# Set SNS Topic ARN, e.g.
#   arn:aws:sns:ap-southeast-2:123456789012:notify-me
SNS_TOPIC_ARN=arn:aws:sns:ap-southeast-2:123456789012:notify-me
# Deploy the CloudWatch alarm
./deploy-cwalarm.sh -s "${AWS_PROFILE}" \
  --short-term-profile "${AWS_PROFILE}" \
  --action destroy \
  --instance-name "${INSTANCE_NAME}" \
  --sns-topic-arn "${SNS_TOPIC_ARN}"
```

### Replace UNKNOWN_AWS_ACCOUNT

To replace the string `UNKNOWN_AWS_ACCOUNT` in the alarm name/description, do:

 1. Copy `accounts.json.example` to `accounts.json`.
 2. Put proper information about the AWS account Id and the name for the AWS account
    in the `accounts.json` file.
 3. Redeploy the CloudWatch alarms.

### Override Threshold ###

The default values for the threshold, or to include the alarm, is defined in
`sceptre/helper-scripts/configgenerator.py`. To override those values, e.g. 
to change the threshold for CPU credit warning and critical from the default
500 and 100 to 100 and 20, use the manifest file
`sceptre/cwalarm-manifest/small_cpu_credit.yaml` and pass it to
`deploy-cwalarm.sh` script using `--cwalarm-manifest` parameter.
The call to the script would be:

```bash
# Set AWS default region environment variable,
# e.g. ap-southeast-2 (Sydney)
AWS_DEFAULT_REGION=ap-southeast-2;export AWS_DEFAULT_REGION
# Set instance name, e.g. MyInstance
INSTANCE_NAME=MyInstance
# Set SNS Topic ARN, e.g.
#   arn:aws:sns:ap-southeast-2:123456789012:notify-me
SNS_TOPIC_ARN=arn:aws:sns:ap-southeast-2:123456789012:notify-me
# Deploy the CloudWatch alarm
./deploy-cwalarm.sh -s "${AWS_PROFILE}" \
  --short-term-profile "${AWS_PROFILE}" \
  --action destroy \
  --instance-name "${INSTANCE_NAME}" \
  --sns-topic-arn "${SNS_TOPIC_ARN}" \
  --cwalarm-manifest "sceptre/cwalarm-manifest/small_cpu_credit.yaml"
```

Only one manifest file can be passed to the script.
You can customise your manifest file and combine several metrics values in
a single manifest file.