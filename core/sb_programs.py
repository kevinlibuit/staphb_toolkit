#!/usr/bin/env python3

import os
import sys
import json
from shutil import which
import multiprocessing as mp
import signal,psutil
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/' + '../..'))

##Test to see if singularity or docker is installed
if which('docker'):
    from staphb_toolkit.core import calldocker as container_engine
elif which('singularity'):
    from staphb_toolkit.core import callsing as container_engine
else:
    print('Singularity or Docker is not installed or not in found in PATH')
    sys.exit(1)

class Run:
    def __init__(self, command=None, path=None, docker_image=None):
        self.path=path
        self.docker_image = docker_image
        self.command = command
        # TODO: Find a better way to grab json file
        docker_config = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))[:-4] + "/core/docker_config.json"
        docker_tag = ""

        with open(docker_config) as config_file:
            config_file = json.load(config_file)
            try:
                docker_tag = config_file['images'][docker_image]
            except KeyError:
                print(f"The docker image for {docker_image} does not exist.")
                sys.exit()

        self.docker_tag = docker_tag

    def run(self):
        try:
            print(container_engine.call(f"staphb/{self.docker_image}:{self.docker_tag}", self.command, '/data', self.path))
        except KeyboardInterrupt:
            container_engine.shutdown()
            sys.exit()

class Run_multi:
    def __init__(self, command_list=None, path=None, docker_image=None):
        self.path = path
        self.docker_image = docker_image
        self.command_list = command_list
        # TODO: Find a better way to grab json file
        docker_config = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))[:-4] + "/core/docker_config.json"
        docker_tag = ""

        with open(docker_config) as config_file:
            config_file = json.load(config_file)
            try:
                docker_tag = config_file['images'][docker_image]
            except KeyError:
                print(f"The docker image for {docker_image} does not exist.")
                sys.exit()

        self.docker_tag = docker_tag

    def run(self,jobs):
        #initalize all workers to ignore signal int since we are handeling the keyboard interrupt ourself
        parent_id = os.getpid()
        def init_worker():
            #set signal for docker since containers are detached and we will kill them separately
            if which('docker'):
                signal.signal(signal.SIGINT, signal.SIG_IGN)
            #for singularity we will kill the child processes when the main process gets a signal
            else:
                def sig_int(signal_num,frame):
                    parent = psutil.Process(parent_id)
                    for child in parent.children():
                        if child.pid != os.getpid():
                            child.kill()
                    psutil.Process(os.getpid()).kill()
                signal.signal(signal.SIGINT,sig_int)

        #create multiprocessing pool
        pool = mp.Pool(processes=jobs,initializer=init_worker)

        try:
            results = pool.starmap_async(container_engine.call,[[f"staphb/{self.docker_image}:{self.docker_tag}",cmd,'/data',self.path] for cmd in self.command_list])
            stdouts = results.get()

        except KeyboardInterrupt:
            pool.terminate()
            pool.join()
            #shutdown containers
            container_engine.shutdown()
            sys.exit()
        else:
            pool.close()
            pool.join()

        for stdout in stdouts:
            print(stdout)
