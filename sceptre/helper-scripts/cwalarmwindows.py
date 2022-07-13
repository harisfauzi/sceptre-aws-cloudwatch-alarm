#!/usr/bin/env python3

import argparse

from configgenerator import ConfigGenerator

class WindowsConfigGenerator(ConfigGenerator):
  def __init__(self,
                key,
                value,
                output,
                in_alarm_warning,
                ok_alarm_warning,
                in_alarm_critical,
                ok_alarm_critical,
                use_recover='false',
                aws_account_alias='unknown account',
                manifest_yaml_file='') -> None:
      super().__init__(key,
                      value,
                      output,
                      in_alarm_warning,
                      ok_alarm_warning,
                      in_alarm_critical,
                      ok_alarm_critical,
                      use_recover,
                      aws_account_alias,
                      manifest_yaml_file)
      self.alert_config = {
        'disk_free_percent' : {
          'enabled': True,
          'warning_threshold': '10',
          'critical_threshold': '5'
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
      # Call this again to override values from manifest file.
      self.load_manifest(manifest_yaml_file)
      self.metric_alarms = ['LogicalDisk % Free Space',
                      'Memory % Committed Bytes In Use',
                      'CPUCreditBalance',
                      'CPUUtilization',
                      'StatusCheckFailed',
                      'StatusCheckFailed_Instance',
                      'StatusCheckFailed_System']

      
def main():

  parser = argparse.ArgumentParser(description="Generate YAML for sceptre_user_data")
  parser.add_argument('-r', dest='userecover', default='false',
                    help='The MetricName to filter')
  parser.add_argument('-k', dest='key', default='AutoScalingGroupName',
                    help='The Dimension Key to filter')
  parser.add_argument('-v', dest='value', default='',
                    help='The Dimension Value to filter')
  parser.add_argument('-o', dest='output', default='output.yaml',
                    help='The output file')
  parser.add_argument('-i1', dest='in_alarm_warning', default='',
                    help='The ARN for in alarm action for [WARNING]')
  parser.add_argument('-x1', dest='ok_alarm_warning', default='',
                    help='The ARN for OK action for [WARNING]')
  parser.add_argument('-i2', dest='in_alarm_critical', default='',
                    help='The ARN for in alarm action for [CRITICAL]')
  parser.add_argument('-x2', dest='ok_alarm_critical', default='',
                    help='The ARN for OK action for [CRITICAL]')
  parser.add_argument('-a', dest='account_alias', default='unknown account',
                    help='The AWS account name/alias')
  parser.add_argument('-m', dest='manifest', help='The path to manifest YAML')

  args = parser.parse_args()
  config_generator = WindowsConfigGenerator(
                      args.key, args.value,
                      args.output,
                      args.in_alarm_warning, args.ok_alarm_warning,
                      args.in_alarm_critical, args.ok_alarm_critical,
                      args.userecover, args.account_alias,
                      args.manifest)

  metrics = config_generator.get_metrics()
  config_generator.generate_yaml(metrics)

if __name__ == "__main__":
    main()