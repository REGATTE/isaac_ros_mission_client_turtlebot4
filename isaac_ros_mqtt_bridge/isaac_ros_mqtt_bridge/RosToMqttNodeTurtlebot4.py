# SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
# Copyright (c) 2021-2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""Implementation for RosToMqttNodeTurtlebot4."""
import json
import socket
import time

from isaac_ros_mqtt_bridge.MqttBridgeUtils import convert_dict_keys

import paho.mqtt.client as mqtt
import rclpy
from rclpy.node import Node

from rosbridge_library.internal import message_conversion
from rosbridge_library.internal import ros_loader


class RosToMqttNodeTurtlebot4(Node):
    """
    Bridge node that converts ROS messages to MQTT messages.

    Bridge node that subscribes to a ROS topic, translates the received message to a JSON,
    and publishes it to a MQTT channel.
    """

    def __init__(self, name='ros_to_mqtt_bridge_node'):
        """Construct the RosToMqttBridgeTurtlebot4."""
        super().__init__(name)
        self.declare_parameters(
            namespace='',
            parameters=[
                ('interface_name', 'uagv'),
                ('major_version', 'v2'),
                ('manufacturer', 'irobot'),
                ('serial_number', 'turtlebot4'),
                ('mqtt_client_name', 'RosToMqttBridgeTurtlebot4'),
                ('mqtt_host_name', 'localhost'),
                ('mqtt_port', 1883),
                ('mqtt_transport', 'tcp'),
                ('mqtt_ws_path', ''),
                ('mqtt_keep_alive', 60),
                ('ros_subscriber_type', 'vda5050_msgs/NodeState'),
                ('ros_subscriber_queue', 1),
                ('convert_snake_to_camel', True),
                ('reconnect_period', 5),
                ('retry_forever', False),
                ('num_retries', 10)
            ]
        )

        self.mqtt_client = mqtt.Client(
            self.get_parameter('mqtt_client_name').value,
            transport=self.get_parameter('mqtt_transport').value)

        if self.get_parameter('mqtt_transport').value == 'websockets' and \
                self.get_parameter('mqtt_ws_path').value != '':
            self.mqtt_client.ws_set_options(path=self.get_parameter('mqtt_ws_path').value)

        self.interface_name = self.get_parameter('interface_name').value
        self.major_version = self.get_parameter('major_version').value
        self.manufacturer = self.get_parameter('manufacturer').value
        self.serial_number = self.get_parameter('serial_number').value
        self.mqtt_topic_prefix = \
            f'{self.interface_name}/{self.major_version}/{self.manufacturer}/{self.serial_number}'

        def on_mqtt_connect(client, userdata, flags, rc):
            self.get_logger().info(f'Connected with result code {str(rc)}')

        def on_mqtt_disconnect(client, userdata, rc):
            if rc != 0:
                self.get_logger().info(f'Disconnected with result code {str(rc)}')

        self.mqtt_client.on_connect = on_mqtt_connect
        self.mqtt_client.on_disconnect = on_mqtt_disconnect

        self.subscription = self.create_subscription(
            ros_loader.get_message_class(
                self.get_parameter('ros_subscriber_type').value),
            'ros_sub_topic', self.__ros_subscriber_callback,
            self.get_parameter('ros_subscriber_queue').value)

        max_retries = self.get_parameter('num_retries').value
        retries = 0
        connected = False
        retry_forever = self.get_parameter('retry_forever').value
        while retries < max_retries or retry_forever:
            try:
                self.mqtt_client.connect(
                    self.get_parameter('mqtt_host_name').value,
                    self.get_parameter('mqtt_port').value,
                    self.get_parameter('mqtt_keep_alive').value)
                connected = True
                break
            except ConnectionRefusedError as e:
                self.get_logger().error(f'Connection Error: {e}. Please check the mqtt_host_name.')
                time.sleep(self.get_parameter('reconnect_period').value)
                retries += 1
            except socket.timeout as e:
                self.get_logger().error(f'Connection Error: {e}. Please check the mqtt_host_name'
                                        ' and make sure it is reachable.')
                time.sleep(self.get_parameter('reconnect_period').value)
                retries += 1
            except socket.gaierror as e:
                self.get_logger().error(f'Connection Error: {e}. Could not resolve mqtt_host_name')
                time.sleep(self.get_parameter('reconnect_period').value)
                retries += 1
        if connected:
            self.mqtt_client.loop_start()
        else:
            self.get_logger().error('Failed to connect to MQTT broker, ending retries.')

    def __ros_subscriber_callback(self, msg):
        try:
            extracted = message_conversion.extract_values(msg)
            if self.get_parameter('convert_snake_to_camel').value:
                self.mqtt_client.publish(
                    f'{self.mqtt_topic_prefix}/state',
                    json.dumps(convert_dict_keys(extracted, 'snake_to_dromedary')))
            else:
                self.mqtt_client.publish(f'{self.mqtt_topic_prefix}/state', json.dumps(extracted))
        except (message_conversion.FieldTypeMismatchException,
                json.decoder.JSONDecodeError) as e:
            self.get_logger().info(repr(e))


def main(args=None):
    """Execute the RosToMqttNodeTurtlebot4."""
    rclpy.init(args=args)
    node = RosToMqttNodeTurtlebot4('ros_to_mqtt_bridge_node')
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
