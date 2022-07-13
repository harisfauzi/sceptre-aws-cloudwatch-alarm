#!/bin/bash

set -eEu -o pipefail +x

CWALARM_MANIFEST=""
SNS_TOPIC_ARN=""
SNS_TOPIC_CFN_NAME=""
SNS_TOPIC_OUTPUT_NAME=""
AWS_ACCOUNT=""
SHORT_AWS_PROFILE=""
LONG_AWS_PROFILE=""
AWS_ROLE_TO_ASSUME=FAODeployerRole
PARAMS=""
SCRIPT_ACTION=""
CFN_CONFIG=""

get_short_term_credentials() {
    AWS_ACCESS_KEY=$(grep -A6 "\[${SHORT_AWS_PROFILE}\]" ~/.aws/credentials | grep aws_access_key_id | awk '{print $NF}')
    AWS_SECRET_KEY=$(grep -A6 "\[${SHORT_AWS_PROFILE}\]" ~/.aws/credentials | grep aws_secret_access_key | awk '{print $NF}')
    AWS_SECURITY_TOKEN=$(grep -A6 "\[${SHORT_AWS_PROFILE}\]" ~/.aws/credentials | grep aws_session_token | awk '{print $NF}')
    AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY
    AWS_SECRET_ACCESS_KEY=$AWS_SECRET_KEY
    AWS_SESSION_TOKEN=$AWS_SECURITY_TOKEN
    export AWS_ACCESS_KEY AWS_SECRET_KEY AWS_SECURITY_TOKEN AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
}

get_long_term_credentials() {
    AWS_ACCESS_KEY=$(grep -A2 "\[${LONG_AWS_PROFILE}\]" ~/.aws/credentials | grep aws_access_key_id | awk '{print $NF}')
    AWS_SECRET_KEY=$(grep -A2 "\[${LONG_AWS_PROFILE}\]" ~/.aws/credentials | grep aws_secret_access_key | awk '{print $NF}')
    AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY
    AWS_SECRET_ACCESS_KEY=$AWS_SECRET_KEY
    export AWS_ACCESS_KEY AWS_SECRET_KEY AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
}

assume_role() {
    local aws_account_id=$(aws ssm get-parameter --name /target/account/${AWS_ACCOUNT} --query "Parameter.Value" --output text)
    echo "Using ${aws_account_id} AWS Account ID"

    local role_arn_to_assume="arn:aws:iam::${aws_account_id}:role/${AWS_ROLE_TO_ASSUME}"
    local identity_session=$(aws sts get-caller-identity | jq -r '.Arn' | awk -F'/' '{print $NF}')
    local role_session_name="${identity_session}@$(date +%s)"
    local local_profile=()
    if [ "z${LONG_AWS_PROFILE}" != "z" ]; then
      local_profile+=("--profile")
      local_profile+=("${LONG_AWS_PROFILE}")
    fi
    local assumed_credentials=$(aws sts assume-role ${local_profile[@]} --region us-west-1 \
        --role-arn "${role_arn_to_assume}" \
        --role-session-name "${role_session_name}")

    # Ansible
    AWS_ACCESS_KEY=$(echo ${assumed_credentials} | jq -r '.Credentials.AccessKeyId')
    AWS_SECRET_KEY=$(echo ${assumed_credentials} | jq -r '.Credentials.SecretAccessKey')
    AWS_SECURITY_TOKEN=$(echo ${assumed_credentials} | jq -r '.Credentials.SessionToken')
    export AWS_ACCESS_KEY AWS_SECRET_KEY AWS_SECURITY_TOKEN
    # AWS CLI
    AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY
    AWS_SECRET_ACCESS_KEY=$AWS_SECRET_KEY
    AWS_SESSION_TOKEN=$AWS_SECURITY_TOKEN
    export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
    echo "Assumed AWS_ACCESS_KEY is $AWS_ACCESS_KEY"
}

get_aws_account_id() {
  local account_id=$(aws sts get-caller-identity \
    --query "Account" \
    --output text)
  echo "${account_id}"
}

get_aws_account_name() {
  local aws_account_id=$(get_aws_account_id)
  local account_name=$(cat accounts.json \
    | jq --arg id "${aws_account_id}" -r '.Accounts[] | select(.Id==$id) | .Name' \
    2>/dev/null || echo 'UNKNOWN_AWS_ACCOUNT')
  echo "${account_name}"
}

get_instance_id() {
  local instance_id=$(aws ec2 describe-instances \
    --filters Name=tag:Name,Values="${INSTANCE_NAME}" \
    Name=instance-state-name,Values=running \
    --query Reservations[0].Instances[0].InstanceId --output text)
  echo "${instance_id}"
}

get_sns_topic_arn() {
  local topic_arn=""
  if [ "${SNS_TOPIC_ARN}" != "" ]; then
    topic_arn="${SNS_TOPIC_ARN}"
  else
    topic_arn=  $(aws cloudformation describe-stacks \
      --stack-name "${SNS_TOPIC_CFN_NAME}" \
      --query "Stacks[0].Outputs[?OutputKey=='${SNS_TOPIC_OUTPUT_NAME}'].OutputValue" \
      --output text)
  fi
  echo "${topic_arn}"
}

get_platform() {
  local instance_id=$1
  local platform=$(aws ec2 describe-instances \
    --instance-ids "${instance_id}" \
    --query "Reservations[0].Instances[0].Platform" \
    --output text 2>/dev/null || echo "none"
  )
  echo "${platform}"
}

launch() {
    local SCRIPT_ACTION=$1

    local SOURCE_REPO_URL=$(git remote get-url origin | cut -d':' -f2)
    local SOURCE_REPO_BRANCH=$(git branch| grep -e '^*' | awk '{print $2}')

    local instance_id=$(get_instance_id)
    local aws_account_name=$(get_aws_account_name)
    local platform=$(get_platform "${instance_id}")
    local sns_topic_arn=$(get_sns_topic_arn)
    local envdir=".venv"
    local manifest_argument=()
    local template_config_path=sceptre/helper-templates/cwalarm-config-template.yaml
    local sceptre_item="cwalarm/$(echo ${INSTANCE_NAME} | sed 's/\W//g').yaml"
    local sceptre_config_path="sceptre/config/${sceptre_item}"
    local cwalarm_yaml="sceptre/generated-config/ec2instance.yaml"
    local generate_script="cwalarmlinux.py"
    echo "platform is [${platform}]"
    if [ "${platform}" == "windows" ]; then
      generate_script="cwalarmwindows.py"
    fi

    rm -f "${cwalarm_yaml}" "${sceptre_config_path}"

    if [ "${CWALARM_MANIFEST}" != "" ]; then
      manifest_argument=("-m" "${CWALARM_MANIFEST}")
    fi
    virtualenv -p /usr/bin/python3 "${envdir}"
    source "${envdir}/bin/activate"
    pip install -r ./requirements.txt

    # Generate the YAML to be invoked by the sceptre config
    sceptre/helper-scripts/"${generate_script}" \
      -k InstanceId \
      -v "${instance_id}" \
      -i1 "${sns_topic_arn}" \
      -x1 "${sns_topic_arn}" \
      -a "${aws_account_name}" \
      ${manifest_argument[@]} \
      -o "${cwalarm_yaml}"

    echo "cp '${template_config_path}' '${sceptre_config_path}'"
    cp "${template_config_path}" "${sceptre_config_path}"
    # Remove the old CloudFormation stack if exists
    ./deploy-cfn-nodocker.sh \
      -e aws_region=${AWS_DEFAULT_REGION} \
      -n "destroy" \
      -i "${sceptre_item}"

    # Deploy the CloudFormation stack if required
    if [ "${SCRIPT_ACTION}" != "destroy" ]; then
      ./deploy-cfn-nodocker.sh \
        -e aws_region=${AWS_DEFAULT_REGION} \
        -n "${SCRIPT_ACTION}" \
        -i "${sceptre_item}"
    fi

    EXIT_STATUS=$?
    deactivate
    # rm -rf "${envdir}"
    exit ${EXIT_STATUS}

}

parse_arguments() {
    while (( "$#" )); do
      case "$1" in
        -a|--account)
          AWS_ACCOUNT=$2
          shift 2
          ;;
        -l|--long-term-profile)
          LONG_AWS_PROFILE=$2
          # Set AWS_ROLE_TO_ASSUME to the IAM Role name to assume
          # in the target account.
          shift 2
          ;;
        -s|--short-term-profile)
          SHORT_AWS_PROFILE=$2
          shift 2
          ;;
        -i|--instance-name)
          INSTANCE_NAME=$2
          shift 2
          ;;
        -sta|--sns-topic-arn)
          SNS_TOPIC_ARN=$2
          shift 2
          ;;
        -t|--sns-topic-cfn-name)
          SNS_TOPIC_CFN_NAME=$2
          shift 2
          ;;
        -o|--sns-topic-output-name)
          SNS_TOPIC_OUTPUT_NAME=$2
          shift 2
          ;;
        -m|--cwalarm-manifest)
          CWALARM_MANIFEST=$2
          shift 2
          ;;
        -n|--action)
          SCRIPT_ACTION=$2
          shift 2
          ;;
        --) # end argument parsing
          shift
          break
          ;;
        -*|--*=) # unsupported flags
          echo "Error: Unsupported flag $1" >&2
          exit 1
          ;;
        *) # preserve positional arguments
          PARAMS="$PARAMS $1"
          shift
          ;;
      esac
    done
    # set positional arguments in their proper place
    eval set -- "$PARAMS"
}

main() {

    # SWITCH_ACCOUNT=1
    parse_arguments $@
    if [ "z$AWS_ACCOUNT" != "z" ]; then
        # Call assume_role to switch AWS account
        assume_role
    elif [ "z$SHORT_AWS_PROFILE" != "z" ]; then
        get_short_term_credentials
    elif [ "z$LONG_AWS_PROFILE" != "z" ]; then
        get_long_term_credentials
    fi

    launch "${SCRIPT_ACTION}" "${CFN_CONFIG}"

}

main "$@"
