#!/usr/bin/env python3

import boto3
import yaml

CONST_DEFAULT_IN_ALARM = 'x'
CONST_DEFAULT_OK_ALARM = 'x'
CONST_CWAGENT_NAMESPACE = 'CWAgent'
CONST_AWSEC2_NAMESPACE = 'AWS/EC2'

class ConfigGenerator:
  def __init__(self,
                key,
                value,
                output,
                in_alarm_warning,
                ok_alarm_warning,
                in_alarm_critical,
                ok_alarm_critical,
                use_recover='true',
                aws_account_name='unknown account',
                manifest_yaml_file='') -> None:
      self.dimension_key = key
      self.dimension_value = value
      self.use_recover = False if use_recover.lower() == 'false' else True
      self.output_file = output
      self.in_alarm_action_warning = in_alarm_warning if len(in_alarm_warning) > 0 else CONST_DEFAULT_IN_ALARM
      self.ok_alarm_action_warning = ok_alarm_warning if len(ok_alarm_warning) > 0 else CONST_DEFAULT_OK_ALARM
      self.in_alarm_action_critical = in_alarm_critical if len(in_alarm_critical) > 0 else self.in_alarm_action_warning
      self.ok_alarm_action_critical = ok_alarm_critical if len(ok_alarm_critical) > 0 else self.ok_alarm_action_warning
      self.instance_tag_name = self.get_instance_tag_name()
      self.alert_config = {
        'disk_used_percent' : {
          'enabled': True,
          'warning_threshold': '80',
          'critical_threshold': '95'
        },
        'mem_used_percent' : {
          'enabled': True,
          'warning_threshold': '90',
          'critical_threshold': '99'
        },
        'cpu_utilization' : {
          'enabled': True,
          'warning_threshold': '85',
          'critical_threshold': '99'
        },
        'cpu_credit_balance' : {
          'enabled': True,
          'warning_threshold': '500',
          'critical_threshold': '100'
        },
        'status_check_failed' : {
          'enabled': True
        }
      }
      self.aws_account_name = aws_account_name
      self.aws_account_id = self.get_aws_account_id()
      self.manifest_vars = {}
      self.load_manifest(manifest_yaml_file)
      self.metric_alarms = ["disk_used_percent",
                      "mem_used_percent",
                      "CPUCreditBalance",
                      "CPUUtilization",
                      "StatusCheckFailed",
                      "StatusCheckFailed_Instance",
                      "StatusCheckFailed_System"]
      self.metric_fstype = ["xfs", "ext2", "ext3", "ext4", "nfs4"]

  # Load manifest override from manifest_yaml_file
  def load_manifest(self, manifest_yaml_file):
    if manifest_yaml_file and len(manifest_yaml_file) > 0:
      with open(manifest_yaml_file, 'r') as manifest_handler:
        try:
          manifest_vars = yaml.safe_load(manifest_handler)
          print("load self.manifest_vars = {0}".format(manifest_vars))
          updated_config = {**self.alert_config, **manifest_vars}
          self.alert_config = updated_config
        except yaml.YAMLError as exc:
          print(exc)

  def get_aws_account_id(self):
    retval = ''
    client = boto3.client('sts')
    response = client.get_caller_identity()
    retval = response["Account"]
    return retval

  def get_instance_tag_name(self):
    retval = ''
    client = boto3.client('ec2')
    response = client.describe_tags(
      DryRun=False,
      Filters=[
        {
          'Name': 'resource-type',
          'Values': ['instance']
        },
        {
          'Name': 'resource-id',
          'Values': [self.dimension_value]
        },
        {
          'Name': 'key',
          'Values': ['Name']
        },
      ],
      MaxResults=10
    )
    if len(response["Tags"]) > 0:
      retval = response["Tags"][0]["Value"]
    return retval

  def get_metrics(self):
    client = boto3.client('cloudwatch')
    param_dimensions = [{'Name': self.dimension_key, 'Value': self.dimension_value}]
    metrics_data = client.list_metrics(Namespace='CWAgent',
                      Dimensions=param_dimensions)
    metrics = metrics_data['Metrics']
    metrics_data = client.list_metrics(Namespace='AWS/EC2',
                      Dimensions=param_dimensions)
    metrics = metrics + metrics_data['Metrics']
    return_value = []
    for metric in metrics:
      metric_name = metric['MetricName']
      if metric_name in self.metric_alarms:
        # We need to filter out any metric with fstype not defined in metric_fstype
        if metric_name == "disk_used_percent" and self.get_dimension_by_name(metric, "fstype") not in self.metric_fstype:
          continue
        return_value.append(metric)
    return(return_value)

  def get_alarm_dimensions(self, metric):
    dimensions = {}
    metric_dimensions = metric['Dimensions']
    for metric_dimension in metric_dimensions:
      dimension_name = metric_dimension['Name']
      dimension_value = "'{0}'".format(metric_dimension['Value'])
      dimensions[dimension_name] = dimension_value
    return(dimensions)

  def get_dimension_by_name(self, metric, dimension_name):
    return_value = ''
    metric_dimensions = metric['Dimensions']
    for dimension in metric_dimensions:
      if str(dimension['Name']).lower() == dimension_name.lower():
        return_value = dimension['Value']
        break
    return(return_value)

  # This is for Linux
  def get_alarm_disk_used_percent(self, metric, in_alarm_action='', ok_alarm_action='', critical_level='warning', critical_threshold='80'):
    return_value = {}
    return_value['comparison_operator'] = 'GreaterThanThreshold'
    return_value['datapoints_to_alarm'] = '2'
    return_value['evaluation_period'] = '3'
    return_value['period'] = '60'
    path = self.get_dimension_by_name(metric, "path")
    return_value['alarm_description'] = "'[{0}] AWS [{5}][{6}] high disk usage on [{4}] {1}:{2} on path {3}'".format(
        critical_level.upper(),
        self.dimension_key,
        self.dimension_value,
        path,
        self.instance_tag_name,
        self.aws_account_id,
        self.aws_account_name)
    return_value['alarm_name'] = "'[{0}] AWS [{5}][{6}] high disk usage on [{4}] {1}:{2} on path {3}'".format(
        critical_level.upper(),
        self.dimension_key,
        self.dimension_value,
        path,
        self.instance_tag_name,
        self.aws_account_id,
        self.aws_account_name)
    return_value['threshold'] = critical_threshold
    return_value['actions_enabled'] = True
    return_value['alarm_actions'] = [in_alarm_action]
    return_value['ok_actions'] = [ok_alarm_action]
    return_value['metric_name'] = metric['MetricName']
    return_value['statistic'] = 'Average'
    return_value['namespace'] = CONST_CWAGENT_NAMESPACE
    return_value['dimensions'] = self.get_alarm_dimensions(metric)
    return(return_value)

  # This is for Windows
  def get_alarm_disk_free_percent(self, metric, in_alarm_action='', ok_alarm_action='', critical_level='warning', critical_threshold='10'):
    return_value = {}
    return_value['comparison_operator'] = 'LessThanThreshold'
    return_value['datapoints_to_alarm'] = '2'
    return_value['evaluation_period'] = '3'
    return_value['period'] = '60'
    drive_instance = self.get_dimension_by_name(metric, "instance")
    return_value['alarm_description'] = "'[{0}] AWS [{5}][{6}] high disk usage on [{4}] {1}:{2} on path {3}'".format(
        critical_level.upper(),
        self.dimension_key,
        self.dimension_value,
        drive_instance,
        self.instance_tag_name,
        self.aws_account_id,
        self.aws_account_name)
    return_value['alarm_name'] = "'[{0}] AWS [{5}][{6}] high disk usage on [{4}] {1}:{2} on path {3}'".format(
        critical_level.upper(),
        self.dimension_key,
        self.dimension_value,
        drive_instance,
        self.instance_tag_name,
        self.aws_account_id,
        self.aws_account_name)
    return_value['threshold'] = critical_threshold  # Default value is '10'
    return_value['actions_enabled'] = True
    return_value['alarm_actions'] = [in_alarm_action]
    return_value['ok_actions'] = [ok_alarm_action]
    return_value['metric_name'] = metric['MetricName']
    return_value['statistic'] = 'Average'
    return_value['namespace'] = CONST_CWAGENT_NAMESPACE
    return_value['dimensions'] = self.get_alarm_dimensions(metric)
    return(return_value)

  def get_alarm_mem_used_percent(self, metric, in_alarm_action='', ok_alarm_action='', critical_level='warning', critical_threshold='95'):
    return_value = {}
    return_value['comparison_operator'] = 'GreaterThanThreshold'
    return_value['datapoints_to_alarm'] = '2'
    return_value['evaluation_period'] = '3'
    return_value['period'] = '60'
    return_value['alarm_description'] = "'[{0}] AWS [{4}][{5}] high memory usage on [{3}] {1}:{2}'".format(
        critical_level.upper(),
        self.dimension_key,
        self.dimension_value,self.instance_tag_name,
        self.aws_account_id,
        self.aws_account_name)
    return_value['alarm_name'] = "'[{0}] AWS [{4}][{5}] high memory usage on [{3}] {1}:{2}'".format(
        critical_level.upper(),
        self.dimension_key,
        self.dimension_value,self.instance_tag_name,
        self.aws_account_id,
        self.aws_account_name)
    return_value['threshold'] = critical_threshold
    return_value['actions_enabled'] = True
    return_value['alarm_actions'] = [in_alarm_action]
    return_value['ok_actions'] = [ok_alarm_action]
    return_value['metric_name'] = metric['MetricName']
    return_value['statistic'] = 'Average'
    return_value['namespace'] = CONST_CWAGENT_NAMESPACE
    return_value['dimensions'] = self.get_alarm_dimensions(metric)
    return(return_value)

  def get_alarm_cpu_utilization(self, metric, in_alarm_action='', ok_alarm_action='', critical_level='warning', critical_threshold='85'):
    return_value = {}
    return_value['comparison_operator'] = 'GreaterThanThreshold'
    return_value['datapoints_to_alarm'] = '5'
    return_value['evaluation_period'] = '5'
    return_value['period'] = '60'
    return_value['alarm_description'] = "'[{0}] AWS [{4}][{5}] high CPU Utilization on [{3}] {1}:{2}'".format(
        critical_level.upper(),
        self.dimension_key,
        self.dimension_value,
        self.instance_tag_name,
        self.aws_account_id,
        self.aws_account_name)
    return_value['alarm_name'] = "'[{0}] AWS [{4}][{5}] high CPU Utilization on [{3}] {1}:{2}'".format(
        critical_level.upper(),
        self.dimension_key,
        self.dimension_value,
        self.instance_tag_name,
        self.aws_account_id,
        self.aws_account_name)
    return_value['threshold'] = critical_threshold
    return_value['actions_enabled'] = True
    return_value['alarm_actions'] = [in_alarm_action]
    return_value['ok_actions'] = [ok_alarm_action]
    return_value['metric_name'] = metric['MetricName']
    return_value['statistic'] = 'Average'
    return_value['namespace'] = CONST_AWSEC2_NAMESPACE
    return_value['dimensions'] = self.get_alarm_dimensions(metric)
    return(return_value)

  def get_alarm_cpu_credit_balance(self, metric, in_alarm_action='', ok_alarm_action='', critical_level='warning', critical_threshold='500'):
    return_value = {}
    return_value['comparison_operator'] = 'LessThanOrEqualToThreshold'
    return_value['datapoints_to_alarm'] = '5'
    return_value['evaluation_period'] = '5'
    return_value['period'] = '60'
    return_value['alarm_description'] = "'[{0}] AWS [{4}][{5}] low CPU credit balance on [{3}] {1}:{2}'".format(
        critical_level.upper(),
        self.dimension_key,
        self.dimension_value,
        self.instance_tag_name,
        self.aws_account_id,
        self.aws_account_name)
    return_value['alarm_name'] = "'[{0}] AWS [{4}][{5}] low CPU credit balance on [{3}] {1}:{2}'".format(
        critical_level.upper(),
        self.dimension_key,
        self.dimension_value,
        self.instance_tag_name,
        self.aws_account_id,
        self.aws_account_name)
    return_value['threshold'] = critical_threshold
    return_value['actions_enabled'] = True
    return_value['alarm_actions'] = [in_alarm_action]
    return_value['ok_actions'] = [ok_alarm_action]
    return_value['metric_name'] = metric['MetricName']
    return_value['statistic'] = 'Average'
    return_value['namespace'] = CONST_AWSEC2_NAMESPACE
    return_value['dimensions'] = self.get_alarm_dimensions(metric)
    return(return_value)

  def get_alarm_status_check_failed(self, metric, in_alarm_action='', ok_alarm_action='', use_recover=False):
    return_value = {}
    return_value['comparison_operator'] = 'GreaterThanThreshold'
    return_value['datapoints_to_alarm'] = '2'
    return_value['evaluation_period'] = '2'
    return_value['period'] = '60'
    return_value['alarm_description'] = "'[CRITICAL] {0} AWS [{4}][{5}] on [{3}] {1}:{2}'".format(
        metric['MetricName'],
        self.dimension_key,
        self.dimension_value,
        self.instance_tag_name,
        self.aws_account_id,
        self.aws_account_name)
    return_value['alarm_name'] = "'[CRITICAL] {0} AWS [{4}][{5}] on [{3}] {1}:{2}'".format(
        metric['MetricName'],
        self.dimension_key,
        self.dimension_value,
        self.instance_tag_name,
        self.aws_account_id,
        self.aws_account_name)
    return_value['threshold'] = '2'
    return_value['actions_enabled'] = True
    if metric['MetricName'] == 'StatusCheckFailed_System' and use_recover:
      return_value['alarm_actions'] = [in_alarm_action, '!Sub "arn:aws:automate:${AWS::Region}:ec2:recover"']
    else:
      return_value['alarm_actions'] = [in_alarm_action]
    return_value['ok_actions'] = [ok_alarm_action]
    return_value['metric_name'] = metric['MetricName']
    return_value['statistic'] = 'Average'
    return_value['namespace'] = CONST_AWSEC2_NAMESPACE
    return_value['dimensions'] = self.get_alarm_dimensions(metric)
    return(return_value)

  def generate_yaml(self, metrics):
    parsed_data = []
    ii = 0
    prefix_name = 'alarm'
    for metric in metrics:
      metric_name = metric['MetricName']
      alarm_data = {}
      if metric_name == 'disk_used_percent' \
        and self.alert_config['disk_used_percent']['enabled']:
        critical_alarm_data = self.get_alarm_disk_used_percent(metric,
                              self.in_alarm_action_critical,
                              self.ok_alarm_action_critical,
                              'critical',
                              self.alert_config['disk_used_percent']['critical_threshold'])
        critical_alarm_data['name'] = "{0}{1:03d}".format(prefix_name, ii)
        ii += 1
        parsed_data.append(critical_alarm_data)
        warning_alarm_data = self.get_alarm_disk_used_percent(metric,
                              self.in_alarm_action_warning,
                              self.ok_alarm_action_warning,
                              'warning',
                              self.alert_config['disk_used_percent']['warning_threshold'])
        warning_alarm_data['name'] = "{0}{1:03d}".format(prefix_name, ii)
        ii += 1
        parsed_data.append(warning_alarm_data)
      elif metric_name == 'LogicalDisk % Free Space' \
        and self.alert_config['disk_free_percent']['enabled']:
          critical_alarm_data = self.get_alarm_disk_free_percent(metric,
                                  self.in_alarm_action_critical,
                                  self.ok_alarm_action_critical,
                                  'critical',
                                  self.alert_config['disk_free_percent']['critical_threshold'])
          critical_alarm_data['name'] = "{0}{1:03d}".format(prefix_name, ii)
          ii += 1
          parsed_data.append(critical_alarm_data)
          warning_alarm_data = self.get_alarm_disk_free_percent(metric, 
                                  self.in_alarm_action_warning,
                                  self.ok_alarm_action_warning,
                                  'warning',
                                  self.alert_config['disk_free_percent']['warning_threshold'])
          warning_alarm_data['name'] = "{0}{1:03d}".format(prefix_name, ii)
          ii += 1
          parsed_data.append(warning_alarm_data)
      elif metric_name == 'mem_used_percent' \
        and self.alert_config['mem_used_percent']['enabled']:
          # Filter out the metric with ImageId + InstanceType dimensions.
          if self.get_dimension_by_name(metric, 'ImageId') == '':
            critical_alarm_data = self.get_alarm_mem_used_percent(metric,
                                  self.in_alarm_action_critical,
                                  self.ok_alarm_action_critical,
                                  'critical',
                                  self.alert_config['mem_used_percent']['critical_threshold'])
            critical_alarm_data['name'] = "{0}{1:03d}".format(prefix_name, ii)
            ii += 1
            parsed_data.append(critical_alarm_data)
            warning_alarm_data = self.get_alarm_mem_used_percent(metric,
                                  self.in_alarm_action_warning,
                                  self.ok_alarm_action_warning,
                                  'warning',
                                  self.alert_config['mem_used_percent']['warning_threshold'])
            warning_alarm_data['name'] = "{0}{1:03d}".format(prefix_name, ii)
            ii += 1
            parsed_data.append(warning_alarm_data)
      elif metric_name == 'Memory % Committed Bytes In Use' \
        and self.alert_config['mem_used_percent']['enabled']:
          critical_alarm_data = self.get_alarm_mem_used_percent(metric,
                                  self.in_alarm_action_critical,
                                  self.ok_alarm_action_critical,
                                  'critical',
                                  self.alert_config['mem_used_percent']['critical_threshold'])
          critical_alarm_data['name'] = "{0}{1:03d}".format(prefix_name, ii)
          ii += 1
          parsed_data.append(critical_alarm_data)
          warning_alarm_data = self.get_alarm_mem_used_percent(metric,
                                    self.in_alarm_action_warning,
                                    self.ok_alarm_action_warning,
                                    'warning',
                                    self.alert_config['mem_used_percent']['warning_threshold'])
          warning_alarm_data['name'] = "{0}{1:03d}".format(prefix_name, ii)
          ii += 1
          parsed_data.append(warning_alarm_data)
      elif metric_name == 'CPUUtilization' \
        and self.alert_config['cpu_utilization']['enabled']:
          critical_alarm_data = self.get_alarm_cpu_utilization(metric,
                                self.in_alarm_action_critical,
                                self.ok_alarm_action_critical,
                                'critical',
                                self.alert_config['cpu_utilization']['critical_threshold'])
          critical_alarm_data['name'] = "{0}{1:03d}".format(prefix_name, ii)
          ii += 1
          parsed_data.append(critical_alarm_data)
          warning_alarm_data = self.get_alarm_cpu_utilization(metric,
                                self.in_alarm_action_warning,
                                self.ok_alarm_action_warning,
                                'warning',
                                self.alert_config['cpu_utilization']['warning_threshold'])
          warning_alarm_data['name'] = "{0}{1:03d}".format(prefix_name, ii)
          ii += 1
          parsed_data.append(warning_alarm_data)
      elif metric_name == 'CPUCreditBalance' \
        and self.alert_config['cpu_credit_balance']['enabled']:
          critical_alarm_data = self.get_alarm_cpu_credit_balance(metric,
                                self.in_alarm_action_critical,
                                self.ok_alarm_action_critical,
                                'critical',
                                self.alert_config['cpu_credit_balance']['critical_threshold'])
          critical_alarm_data['name'] = "{0}{1:03d}".format(prefix_name, ii)
          ii += 1
          parsed_data.append(critical_alarm_data)
          warning_alarm_data = self.get_alarm_cpu_credit_balance(metric,
                                self.in_alarm_action_warning,
                                self.ok_alarm_action_warning,
                                'warning',
                                self.alert_config['cpu_credit_balance']['warning_threshold'])
          warning_alarm_data['name'] = "{0}{1:03d}".format(prefix_name, ii)
          ii += 1
          parsed_data.append(warning_alarm_data)
      elif metric_name in ['StatusCheckFailed', 'StatusCheckFailed_Instance', 'StatusCheckFailed_System'] \
        and self.alert_config['status_check_failed']['enabled']:
          alarm_data = self.get_alarm_status_check_failed(metric,
                                self.in_alarm_action_critical,
                                self.ok_alarm_action_critical,
                                self.use_recover)
          alarm_data['name'] = "{0}{1:03d}".format(prefix_name, ii)
          ii += 1
          parsed_data.append(alarm_data)
    with open(self.output_file, 'a') as file:
      outputs = yaml.dump(parsed_data, file)

