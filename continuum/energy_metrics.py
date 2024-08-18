import os
import sys
import signal
import subprocess
import time
import argparse
import configparser
import re
import uuid
import random
import multiprocessing
from typing import Callable
from multiprocessing import Pool

# Place in same folder as continuu.py to hijack Continuum processes using Continuum main branch last checked on 2024-06-01.
import continuum


def print_with_time(to_print: str):
    out_str = f'{time.strftime("%H:%M:%S", time.localtime(time.time()))} {to_print}'
    print(out_str)


def init_argparse() -> argparse.ArgumentParser:
    # Get input arguments, and validate those arguments..

    # Use same formatter_class setting as Continuum.
    parser_obj = argparse.ArgumentParser(
        formatter_class=continuum.make_wide(argparse.HelpFormatter, w=120, h=500)
    )

    # parser_obj.add_argument(
    #     "config",
    #     type=str,
    #     help="benchmark config file",
    # )

    # # Specify whether Continuum should use DEBUG logging or the default INFO logging.    
    # parser_obj.add_argument(
    #     "-v", 
    #     # Name "verbose" has to stay consistent with Continuum.
    #     "--verbose", 
    #     action="store_true", 
    #     help="Increase verbosity level, flag used = DEBUG, flag unused = INFO",
    #     default=False
    # )
    # parser_obj.add_argument("-v", "--verbose", action="store_true", help="increase verbosity level", default=False)


    parser_obj.add_argument(
        "-mi", 
        "--measure-interval", 
        action="store", 
        help="Time measuring VMs", 
        default=300, 
        type=int
    )

    parser_obj.add_argument(
        "-en", 
        "--experiment-names", 
        nargs="+",
        help="(REQUIRED) List of experiment names to run separated by space (choose from qemu qemu_virtiofsd qemu_cpu100 kube kube_cpu100 kube_prom kube_sca kube_sca_sched kube_sca_dsb kube_sca_dsb_sched)",  
        required=True
    )
    
    parser_obj.add_argument(
        "-r", 
        "--runs", 
        action="store", 
        help="Number of times the experiment is performed", 
        default=5, 
        type=int
    )
    
    parser_obj.add_argument(
        "--keep-vms", 
        action="store_true", 
        help="Keep VMs used in experiment (only last run of VMs kept)"
    )

    return parser_obj


# def setup_logging(args, parser_obj):
#     """
#     """
#     continuum.set_logging(args)

#     continuum.input.print_input(args.benchmark_config)


def get_modified_time(file):
    """Get the time the file was last modified through ctime (works for Unix).

    Equavalent command:
    stat --format=%Y {file}

    Args:
        file (str): full path to file

    Returns:
        str: ctime, time of last metadata change
    """
    return os.stat(file).st_ctime


def get_first_line(file):
    """Get the first line of the file.

    Equivalent command:
    head -n 1 {file}

    Args:
        file (str): full path to file

    Returns:
        str: first line of file
    """
    with open(file) as f:
        return f.readline()


def get_last_log_filename():
    """Get the last log file produced based on the name by using the datetime included.

    Returns:
        str: last log file according to datetime included in name
    """
    logs_dir = '/home/tkemenade/continuum/logs'
    log_files = [log_file for log_file in os.listdir(logs_dir) if log_file.endswith('.log')]
    log_files.sort()
    return log_files[-1]


def get_vms_from_log(log_filename):
    with open(f'/home/tkemenade/continuum/logs/{log_filename}') as log_file:
        return zip(*[line.split()[1].split('@') for line in log_file.readlines() if line.strip().startswith('ssh ') and line.strip().endswith('/.ssh/id_rsa_continuum')])


def get_vm_count():
    return len([process.split() for process in subprocess.run(['ps', '-ef'], check=True, text=True, stdout=subprocess.PIPE).stdout.split('\n') if len(process.split()) > 0 and "libvirt+" in process.split()[0]])


def run_continuum(config_path: str) -> int:
    process = subprocess.Popen(f'python3 continuum.py {config_path}', shell=True, text=True, stdout=subprocess.PIPE, preexec_fn=os.setsid)

    # Wait for Continuum to finish by waiting for string "ssh cloud" which is outputted once everything is started to connect to the VMs
    while True:
        stdout_line = process.stdout.readline()
        if "ssh cloud" in stdout_line:
            break
    return -1


def run_scaphandre():
    process = subprocess.Popen('sudo /home/tkemenade/scaphandre/target/release/scaphandre qemu', shell=True, text=True, stdout=subprocess.PIPE, preexec_fn=os.setsid)

    # Wait for scaphandre startup by waiting for string "Sending" from "Sending ⚡ metrics"
    while True:
        stdout_line = process.stdout.readline()
        if "Sending" in stdout_line:
            break
    return process.pid


def kill(process_name, pid):
    # https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true/4791612#4791612
    if (pid < 0):
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        print_with_time(f'Killed {process_name}!{pid}')
    except:
        print_with_time("No process found")


def get_global_proc_stat_metrics():
    return f'{time.time()} {sum([int(val) for val in get_first_line("/proc/stat").split()[1:3]])}\n'


def get_pid_proc_stat_metrics(pid):
    usr_time, sys_time = get_first_line(f'/proc/{pids[i]}/stat').split()[13:15]
    return usr_time, sys_time


def save_synced_resource_usage(sync_with, vm_names, run, limit):
    if len(vm_names) == 0:
        print("No vms provided")
        return

    # Get pid of guest VM processes
    all_processes = subprocess.run(['ps', '-ef'], check=True, text=True, stdout=subprocess.PIPE).stdout
    vm_processes = [process for process in all_processes.split('\n') if '_tkemenade' in process and 'libvirt+' in process]
    pids = [0] * len(vm_names)
    for vm_process in vm_processes:
        proc_info = vm_process.split()
        guest_name = proc_info[9][6:].split(',')[0]
        idx = vm_names.index(guest_name)
        pids[idx] = proc_info[1]
    
    if 0 in pids:
        print("pids not valid")
        return

    # Wait untill energy_uj created by Scaphandre exists
    sync_paths = [sync_with + vm_name + '/intel-rapl:0/energy_uj' for vm_name in vm_names]
    for path in sync_paths:
        while True:
            if os.path.exists(path):
                break

    with open(f'/home/tkemenade/continuum/res/{run}_metrics.txt', 'w') as metrics_file:
        metrics_file.write(get_global_proc_stat_metrics())
        for i in range(len(vm_names)):
            proc_usr_time, proc_sys_time = get_first_line(f'/proc/{pids[i]}/stat').split()[13:15]
            metrics_file.write(f'{vm_names[i]} {get_first_line(sync_paths[i])} {proc_usr_time} {proc_sys_time}\n')
        metrics_file.write('\n')

        # cat /proc/[pid]/stat
        # 1-index
        # 14 user time
        # 15 system time


        prev_modified_times = [get_modified_time(sync_paths[i]) for i in range(len(vm_names))]
        clock_times = [time.time()] * len(vm_names)
        start = time.time()
        while time.time() - start < limit:
            for i in range(len(vm_names)):
                new_modified_time = get_modified_time(sync_paths[i])
                new_clock_time = time.time()
                modified = prev_modified_times[i] != new_modified_time

                # if modified:
                #     print(f'modified {vm_names[i]} at {new_clock_time}')
                if modified or new_clock_time - clock_times[i] > 1:
                    metrics_file.write(get_global_proc_stat_metrics())
                    proc_usr_time, proc_sys_time = get_first_line(f'/proc/{pids[i]}/stat').split()[13:15]
                    metrics_file.write(f'{vm_names[i]} {get_first_line(sync_paths[i])} {proc_usr_time} {proc_sys_time}\n\n')
                    
                    prev_modified_times[i] = new_modified_time
                    clock_times[i] = new_clock_time

            time.sleep(0.1)

    print("Exit sync loop")


def destroy_vm(vm_name):
    subprocess.run(['virsh', 'destroy', vm_name], check=True, text=True)


def create_ssh_process(vm_name: str, host_name: str) -> int:
    return subprocess.Popen(['ssh', '-tt', f'{vm_name}@{host_name}', '-i', '/home/tkemenade/.ssh/id_rsa_continuum'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True, bufsize=0, preexec_fn=os.setsid)


def overwrite_file(ssh_process, file_path: str, content: str):
    if content == "":
        return
    ssh_process.stdin.write(f"echo \"{content}\" > \"{file_path}\"\n")
    
    # Let file write finish
    sync_stdout_with_guid(ssh_process)


def escape_popen(unescaped_str: str) -> str:
    return re.sub(r'[\"\$\\]', lambda match: "\\" + match.group(0), unescaped_str)


def read_file(file_path: str) -> str:
    if not os.path.exists(file_path):
        print_with_time(f"read file: file path doesn't exist {file_path}")
        return ""
    with open(file_path, 'r') as file:
        return escape_popen(file.read())


def get_pod_name_from_pods_str(pod_str: str) -> str:
    sub_strs = pod_str[4:].split("-")
    res = sub_strs[0]
    for sub_str in sub_strs[1:]:
        if not any(char.isdigit() for char in sub_str):
            res += "-" + sub_str
    return res


def sync_stdout_with_guid(ssh_process):
    guid = str(uuid.uuid4())
    print_with_time(f"Wait until guid {guid}")
    ssh_process.stdin.write(f"echo \"{guid}\"\n")
    while True:
        line = ssh_process.stdout.readline()
        if guid in line and not "echo" in line:
            print_with_time(f"Done waiting for guid{guid}")
            break
        else:
            print(line, end='')


def wait_for_kube_pods(ssh_process, pods: list[str], namespace=None):
    # Make sure commands before kubectl wait finished
    sync_stdout_with_guid(ssh_process)

    wait_time = 120
    command = f'kubectl wait pod --all {"--all-namespaces" if namespace is None else f"-n {namespace}"} --for=condition=Ready --timeout {wait_time}s\n'
    empty_line = 0
    while len(pods) > 0:
        ssh_process.stdin.write(command)
    
        print_with_time(f"{command}\nwait for kube remaining pods: {pods}")

        timed_out = 0

        start = time.time()

        while timed_out < len(pods) and time.time() - start < wait_time:
            stdout_line = ssh_process.stdin.write("\n")
            empty_line += 1

            stdout_line = ssh_process.stdout.readline()

            if (stdout_line == '\n'):
                # print_with_time(f"wait for kube: skip empty")
                if empty_line % 10 == 0:
                    empty_line = 0
                    # print_with_time(f"wait for kube: 10s")
                    # time.sleep(10)
                    time.sleep(0.5)
                continue
            else:
                empty_line -= 1

            if "cloud_controller_tkemenade@cloudcontrollertkemenade" not in stdout_line:
                print_with_time(f"wait for kube: {stdout_line}")

            if "pod/" in stdout_line:
                if "condition met" in stdout_line:
                    idx_to_remove = -1
                    for i in range(len(pods)):
                        if pods[i] in stdout_line:
                            idx_to_remove = i
                            break
                    if (idx_to_remove >= 0):
                        pod_name = pods[idx_to_remove]
                        del pods[idx_to_remove]
                        print_with_time(f"condition met for {pod_name} remaining {len(pods)}")
                elif "timed out waiting for the condition on" in stdout_line:
                    idx_found = -1
                    for i in range(len(pods)):
                        if pods[i] in stdout_line:
                            idx_found = i
                            break
                    if (idx_found >= 0):
                        print_with_time(f"timed out for {pods[idx_found]} remaining {len(pods)}")
                        timed_out += 1
        print(f"waited {time.time() - start} < {wait_time} with {timed_out} < {len(pods)}")


def vm_setup_qemu(vm_name: str, host_name: str) -> int:
    print_with_time(f"Setup qemu {vm_name}, {host_name}")
    ssh_process = create_ssh_process(vm_name, host_name)
    
    sync_stdout_with_guid(ssh_process)

    ssh_process.stdin.write("sudo apt remove unattended-upgrades -y\n")
    ssh_process.stdin.write("sudo apt update && sudo apt upgrade -y\n")
    ssh_process.stdin.write("\n")

    # Wait for VM update to finish by waiting for string "done"
    while True:
        stdout_line = ssh_process.stdout.readline()
        print_with_time(f"qemu {vm_name}: {stdout_line}")
        if "done" in stdout_line or ("upgraded" in stdout_line and "newly installed" in stdout_line):
            break
        if "Failed to restart snapd" in stdout_line or "thread 'main' panicked" in stdout_line:
            print_with_time(f"qemu {vm_name}: failed to update/upgrade, hoping it doesn't trigger later")
            break

    kill("qemu automatic updates executed", ssh_process.pid)
    time.sleep(1)  # Starting to fast after update can cause errors
    return -1


def vm_setup_virtiofs(vm_name: str, host_name: str) -> int:
    print_with_time(f"Setup virtiofsd {vm_name}, {host_name}")
    ssh_process = create_ssh_process(vm_name, host_name)

    sync_stdout_with_guid(ssh_process)

    ssh_process.stdin.write('sudo mkdir /var/scaphandre\n')
    ssh_process.stdin.write('sudo mount -t virtiofs scaphandre /var/scaphandre\n')
    ssh_process.stdin.write('\n')
    ssh_process.stdin.write('ls /var/scaphandre\n')
    ssh_process.stdin.write('\n')

    # Wait for virtiofs to connect by waiting for string "intel-rapl:0 from command ls"
    while True:
        stdout_line = ssh_process.stdout.readline()
        print_with_time(f"virtiofsd: {stdout_line}")
        if "intel-rapl:0" in stdout_line:
            break

    kill("virtiofsd mounted", ssh_process.pid)
    return -1


def vm_setup_scaphandre(vm_name: str, host_name: str, wait: bool) -> int:
    print_with_time(f"Setup scaphandre {vm_name}, {host_name}")
    ssh_process = create_ssh_process(vm_name, host_name)

    sync_stdout_with_guid(ssh_process)

    ssh_process.stdin.write('git clone --depth 1 --branch v1.0.0 https://github.com/hubblo-org/scaphandre.git\n')
    ssh_process.stdin.write('sudo snap install helm --classic\n')

    # Wait for install to finish
    sync_stdout_with_guid(ssh_process)

    ssh_process.stdin.write('cd scaphandre\n')

    overwrite_file(ssh_process, 'helm/scaphandre/values.yaml', read_file('res/config/write_as_file/scaphandre/values.yaml'))
    overwrite_file(ssh_process, 'helm/scaphandre/templates/daemonset.yaml', read_file('res/config/write_as_file/scaphandre/daemonset.yaml'))
    
    ssh_process.stdin.write('helm install scaphandre helm/scaphandre\n')
    print_with_time(f"scaphandre kube: installed")
    
    if wait:
        wait_for_kube_pods(ssh_process, ["scaphandre"], namespace="default")

    ssh_process.stdin.write('\n')
    print_with_time(f"Finished setup scaphandre {vm_name}, {host_name}")

    # Give 1 additional second for the other scaphandre instances to catch up
    time.sleep(1)

    return ssh_process.pid


def vm_setup_dsb(vm_name: str, host_name: str, wait: bool) -> int:
    pods = [
        "compose-post-service", 
        "home-timeline-redis", 
        "home-timeline-service", 
        "jaeger", 
        "media-frontend", 
        "media-memcached", 
        "media-mongodb", 
        "media-service", 
        "nginx-thrift", 
        "post-storage-memcached", 
        "post-storage-mongodb", 
        "post-storage-service", 
        "social-graph-mongodb", 
        "social-graph-redis", 
        "social-graph-service", 
        "text-service", 
        "unique-id-service", 
        "url-shorten-memcached", 
        "url-shorten-mongodb", 
        "url-shorten-service", 
        "user-memcached", 
        "user-mention-service", 
        "user-mongodb", 
        "user-service", 
        "user-timeline-mongodb", 
        "user-timeline-redis", 
        "user-timeline-service"
    ]
    # TODO still need to switch when scheduler is on to use right scheduler
    print_with_time(f"Setup DSB {vm_name}, {host_name}")
    ssh_process = create_ssh_process(vm_name, host_name)
    ssh_process.stdin.write('git clone --depth 1 --branch socialNetwork-0.3.2 https://github.com/delimitrou/DeathStarBench.git\n')
    ssh_process.stdin.write('sudo snap install helm --classic\n')

    # Wait for install to finish
    sync_stdout_with_guid(ssh_process)
    input("IS DSB INSTALLED?")
    
    overwrite_file(ssh_process, './DeathStarBench/socialNetwork/helm-chart/socialnetwork/values.yaml', read_file('res/config/write_as_file/dsb/values.yaml'))
    for pod in pods:
        overwrite_file(ssh_process, f'./DeathStarBench/socialNetwork/helm-chart/socialnetwork/charts/{pod}/values.yaml', read_file(f'res/config/write_as_file/dsb/{pod}/values.yaml'))
    ssh_process.stdin.write('helm install dsb ./DeathStarBench/socialNetwork/helm-chart/socialnetwork\n')
    
    if wait:
        wait_for_kube_pods(ssh_process, pods, namespace="default")

        # ready = input("DSB ready? [Y/N]")
        # if (ready.lower() == 'y'):
        #     break
    
    ssh_process.stdin.write('\n')
    kill("DeathStarBench started", ssh_process.pid)
    # Doesn't include enabled scaling options
    return -1


def vm_setup_sched(vm_name: str, host_name: str, wait: bool) -> int:
    ssh_process = create_ssh_process(vm_name, host_name)
    ssh_process.stdin.write('nohup kubectl port-forward --namespace=monitoring --address=192.168.221.2,192.168.221.2 svc/prometheus-k8s 9090:9090 > /dev/null 2>&1 &\n')
    overwrite_file(ssh_process, 'scheduler.yaml', read_file('res/config/write_as_file/scheduler/values.yaml'))
    ssh_process.stdin.write('kubectl create -f scheduler.yaml\n')
    if wait:  
        wait_for_kube_pods(ssh_process, ["escheduler"], namespace="kube-system")
        
    ssh_process.stdin.write('\n')
    # TODO finish config
    kill("KubePowerSched started", ssh_process.pid)
    return -1


def vm_setup_wrk_from_dsb(vm_name: str, host_name: str):
    print_with_time(f"Setup DSB {vm_name}, {host_name}")
    ssh_process = create_ssh_process(vm_name, host_name)
    if (True):
        input("ENTER TO CONTINUE ONCE wrk2 downloaded")
    else:
        # Get dependencies
        ssh_process.stdin.write("sudo apt-get install -y libssl-dev libz-dev luarocks make && sudo luarocks install luasocket\n")

        sync_stdout_with_guid(ssh_process)

        # Open wrk2 folder from DSB
        ssh_process.stdin.write("cd ./DeathStarBench/wrk2\n")

        # Get luajit folder into DeathStarBench
        ssh_process.stdin.write("cd deps && rm -r luajit && git clone https://github.com/LuaJIT/LuaJIT.git && cd LuaJIT && git reset --hard 2090842410e0ba6f81fad310a77bf5432488249a && cd .. && mv LuaJIT/ luajit/ && cd ..\n")

        # Wait for install to finish
        sync_stdout_with_guid(ssh_process)

        # Build and install
        ssh_process.stdin.write("make -j\n")
        ssh_process.stdin.write("sudo make install\n")  # Put wrk into /usr/local/bin

    # Forward nginx port of DeathStarBench
    ssh_process.stdin.write("cd ~")
    return ssh_process.pid


def cpu_load_no_kube(vm_name: str, host_name: str, cores: int) -> int:
    print_with_time(f"Setup qemu cpu100 {vm_name}, {host_name}")
    ssh_process = create_ssh_process(vm_name, host_name)
    # Using rust executable from host placed in /var/scaphandre on guest using virtiofsd. 
    ssh_process.stdin.write(f'/var/scaphandre/block_cpu -n {cores}\n')

    # Wait for block cpu to start by waiting for string "Blocking"
    while True:
        stdout_line = ssh_process.stdout.readline()
        print_with_time(f"cpu100: {stdout_line}")
        if "Blocking" in stdout_line:
            break

    print_with_time(f"Finished setup qemu cpu100 {vm_name}, {host_name}")
    return ssh_process.pid


def cpu_load_kube(vm_name: str, host_name: str, wait: bool) -> int:
    # Assume docker image exists
    ssh_process = create_ssh_process(vm_name, host_name)
    overwrite_file(ssh_process, 'pod.yaml', read_file('res/config/write_as_file/cpu_load/values.yaml'))
    ssh_process.stdin.write('kubectl create -f pod.yaml\n')
    # replicas set to 2 so 2 cores blocked. Only gets scheduled on worker node
    if wait:
        wait_for_kube_pods(ssh_process, ["block-cpu"], namespace="default")

    ssh_process.stdin.write('\n')
    return ssh_process.pid


def get_config_path(name: str):
    match name:
        case "baseline1":
            return "configuration/tkemenade/baseline/1.cfg"
        case "baseline4":
            return "configuration/tkemenade/baseline/4.cfg"
        case "baseline8":
            return "configuration/tkemenade/baseline/8.cfg"
        case "baseline12":
            return "configuration/tkemenade/baseline/12.cfg"
        case "baseline16":
            return "configuration/tkemenade/baseline/16.cfg"
        case "baseline20":
            return "configuration/tkemenade/baseline/20.cfg"
        case "qemu":
            return "configuration/tkemenade/qemu.cfg"
        case "qemu_virtiofsd":
            return "configuration/tkemenade/qemu_virtiofsd.cfg"
        case "qemu_cpu100":
            return "configuration/tkemenade/qemu_virtiofsd.cfg"
        case "kube":
            return "configuration/tkemenade/qemu_kube.cfg"
        case "kube_cpu100":
            return "configuration/tkemenade/qemu_kube_virtiofsd.cfg"
        case "kube_prom":
            return "configuration/tkemenade/qemu_kube_observe.cfg"
        case "kube_sca":
            return "configuration/tkemenade/qemu_kube_observe_virtiofsd.cfg"
        case "kube_sca_sched":
            return "configuration/tkemenade/qemu_kube_observe_virtiofsd.cfg"
        case "kube_sca_dsb":
            return "configuration/tkemenade/qemu_kube_observe_virtiofsd.cfg"
        case "kube_sca_dsb_sched":
            return "configuration/tkemenade/qemu_kube_observe_virtiofsd.cfg"
        case "kube-scheduler":
            return "configuration/tkemenade/benchmark.cfg"
        case "esched":
            return "configuration/tkemenade/benchmark.cfg"
        case _:
            return "configuration/template.cfg"


def load_config_from_file(config_path: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(config_path)
    return config


def exec_setup(zipped_func: (Callable[[str, str], int], str, str)) -> [int]:
    packed_funcs, vm_name, host_name = zipped_func
    return [func(vm_name, host_name, additional_args) if additional_args is not None else func(vm_name, host_name) for func, additional_args in packed_funcs]


def setup_by_name(name: str, vm_names: [str], host_names: [str], args: argparse.Namespace) -> [int]:
    parallel_setup = False
    vm_count = len(vm_names)
    if (vm_count != len(host_names) or vm_count == 0):
        # Execute nothing, and go to default case.
        name = ""
    
    exec_list = [[] for _ in range(vm_count)]
    match name:
        case "baseline1" | "baseline4" | "baseline8" | "baseline12" | "baseline16" | "baseline20":
            for i in range(vm_count):
                exec_list[i] = [
                    (vm_setup_qemu, None),
                ]
        case "qemu":
            parallel_setup = True
            for i in range(vm_count):
                exec_list[i] = [
                    (vm_setup_qemu, None),
                ]
        case "qemu_virtiofsd":
            parallel_setup = True
            for i in range(vm_count):
                exec_list[i] = [
                    (vm_setup_qemu, None),
                    (vm_setup_virtiofs, None),
                ]
        case "qemu_cpu100":
            parallel_setup = True
            config = load_config_from_file(get_config_path("qemu_cpu100"))
            for i in range(vm_count):
                exec_list[i] = [
                    (vm_setup_qemu, None),
                    (vm_setup_virtiofs, None),
                    (cpu_load_no_kube, config["infrastructure"]["cloud_cores"]),
                ]
        case "kube":
            parallel_setup = True
            for i in range(vm_count):
                exec_list[i] = [
                    (vm_setup_qemu, None),
                ]
        case "kube_prom":
            parallel_setup = True
            for i in range(vm_count):
                exec_list[i] = [
                    (vm_setup_qemu, None),
                ]
        case "kube_cpu100":
            parallel_setup = True
            for i in range(vm_count):
                exec_list[i] = [
                    (vm_setup_qemu, None),
                    (vm_setup_virtiofs, None),
                ]
            exec_list[0].append((cpu_load_kube, True))
        case "kube_sca":
            parallel_setup = True
            for i in range(vm_count):
                exec_list[i] = [
                    (vm_setup_qemu, None),
                    (vm_setup_virtiofs, None),
                ]
            # Scaphandre installation using helm happens only on controller node
            exec_list[0].append((vm_setup_scaphandre, True))
        case "kube_sca_sched":
            for i in range(vm_count):
                exec_list[i] = [
                    (vm_setup_qemu, None),
                    (vm_setup_virtiofs, None),
                ]
            # Scaphandre installation using helm happens only on controller node
            exec_list[0].append((vm_setup_scaphandre, True))
            # Scheduler installation using helm happens only on controller node
            exec_list[0].append((vm_setup_sched, True))
        case "kube_sca_dsb":
            for i in range(vm_count):
                exec_list[i] = [
                    (vm_setup_qemu, None),
                    (vm_setup_virtiofs, None),
                ]        
            # Scaphandre installation using helm happens only on controller node
            exec_list[0].append((vm_setup_scaphandre, True))
            # DSB installation using helm happens only on controller node
            exec_list[0].append((vm_setup_dsb, True))
        case "kube_sca_dsb_sched":
            for i in range(vm_count):
                exec_list[i] = [
                    (vm_setup_qemu, None),
                    (vm_setup_virtiofs, None),
                ]
            # Scaphandre installation using helm happens only on controller node
            exec_list[0].append((vm_setup_scaphandre, True))
            # Scheduler installation using helm happens only on controller node
            exec_list[0].append((vm_setup_sched, True))
            # DSB installation using helm happens only on controller node
            exec_list[0].append((vm_setup_dsb, True))
        case "kube-scheduler":
            for i in range(vm_count):
                exec_list[i] = [
                    (vm_setup_qemu, None),
                    (vm_setup_virtiofs, None),
                ]
            # Scaphandre installation using helm happens only on controller node
            exec_list[0].append((vm_setup_scaphandre, True))
            # DSB installation using helm happens only on controller node
            exec_list[0].append((vm_setup_dsb, True))
            exec_list[0].append((vm_setup_wrk_from_dsb, None))
        case "esched":
            for i in range(vm_count):
                exec_list[i] = [
                    (vm_setup_qemu, None),
                    (vm_setup_virtiofs, None),
                ]
            # Scaphandre installation using helm happens only on controller node
            exec_list[0].append((vm_setup_scaphandre, True))
            # Scheduler installation using helm happens only on controller node
            exec_list[0].append((vm_setup_sched, True))
            # DSB installation using helm happens only on controller node
            exec_list[0].append((vm_setup_dsb, True))  # TODO turn on scheduler name for DSB
            exec_list[0].append((vm_setup_wrk_from_dsb, None))
        case _:
            print("Nothing to run")
            return []
    
    zipped_funcs = zip(exec_list, vm_names, host_names)

    pids = []

    res = []
    if (parallel_setup):
        # Perform startup with pool of same size as amount of VMs.
        with Pool(vm_count) as pool:
            res = pool.map(exec_setup, zipped_funcs)
    else:
        for zipped_func in zipped_funcs:
            res.append(exec_setup(zipped_func))

    for res_pids in res:
        for pid in res_pids:
            pids.append(pid)
    return pids



def start_wrk2(vm_name: str, host_name: str) -> int:
    print_with_time(f"Start wrk2 {vm_name}, {host_name}")
    ssh_process = create_ssh_process(vm_name, host_name)

    ssh_process.stdin.write("nohup kubectl port-forward svc/nginx-thrift 8080 > /dev/null 2>&1 &\n")

    sync_stdout_with_guid(ssh_process)

    # wrk command
    threads = 8
    connections = 64
    duration = 6000  # in seconds = 1 2/3 hour
    requests_per_sec = 2056
    # wrk -D exp -t 8 -c 64 -d 6000s -L -s ~/DeathStarBench/socialNetwork/wrk2/scripts/social-network/read-home-timeline.lua http://localhost:8080/wrk2-api/home-timeline/read -R 2056
    # ssh_process.stdin.write(f"wrk -D exp -t {threads} -c {connections} -d {duration}s -L -s ~/DeathStarBench/socialNetwork/wrk2/scripts/social-network/compose-post.lua http://localhost:8080/wrk2-api/post/compose -R {requests_per_sec}\n")
    ssh_process.stdin.write(f"wrk -D exp -t {threads} -c {connections} -d {duration}s -L -s ~/DeathStarBench/socialNetwork/wrk2/scripts/social-network/read-home-timeline.lua http://localhost:8080/wrk2-api/home-timeline/read -R {requests_per_sec}\n")

    ssh_process.stdin.write('\n')

    # wrk -D exp -t <num-threads> -c <num-conns> -d <duration> -L -s ~/DeathStarBench/socialNetwork/wrk2/scripts/social-network/mixed-workload.lua http://localhost:8080/wrk2-api/post/compose -R <reqs-per-sec>
    # wrk -D exp -t 2 -c 10 -d 10s -L -s ~/DeathStarBench/socialNetwork/wrk2/scripts/social-network/compose-post.lua http://localhost:8080/wrk2-api/post/compose -R 100
    
    return ssh_process.pid


def get_running_pods(ssh_process):
    sync_stdout_with_guid(ssh_process)
    pods = []
    ssh_process.stdin.write("kubectl get pod --field-selector=status.phase==Running\n")
    ssh_process.stdin.write("echo \"END OF OUT\"\n")
    while True:
        line = ssh_process.stdout.readline()
        if "Running" in line:
            pods.append(line.split()[0])
            continue
        if "END OF OUT" in line and "echo" not in line :
            break
    return pods


def kill_predefined_pod_randomly(vm_name: str, host_name: str, interval: int):
    pods = [
        "compose-post-service", 
        "home-timeline-redis", 
        "home-timeline-service", 
        "jaeger", 
        # "media-frontend",  # Exlcude slow starting service from kill
        "media-memcached", 
        "media-mongodb", 
        "media-service", 
        # "nginx-thrift",  # Exlcude slow starting service from kill
        "post-storage-memcached", 
        "post-storage-mongodb", 
        "post-storage-service", 
        "social-graph-mongodb", 
        "social-graph-redis", 
        "social-graph-service", 
        "text-service", 
        "unique-id-service", 
        "url-shorten-memcached", 
        "url-shorten-mongodb", 
        "url-shorten-service", 
        "user-memcached", 
        "user-mention-service", 
        "user-mongodb", 
        "user-service", 
        "user-timeline-mongodb", 
        "user-timeline-redis", 
        "user-timeline-service"
    ]
    random.seed(1)
    ssh_process = create_ssh_process(vm_name, host_name)
    while True:
        time.sleep(interval)
        to_kill = []
        running_pods = get_running_pods(ssh_process)
        running_pods.sort()
        it = 0
        while it < 3:
            idx = random.randrange(len(running_pods))
            pod_to_kill = running_pods[idx]
            found = False
            for allowed_pod in pods:
                if allowed_pod in pod_to_kill:
                    found = True
                    to_kill.append(pod_to_kill) 
            if found:
                it += 1
        for pod_to_kill in to_kill:
            ssh_process.stdin.write(f'kubectl delete pod {pod_to_kill}\n')
            print_with_time(f'KILL INTERVAL: killed {pod_to_kill}')
            

def run_benchmark(parser_obj: argparse.ArgumentParser, args: argparse.Namespace):
    if (False):
        destroy_vm(f'cloud_controller_tkemenade')
        for i in range(20):
            destroy_vm(f'cloud{i}_tkemenade')
        return

    infra_already_running = True
    benchmark_on = True
    
    for experiment_name in args.experiment_names:
        print_with_time(f'Start experiment {experiment_name}')

        config_path = get_config_path(experiment_name)

        os.makedirs(f'/home/tkemenade/continuum/res/{experiment_name}', exist_ok=True)
        prev_runs = os.listdir(f'/home/tkemenade/continuum/res/{experiment_name}')
        
        for i in range(args.runs):
            file_identifier = f"{i}_{args.measure_interval}"

            already_ran = False
            for prev_run in prev_runs:
                if file_identifier in prev_run:
                    already_ran = True
            if already_ran:
                print_with_time(f"  run {file_identifier} skipped")
                continue
            print_with_time(f"  run {file_identifier} started")

            run_name = f'{experiment_name}/{file_identifier}'

            print_with_time('\tStart Continuum')
            start_continuum = time.time()
            if not infra_already_running:
                run_continuum(config_path)
            end_continuum = time.time()
            print_with_time('\tFinished Continuum')

            # Time for Continuum to finish.
            time.sleep(3)

            log_filename = get_last_log_filename()

            vm_names, host_names = get_vms_from_log(log_filename)

            for vm_name in vm_names:
                os.makedirs('/var/lib/libvirt/scaphandre/' + vm_name + '/intel-rapl:0', exist_ok=True)
            
            print_with_time('\tStart Scaphandre')
            start_scaphandre = time.time()
            pid = -1
            if (benchmark_on):
                pid = run_scaphandre()
            end_scaphandre = time.time()
            print_with_time('\tStarted Scaphandre')
            
            # Time for Scaphandre to finish
            time.sleep(1)

            print_with_time('\tStart setup')
            start_setup = time.time()
            pids = []
            pids = setup_by_name(experiment_name, vm_names, host_names, args)
            end_setup = time.time()
            print_with_time('\tFinished setup')
            
            # Time for setup to finish
            time.sleep(1)
            pids.append(start_wrk2(vm_names[0], host_names[0]))
            # input("ENTER TO CONTINUE TO MEASURE")
            kill_proc = multiprocessing.Process(target=kill_predefined_pod_randomly, args=(vm_names[0], host_names[0], 60))
            # kill_predefined_pod_randomly(vm_names[0], host_names[0], 60)
            kill_proc.start()
            print_with_time(f'\tStart measurement {run_name} with {arguments.measure_interval} iterations with vms: {", ".join(vm_names)}')

            start_resource_usage_sync = time.time()
            if (benchmark_on):
                save_synced_resource_usage('/var/lib/libvirt/scaphandre/', vm_names, run_name, arguments.measure_interval)
            end_resource_usage_sync = time.time()

            kill_proc.terminate()

            if (benchmark_on):
                # Store some metrics about times and active processes.
                with open(f'/home/tkemenade/continuum/res/{run_name}_METADATA.txt', 'w') as meta_file:
                    meta_file.write(f'Continuum deployment time {end_continuum - start_continuum}\n')
                    meta_file.write(f'Stack setup time {end_setup - start_setup}\n')
                    meta_file.write(f'Scaphandre open process time {end_scaphandre - start_scaphandre}\n')
                    meta_file.write(f'Sync metrics time {end_resource_usage_sync - start_resource_usage_sync}\n')
                    meta_file.write(f'VMs active {get_vm_count()}\nVMs experiment {len(vm_names)}\n')

            # Scaphandre always killed to prevent unmanaged dangling Scaphandre thread.
            kill("Scaphandre", pid)
            # Cleanup setup that is still running.
            for pid in pids:
                print(f"Killing {pid}")
                kill("Setup process", pid)

            if (not benchmark_on):
                print_with_time("Next run in 30 seconds")
                time.sleep(30)

            # Cleanup VMs if keep_vm is not on.
            if (not args.keep_vms):
                for vm_name in vm_names:
                    destroy_vm(vm_name)
            
            print_with_time(f'\tFinished measurement {run_name} with {arguments.measure_interval} iterations with vms: {", ".join(vm_names)}')

            # Cooldown to prevent Scaphandre from crashing.
            time.sleep(3)
        print_with_time(f'Finished experiment {experiment_name}')


if __name__ == "__main__":
    parser_obj = init_argparse()
    arguments = parser_obj.parse_args()

    run_benchmark(parser_obj, arguments)
