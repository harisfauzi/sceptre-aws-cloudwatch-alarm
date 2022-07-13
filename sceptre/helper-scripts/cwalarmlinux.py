#!/usr/bin/env python3

import argparse

from configgenerator import ConfigGenerator

class LinuxConfigGenerator(ConfigGenerator):
  pass

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
  config_generator = LinuxConfigGenerator(
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