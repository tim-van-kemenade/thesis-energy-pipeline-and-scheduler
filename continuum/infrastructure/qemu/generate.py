"""\
Generate a QEMU configuration file
The file is generated from scratch instead of using an existing template file as
too many things can change depending on user input.
"""

import logging
import sys
import re


DOMAIN = """\
<domain type='kvm'>
    <name>%s</name>
    <memory>%i</memory>
%s
    <os>
        <type>hvm</type>
        <boot dev="hd"/>
    </os>
%s
    <features>
        <acpi/>
    </features>
    <vcpu placement="static">%i</vcpu>
    <cputune>
        <period>%i</period>
        <quota>%i</quota>
%s
    </cputune>
    <devices>
        <interface type='bridge'>
            <source bridge='%s'/>
            <model type='e1000'/>
        </interface>
        <disk type='file' device='disk'>
            <driver type='qcow2' cache='none'/>
            <source file='%s/.continuum/images/%s.qcow2'/>
            <target dev='vda' bus='virtio'/>
            <iotune>
                <read_bytes_sec>%i</read_bytes_sec>
                <write_bytes_sec>%i</write_bytes_sec>
                <read_bytes_sec_max>%i</read_bytes_sec_max>
                <write_bytes_sec_max>%i</write_bytes_sec_max>
            </iotune>
        </disk>
        <disk type='file' device='disk'>
            <source file='%s/.continuum/images/user_data_%s.img'/>
            <target dev='vdb' bus='virtio'/>
        </disk>
        <console type="pty">
           <target type="serial" port="1"/>
        </console>
%s
    </devices>
</domain>
"""

USER_DATA = """\
#cloud-config
hostname: %s
fqdn: %s
manage_etc_hosts: true
users:
  - name: %s
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: users, admin
    home: /home/%s
    shell: /bin/bash
    lock_passwd: false
    ssh-authorized-keys:
      - %s
ssh_pwauth: false
disable_root: false
chpasswd:
  list: |
     %s:password
  expire: False
write_files:
- path: /etc/cloud/cloud.cfg.d/99-custom-networking.cfg
  permissions: '0644'
  content: |
    network: {config: disabled}
- path: /etc/netplan/new-config.yaml
  permissions: '0644'
  content: |
    network:
      version: 2
      ethernets:
        %s:
          dhcp4: false
          addresses: [%s/16]
          gateway4: %s
          nameservers:
            addresses: [1.1.1.1, 8.8.8.8]
            search: []
runcmd:
 - rm /etc/netplan/50-cloud-init.yaml
 - netplan generate
 - netplan apply
 # additional commands for fast prototyping
 %s
# written to /var/log/cloud-init-output.log
final_message: "The system is finally up, after $UPTIME seconds"
"""


def memory_backing_config():
    """Memory backing config for the domain XML file.

    Returns:
        str: Memory backing domain config
    """
    return """\
    <memoryBacking>
        <source type='memfd'/>
        <access mode='shared'/>
    </memoryBacking>\
    """


def virtiofsd_config(domain_name):
    """virtiofsd Scaphandre mount config for the domain XML file.

    Args:
        domain_name (str): domain name under which Scaphandre metrics are stored
    
    Returns:
        str: virtiofsd Scaphandre mount domain config
    """
    return f"""\
        <filesystem type='mount' accessmode='passthrough'>
            <driver type='virtiofs'/>
            <source dir='/var/lib/libvirt/scaphandre/{domain_name}'/>
            <target dir='scaphandre'/>
        </filesystem>\
    """


def additional_commands(commands):
    """Format additional commands provided to USER_DATA.

    Args:
        commands (list): List of command line commands
    
    Returns:
        str: Valid string of additional commands to be appended to the end of USER_DATA
    """
    return ""  # "\n".join(["- " + command for command in commands])


def find_bridge(config, machine, bridge):
    """Check if bridge <bridge> is available on the system.

    Args:
        config (dict): Parsed configuration
        machine (Machine object): Object representing the physical machine we currently use
        bridge (str): Bridge name to check

    Returns:
        int: Bool representing if we found the bridge on this machine
    """
    output, error = machine.process(
        config, "brctl show | grep '^%s' | wc -l" % (bridge), shell=True
    )[0]
    if error != [] or output == []:
        logging.error("ERROR: Could not find a network bridge")
        sys.exit()

    return int(output[0].rstrip())


def start(config, machines):
    """Create QEMU config files for each machine

    Args:
        config (dict): Parsed configuration
        machines (list(Machine object)): List of machine objects representing physical machines
    """
    logging.info("Start writing QEMU config files for cloud / edge")

    using_kata = False
    if (
        "benchmark" in config
        and "runtime" in config["benchmark"]
        and "kata" in config["benchmark"]["runtime"]
    ):
        using_kata = True

    # Get the SSH public key
    with open("%s.pub" % (config["ssh_key"]), "r", encoding="utf-8") as f:
        ssh_key = f.read().rstrip()
        f.close()

    # --------------------------------------------------------------------------------------------
    # NOTE
    # If an error occurs in the following lines, please:
    # 1. Comment this part of the code between the two ---- lines out
    # 2. Set the "bridge_name" variable to the name of your bridge (e.g. br0, virbr0, etc.)
    # 3. Set the gateway variable to the IP of your gateway (e.g. 10.0.2.2, 192.168.122.1, etc)
    # --------------------------------------------------------------------------------------------
    # Find out what bridge to use
    bridge = find_bridge(config, machines[0], "br0")
    bridge_name = "br0"
    if bridge == 0:
        bridge = find_bridge(config, machines[0], "virbr0")
        bridge_name = "virbr0"
        if bridge == 0:
            logging.error("ERROR: Could not find a network bridge")
            sys.exit()

    # Get gateway address
    output, error = machines[0].process(
        config, "ip route | grep ' %s '" % (bridge_name), shell=True
    )[0]
    if error != [] or output == []:
        logging.error("ERROR: Could not find gateway address")
        sys.exit()

    gateway = 0
    pattern = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
    gatewaylists = [pattern.findall(line) for line in output]

    if bridge_name == "br0":
        # For br0, pick gateway of machine
        gateway = gatewaylists[0][0]
    else:
        # For virbr0
        for gatewaylist in gatewaylists:
            if len(gatewaylist) > 1:
                if gateway != 0:
                    logging.error("ERROR: Found multiple gateways")
                    sys.exit()

                gateway = gatewaylist[1].rstrip()
    # --------------------------------------------------------------------------------------------

    cc = config["infrastructure"]["cloud_cores"]
    ec = config["infrastructure"]["edge_cores"]
    pc = config["infrastructure"]["endpoint_cores"]

    period = 100000
    pinnings = []

    for machine in machines:
        # Counter for pinning vcpu to physical cpu
        start_core = 0

        # Clouds
        for ip, name in zip(
            machine.cloud_controller_ips + machine.cloud_ips,
            machine.cloud_controller_names + machine.cloud_names,
        ):
            with open(".tmp/domain_%s.xml" % (name), "w", encoding="utf-8") as f:
                memory = int(1048576 * config["infrastructure"]["cloud_memory"])

                if config["infrastructure"]["cpu_pin"]:
                    pinnings = [
                        '        <vcpupin vcpu="%i" cpuset="%i"/>' % (a, b)
                        for a, b in zip(range(cc), range(start_core, start_core + cc))
                    ]
                    start_core += cc
                # Include the running VMs, exclude base VMs
                if config["infrastructure"]["virtiofsd"] and name.startswith("cloud"):
                    f.write(
                        DOMAIN
                        % (
                            name,
                            memory,
                            memory_backing_config(),
                            "    <cpu mode='host-passthrough'/>" if using_kata else "",
                            cc,
                            period,
                            int(period * config["infrastructure"]["cloud_quota"]),
                            "\n".join(pinnings),
                            bridge_name,
                            config["infrastructure"]["base_path"],
                            name,
                            config["infrastructure"]["cloud_read_speed"],
                            config["infrastructure"]["cloud_write_speed"],
                            config["infrastructure"]["cloud_read_speed"],
                            config["infrastructure"]["cloud_write_speed"],
                            config["infrastructure"]["base_path"],
                            name,
                            virtiofsd_config(name),
                        )
                    )
                    f.close()

                    with open(".tmp/user_data_%s.yml" % (name), "w", encoding="utf-8") as f:
                        hostname = name.replace("_", "")
                        f.write(USER_DATA % (hostname, hostname, name, name, ssh_key, name, "ens3", ip, gateway, additional_commands(["sudo mkdir /var/scaphandre", "sudo mount -t virtiofs scaphandre /var/scaphandre"])))
                        f.close()
                else:
                    f.write(
                        DOMAIN
                        % (
                            name,
                            memory,
                            "",  # memory backing not included
                            "    <cpu mode='host-passthrough'/>" if using_kata else "",
                            cc,
                            period,
                            int(period * config["infrastructure"]["cloud_quota"]),
                            "\n".join(pinnings),
                            bridge_name,
                            config["infrastructure"]["base_path"],
                            name,
                            config["infrastructure"]["cloud_read_speed"],
                            config["infrastructure"]["cloud_write_speed"],
                            config["infrastructure"]["cloud_read_speed"],
                            config["infrastructure"]["cloud_write_speed"],
                            config["infrastructure"]["base_path"],
                            name,
                            "",  # virtiofsd filesystem mapping not included
                        )
                    )
                    f.close()

                    with open(".tmp/user_data_%s.yml" % (name), "w", encoding="utf-8") as f:
                        hostname = name.replace("_", "")
                        f.write(USER_DATA % (hostname, hostname, name, name, ssh_key, name, "ens2", ip, gateway, ""))
                        f.close()

        # Edges
        for ip, name in zip(machine.edge_ips, machine.edge_names):
            with open(".tmp/domain_%s.xml" % (name), "w", encoding="utf-8") as f:
                memory = int(1048576 * config["infrastructure"]["edge_memory"])

                if config["infrastructure"]["cpu_pin"]:
                    pinnings = [
                        '        <vcpupin vcpu="%i" cpuset="%i"/>' % (a, b)
                        for a, b in zip(range(ec), range(start_core, start_core + ec))
                    ]
                    start_core += ec

                f.write(
                    DOMAIN
                    % (
                        name,
                        memory,
                        "",  # memory backing not included
                        "    <cpu mode='host-passthrough'/>" if using_kata else "",
                        ec,
                        period,
                        int(period * config["infrastructure"]["edge_quota"]),
                        "\n".join(pinnings),
                        bridge_name,
                        config["infrastructure"]["base_path"],
                        name,
                        config["infrastructure"]["edge_read_speed"],
                        config["infrastructure"]["edge_write_speed"],
                        config["infrastructure"]["edge_read_speed"],
                        config["infrastructure"]["edge_write_speed"],
                        config["infrastructure"]["base_path"],
                        name,
                        "",  # virtiofsd filesystem mapping not included
                    )
                )
                f.close()

            with open(".tmp/user_data_%s.yml" % (name), "w", encoding="utf-8") as f:
                hostname = name.replace("_", "")
                f.write(USER_DATA % (hostname, hostname, name, name, ssh_key, name, "ens2", ip, gateway, ""))
                f.close()

        # Endpoints
        for ip, name in zip(machine.endpoint_ips, machine.endpoint_names):
            with open(".tmp/domain_%s.xml" % (name), "w", encoding="utf-8") as f:
                memory = int(1048576 * config["infrastructure"]["endpoint_memory"])

                if config["infrastructure"]["cpu_pin"]:
                    pinnings = [
                        '        <vcpupin vcpu="%i" cpuset="%i"/>' % (a, b)
                        for a, b in zip(range(pc), range(start_core, start_core + pc))
                    ]
                    start_core += pc

                f.write(
                    DOMAIN
                    % (
                        name,
                        memory,
                        "",  # memory backing not included
                        "    <cpu mode='host-passthrough'/>" if using_kata else "",
                        pc,
                        period,
                        int(period * config["infrastructure"]["endpoint_quota"]),
                        "\n".join(pinnings),
                        bridge_name,
                        config["infrastructure"]["base_path"],
                        name,
                        config["infrastructure"]["endpoint_read_speed"],
                        config["infrastructure"]["endpoint_write_speed"],
                        config["infrastructure"]["endpoint_read_speed"],
                        config["infrastructure"]["endpoint_write_speed"],
                        config["infrastructure"]["base_path"],
                        name,
                        "",  # virtiofsd filesystem mapping not included
                    )
                )
                f.close()

            with open(".tmp/user_data_%s.yml" % (name), "w", encoding="utf-8") as f:
                hostname = name.replace("_", "")
                f.write(USER_DATA % (hostname, hostname, name, name, ssh_key, name, "ens2", ip, gateway, ""))
                f.close()

        # Base image(s)
        for ip, name in zip(machine.base_ips, machine.base_names):
            with open(".tmp/domain_%s.xml" % (name), "w", encoding="utf-8") as f:
                f.write(
                    DOMAIN
                    % (
                        name,
                        1048576,
                        "",  # memory backing not included
                        "    <cpu mode='host-passthrough'/>" if using_kata else "",
                        1,
                        0,
                        0,
                        "",
                        bridge_name,
                        config["infrastructure"]["base_path"],
                        name,
                        0,
                        0,
                        0,
                        0,
                        config["infrastructure"]["base_path"],
                        name,
                        "",  # virtiofsd filesystem mapping not included
                    )
                )
                f.close()

            with open(".tmp/user_data_%s.yml" % (name), "w", encoding="utf-8") as f:
                hostname = name.replace("_", "")
                f.write(USER_DATA % (hostname, hostname, name, name, ssh_key, name, "ens2", ip, gateway, ""))
                f.close()
