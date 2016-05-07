#!/usr/bin/env python

import os
import json
import boto3
import psutil
import urllib2
import consulate
from botocore.client import ClientError


class AutoScale(object):
    # This is the default configuration which must be edited.
    empty_config_data = {
        "region_name": "us-east-1",
        "asg_name": "PLEASE FILL THIS OUT",
        "AWS_ACCESS_KEY_ID": "PLEASE FILL THIS OUT",
        "AWS_SECRET_ACCESS_KEY_ID": "PLEASE FILL THIS OUT"
    }

    def __init__(self, asg_name, region_name,
            AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY_ID):
        self.asg_name = asg_name;
        self.region_name = region_name;
        self.AWS_ACCESS_KEY_ID = AWS_ACCESS_KEY_ID;
        self.AWS_SECRET_ACCESS_KEY_ID = AWS_SECRET_ACCESS_KEY_ID;
        self.consul = consulate.Consul();
        self.cpu_upper_limit = 60;
        self.memory_upper_limit = 80;
        super(AutoScale, self).__init__()

    @classmethod
    def load_from_config(cls, config_filepath):
        with open(config_filepath, 'r') as config:
            config_data = json.load(config)
            return AutoScale(**config_data)

    @classmethod
    def create_empty_config(cls, config_filepath):
        """
        Create a default JSON config file. After this method is run,
        you must edit the file before this application can work.
        """
        with open(config_filepath, 'w') as config:
            json.dump(cls.empty_config_data, config, indent=4)

    def run(self):
        session_id = self.consul.session.create(self.asg_name);
        if self.consul.kv.acquire_lock(self.asg_name + '/lock', session_id):
            system_data = self.get_system_data();
            client = boto3.setup_default_session(region_name=self.region_name);
            client = boto3.client('autoscaling', aws_access_key_id=self.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY_ID);
            asg = client.describe_auto_scaling_groups(AutoScalingGroupNames=[
                self.asg_name
            ])['AutoScalingGroups'][0]

            scale_amount = 0;
            """
            Anything greater than 90% could require doubline or more
            otherwise just make incremental changes
            """
            if system_data['cpu_percent'] > 90:
                scale_amount = len(asg['Instances']) * 2;
            elif system_data['cpu_percent'] > this.cpu_upper_limit:
                scale_amount = len(asg['Instances']) + 1;
            elif len(asg['Instances']) > 2 and self.should_scale_down(system_data, len(asg['Instances'])):
                scale_amount = len(asg['Instances']) - 1;

            if scale_amount != 0:
                update_asg(client, asg, scale_amount);
            self.consul.kv.release_lock(self.asg_name + '/lock', session_id)

    def update_asg(self, client, asg, scale_amount):
        asg['DesiredCapacity'] = scale_amount;
        if asg['MaxSize'] < asg['DesiredCapacity']:
            asg['MaxSize'] = asg['DesiredCapacity'];
        client.update_auto_scaling_group(
            AutoScalingGroupName=asg['AutoScalingGroupName'],
            DesiredCapacity=asg['DesiredCapacity'],
            MaxSize=asg['MaxSize']
        );

    def should_scale_down(self, system_data, asg_instance_count):
        """
        Will scaling down put us over the cpu limit
        """
        total_cpu_load = system_data['cpu_percent'] * system_data['cpu_count'];
        new_cpu_load = total_cpu_load / (asg_instance_count - 1);

        if new_cpu_load < self.cpu_upper_limit / 1.5:
            return true;

        return false;

    def get_system_data(self):
        data = {
            "cpu_count" : psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1)
        };
        return data;

if __name__ == '__main__':
    import sys

    config_filepath = os.path.abspath(
        os.path.expanduser(
            '.env.json'
        )
    )
    # Check if the config file exists.
    # If not, create an empty one & prompt the user to edit it.
    if not os.path.exists(config_filepath):
        AutoScale.create_empty_config(config_filepath)
        print("Created an empty config file at %s." % config_filepath)
        print("Please modify it & re-run this command.")
        sys.exit(1)

    # If so, load from it & run.
    auto = AutoScale.load_from_config(config_filepath)

    try:
        auto.run()
    except KeyboardInterrupt:
        # We're done. Bail out without dumping a traceback.
        sys.exit(0)
