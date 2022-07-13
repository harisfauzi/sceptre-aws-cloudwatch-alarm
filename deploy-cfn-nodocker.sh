#!/bin/bash

set -eEu -o pipefail +x

AWS_ACCOUNT=""
LONG_AWS_PROFILE=""
SHORT_AWS_PROFILE=""
ARG_ARRAY=()
SCRIPT_ACTION=""
CFN_CONFIG=""
DRY_RUN=""
PARAMS=""
AWS_ROLE_TO_ASSUME=FAODeployerRole

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

launch() {
    local script_action=$1
    local cfn_config=$2
    cd sceptre/

    local source_repo_url=$(git remote get-url origin | cut -d':' -f2)
    local source_repo_branch=$(git branch| grep -e '^*' | awk '{print $2}')
    local dir_prefix=""
    if [ "z${AWS_ACCOUNT}" != "z" ]; then
      dir_prefix="${AWS_ACCOUNT}/"
    fi

    if [ "z${script_action}" == "zdeploy" ]; then
        ACTION="launch -y"
    elif [ "z${script_action}" == "zdestroy" ]; then
        ACTION="delete -y"
    elif [ "z${SCRIPT_ACTION}" == "zgenerate" ]; then
        ACTION="generate"
    else
      echo "Invalid action. You need to define action as"
      echo "$0 -n <action>"
      echo "Where valid actions are choice of deploy, destroy, generate."
    fi

    if [ "z${DRY_RUN}" == "z" -o "z${DRY_RUN}" == "zfalse" ]; then
        echo "[Calling:]"
        echo "sceptre \
          "${ARG_ARRAY[@]}" \
          ${ACTION} ${dir_prefix}${cfn_config}"
        sceptre \
          "${ARG_ARRAY[@]}" \
          ${ACTION} ${dir_prefix}${cfn_config}
    fi
    local exit_status=$?
    cd ../
    exit ${exit_status}

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
          shift 2
          ;;
        -s|--short-term-profile)
          SHORT_AWS_PROFILE=$2
          shift 2
          ;;
        -e|--extra-vars)
          ARG_ARRAY+=("--var" "${2}")
          shift 2
          ;;
        -f|--var-file)
          ARG_ARRAY+=("--var-file" "./vars/${2}")
          shift 2
          ;;
        -n|--action)
          SCRIPT_ACTION=$2
          shift 2
          ;;
        -i|--item)
          CFN_CONFIG=$2
          shift 2
          ;;
        -d|--dry-run)
          DRY_RUN=$2
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

get_template() {
  local git_branch=main
  git clone -b "${git_branch}" --depth 1 https://github.com/harisfauzi/shared-sceptre-template.git shared-sceptre-template
  local current_dir=$(pwd)
  (cd "${current_dir}/shared-sceptre-template/templates"; tar cf - .) | (cd "${current_dir}/sceptre/templates"; tar xf -)
  rm -rf shared-sceptre-template
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

    get_template
    launch "${SCRIPT_ACTION}" "${CFN_CONFIG}"

}

main "$@"
