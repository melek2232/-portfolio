from glob import glob
from setuptools import find_packages, setup

package_name = 'robot_base'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/rviz', glob('rviz/*.rviz')),
        ('share/' + package_name + '/service', glob('service/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='melek',
    maintainer_email='todo@todo.todo',
    description='Motor driver, open-loop odometry, SLAM and Nav2 bring-up',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'base_node = robot_base.base_node:main',
            'explore = robot_base.explore:main',
            'cmd_mux = robot_base.cmd_mux:main',
            'scan_filter = robot_base.scan_filter:main',
            'health = robot_base.health:main',
            'map_autosave = robot_base.map_autosave:main',
        ],
    },
)
