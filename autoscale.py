#!/usr/bin/env python

import os
import json
import time
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
        "service_name": "SERVICE AS REGISTERED IN CONSUL"
        "AWS_ACCESS_KEY_ID": "PLEASE FILL THIS OUT",
        "AWS_SECRET_ACCESS_KEY_ID": "PLEASE FILL THIS OUT"
    }

    def __init__(self, asg_name, region_name, service_name
            AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY_ID):
        self.asg_name = asg_name;
        self.region_name = region_name;
        self.service_name = service_name;
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

    def consul_lock(func):
        def func_wrapper(*args):
            consul = args[0].consul;
            asg_name = args[0].asg_name;
            session_id = consul.session.create(asg_name);
            if consul.kv.acquire_lock(asg_name + '/lock', session_id):
                instanceid = urllib2.urlopen('http://169.254.169.254/latest/meta-data/instance-id').read();
                boto3.client('ec2', aws_access_key_id=args[0].AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=args[0].AWS_SECRET_ACCESS_KEY_ID).modify_instance_attribute(
                    InstanceId=instanceid,
                    DisableApiTermination={'Value': True}
                );
                try:
                    func(*args)
                except:
                    boto3.client('ec2', aws_access_key_id=args[0].AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=args[0].AWS_SECRET_ACCESS_KEY_ID).modify_instance_attribute(
                        InstanceId=instanceid,
                        DisableApiTermination={'Value': False}
                    );
                    consul.kv.release_lock(asg_name + '/lock', session_id);
                    raise;
            boto3.client('ec2', aws_access_key_id=args[0].AWS_ACCESS_KEY_ID,
                aws_secret_access_key=args[0].AWS_SECRET_ACCESS_KEY_ID).modify_instance_attribute(
                InstanceId=instanceid,
                DisableApiTermination={'Value': False}
            );
            consul.kv.release_lock(asg_name + '/lock', session_id);
        return func_wrapper;

    @consul_lock
    def run(self):
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
            scale_amount = len(asg['Instances']) + 1 * 2;
        elif system_data['cpu_percent'] > self.cpu_upper_limit:
            scale_amount = len(asg['Instances']) + 1;
        elif len(asg['Instances']) > 2 and self.should_scale_down(system_data, len(asg['Instances'])):
            scale_amount = len(asg['Instances']) - 1;

        """
        If scaling down protect this instance from termination
        """
        if scale_amount != 0
            self.update_asg(client, asg, scale_amount);

    def update_asg(self, client, asg, scale_amount):
        asg['DesiredCapacity'] = scale_amount;
        if asg['MaxSize'] < asg['DesiredCapacity']:
            asg['MaxSize'] = asg['DesiredCapacity'];
        client.update_auto_scaling_group(
            AutoScalingGroupName=asg['AutoScalingGroupName'],
            DesiredCapacity=asg['DesiredCapacity'],
            MaxSize=asg['MaxSize']
        );
        registered_services = self.consul.catalog.service(self.service_name);
        while len(registered_services) != scale_amount:
            time.sleep(5);
            registered_services = self.consul.catalog.service(self.service_name);

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
