import matplotlib.pyplot as plt
import numpy as np
import os.path


def read_vals_file(metadata_file, metrics_file, absolute=False):
    with open(metadata_file, 'r') as metadata:
        metadata_lines = metadata.readlines()
        scaph_offset = metadata_lines[2].split()[0] == "Scaphandre"
        benchmark_duration = float(metadata_lines[2 + scaph_offset].split()[-1])
        vms = int(metadata_lines[3 + scaph_offset].split()[-1])
        vms_experiment = int(metadata_lines[4 + scaph_offset].split()[-1])
    with open(metrics_file, 'r') as measurements:
        start_time, start_total_cpu = measurements.readline().split()
        prev_total_cpu = [int(start_total_cpu)] * vms_experiment
        prev_time = [float(start_time)] * vms_experiment
        
        names = {}
        vm_measurements = []
        

        prev_energy = []
        prev_usr_cpu = []
        prev_sys_cpu = []
        for i in range(vms_experiment):
            name, energy, usr_cpu, sys_cpu = measurements.readline().split()
            names[name] = i
            energy = int(energy)
            usr_cpu = int(usr_cpu)
            sys_cpu = int(sys_cpu)
            prev_energy.append(energy)
            prev_usr_cpu.append(usr_cpu)
            prev_sys_cpu.append(sys_cpu)
            
            vm_measurements.append(([0], [0], [0], [0], [0]))
        
        # Skip empty line
        measurements.readline()

        line = measurements.readline()
        while line != '' and line != '\n':
            curr_time, curr_total_cpu = line.split()
            curr_time = float(curr_time)
            curr_total_cpu = int(curr_total_cpu)
            measurement_line = measurements.readline()
            name, energy, usr_cpu, sys_cpu = measurement_line.split()
            curr_energy = int(energy)
            curr_usr_cpu = int(usr_cpu)
            curr_sys_cpu = int(sys_cpu)

            i = names[name]

            delta_time = curr_time - prev_time[i]
            if absolute:
                delta_total_cpu = curr_total_cpu
                delta_energy = curr_energy
                delta_usr_cpu = curr_usr_cpu
                delta_sys_cpu = curr_sys_cpu
            else:
                delta_total_cpu = curr_total_cpu - prev_total_cpu[i]
                delta_energy = curr_energy - prev_energy[i]
                delta_usr_cpu = curr_usr_cpu - prev_usr_cpu[i]
                delta_sys_cpu = curr_sys_cpu - prev_sys_cpu[i]
            
            if curr_energy - prev_energy[i] != 0:
                time_deltas, total_cpu_deltas, energy_deltas, usr_cpu_deltas, sys_cpu_deltas = vm_measurements[i]

                time_deltas.append(time_deltas[-1] + delta_time)
                total_cpu_deltas.append(delta_total_cpu)
                energy_deltas.append(delta_energy)
                usr_cpu_deltas.append(delta_usr_cpu + delta_sys_cpu)
                sys_cpu_deltas.append(delta_sys_cpu)

                prev_time[i] = curr_time
                prev_total_cpu[i] = curr_total_cpu
                prev_energy[i] = curr_energy
                prev_usr_cpu[i] = curr_usr_cpu
                prev_sys_cpu[i] = curr_sys_cpu
            
            measurements.readline()
            line = measurements.readline()
    
    return vm_measurements, benchmark_duration, vms, vms_experiment


def read_vals_folder(folder, mi, absolute=False):
    runs = []
    for i in range(6):
        metadata_file = f'{folder}{i}_{mi}_METADATA.txt'
        metrics_file = f'{folder}{i}_{mi}_metrics.txt'
        if os.path.isfile(metadata_file) and os.path.isfile(metrics_file):
            runs.append(read_vals_file(metadata_file, metrics_file, absolute))
    return runs


def plot_power_cpu(vm_measurements, title):
    # CPU vs Energy
    time_deltas, total_cpu_deltas, energy_deltas, usr_cpu_deltas, sys_cpu_deltas = vm_measurements[0]

    print(len(time_deltas))

    fig, ax1 = plt.subplots()

    plt.title(title)

    offset = 25

    color = 'tab:red'
    ax1.set_xlabel('time (s)')
    ax1.set_ylabel('power usage', color=color)
    ax1.plot(time_deltas[offset:], energy_deltas[offset:], color=color)
    ax1.tick_params(axis='y', labelcolor=color)

    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis

    color = 'tab:blue'
    ax2.set_ylabel('cpu', color=color)  # we already handled the x-label with ax1
    ax2.plot(time_deltas[offset:], usr_cpu_deltas[offset:], color=color)
    # ax2.plot(time_deltas, sys_cpu_deltas, color=color)
    ax2.tick_params(axis='y', labelcolor=color)

    fig.tight_layout()  # otherwise the right y-label is slightly clipped

    plt.show()


def plot(vm_measurements, title):
    time_deltas, total_cpu_deltas, energy_deltas, usr_cpu_deltas, sys_cpu_deltas = vm_measurements[0]

    plot_power_cpu(vm_measurements, title)

    data = total_cpu_deltas[5:-5]

    print(len(data))

    fig = plt.figure(figsize =(10, 7))
    plt.title(title)
 
    # Creating plot
    plt.boxplot(data)
    
    # show plot
    plt.show()


def plot_all(run_list, title):
    data = []
    for measurements, _, _, vms_in_experiment in run_list:
        data.extend(measurements[0][2][5:-5])
    
    print(len(data))

    fig = plt.figure(figsize =(10, 7))
    plt.title(title)
 
    # Creating plot
    plt.boxplot(data)
    
    # show plot
    plt.show()


def fill_plot(ax1, title, data_energy, data_cpu):
    ax1_label = "energy"
    ax2_label = "cpu"

    energy_color = 'tab:red'
    cpu_color = 'tab:blue'

    ax1.set_title(title)

    ax1.boxplot(data_energy, positions=[1])
    ax1.set_ylabel(ax1_label, color=energy_color)
    ax1.ticklabel_format(axis='y', style='sci', scilimits=(6, 6))
    ax1.tick_params(axis='y', labelcolor=energy_color)

    ax2 = ax1.twinx()

    ax2.boxplot(data_cpu, positions=[2])
    ax2.set_ylabel(ax2_label, color=cpu_color)
    ax2.ticklabel_format(axis='y', style='sci', scilimits=(3, 3))
    ax2.tick_params(axis='y', labelcolor=cpu_color)

    ax2.set_xticklabels([ax1_label, ax2_label])


def plot_all_different_runs(run_lists, title, baseline=True):
    data = []
    for sub_title, run_list in run_lists:
        sub_data_energy = []
        sub_data_cpu = []
        for measurements, _, _, vms_in_experiment in run_list:
            if baseline:
                if 'kube' in sub_title:
                    sub_data_energy.extend(measurements[1][2][5:-5])
                    sub_data_cpu.extend(measurements[1][1][5:-5])
                else:
                    sub_data_energy.extend(measurements[0][2][5:-5])
                    sub_data_cpu.extend(measurements[0][1][5:-5])
            else:
                for measurement in measurements:
                    sub_data_energy.extend(measurement[2])
                    sub_data_cpu.extend(measurement[1])
        data.append((sub_title, sub_data_energy, sub_data_cpu))

    titles = [data_row[0] for data_row in data]
    energy_data = [data_row[1] for data_row in data]
    cpu_data = [data_row[2] for data_row in data]

    positions = [i + 1 for i in range(len(data))]
    energy_positions = [position - .25 for position in positions]
    cpu_positions = [position + .25 for position in positions]

    energy_color = 'tab:red'
    cpu_color = 'tab:blue'

    fig, ax1 = plt.subplots()

    energy_boxplot = ax1.boxplot(energy_data, positions=energy_positions, notch=False, patch_artist=True,
                             boxprops=dict(facecolor=energy_color, color=energy_color),
                             capprops=dict(color=energy_color),
                             whiskerprops=dict(color=energy_color),
                             flierprops=dict(color=energy_color, markeredgecolor=energy_color),
                             medianprops=dict(color='black'),
                             )
    ax1.set_ylabel('energy', color=energy_color)
    ax1.ticklabel_format(axis='y', style='sci', scilimits=(6, 6))
    ax1.tick_params(axis='y', labelcolor=energy_color)

    plt.xticks(rotation=60)

    ax2 = ax1.twinx()

    cpu_boxplot = ax2.boxplot(cpu_data, positions=cpu_positions, notch=False, patch_artist=True,
                             boxprops=dict(facecolor=cpu_color, color=cpu_color),
                             capprops=dict(color=cpu_color),
                             whiskerprops=dict(color=cpu_color),
                             flierprops=dict(color=cpu_color, markeredgecolor=cpu_color),
                             medianprops=dict(color='black'),
                             )
    ax2.set_ylabel('cpu', color=cpu_color)
    ax2.ticklabel_format(axis='y', style='sci', scilimits=(3, 3))
    ax2.tick_params(axis='y', labelcolor=cpu_color)

    plt.xticks(positions, titles)
    plt.tight_layout()
    plt.show()


def combine_reportings(times, ref):
    if len(times) < 2:
        return []

    data = []
    last_time = times[0]
    last_ref = ref[0]
    for i in range(1, len(times)):
        if last_ref != ref[i]:
            time_diff = times[i] - last_time
            data.append(time_diff)
            last_time = times[i]
            last_ref = ref[i]
    # Discard first reading as it is affected by start time of benchmark compared to start time of scaphandre
    return data[1:]


def plot_baseline_nodes(run_lists):
    data = []
    for run_list in run_lists:
        sub_data_time_deltas = []
        validate_deltas = []
        vm_count = 0.0
        for measurements, _, _, vms_in_experiment in run_list:
            vm_count += vms_in_experiment
            for measurement in measurements:
                reportings = combine_reportings(measurement[0], measurement[2])
                sub_data_time_deltas.extend(reportings)
                validate_deltas.append(reportings)
        vm_count /= len(run_list)
        print("VM count: ", vm_count)
        data.append((int(vm_count), sub_data_time_deltas))

    boxplot_vm_counts = []
    boxplot_data = []
    for vm_count, reporting_times in data:
        boxplot_vm_counts.append(vm_count)
        boxplot_data.append(reporting_times)

    fig = plt.figure(figsize=(10, 7))
    ax = plt.gca()
    plt.title("Reporting times per node")
    ax.set_ylabel("Reporting time (s)")
    ax.set_xlabel("VM count")

    # Creating plot
    plt.boxplot(boxplot_data, labels=boxplot_vm_counts)

    # show plot
    plt.show()


def get_ratios(time_deltas, cpu_deltas, energy_deltas):
    cpu_res = []
    energy_res = []
    cpu_average = sum(cpu_deltas) / len(cpu_deltas)
    energy_average = sum(energy_deltas) / len(energy_deltas)
    for i in range(1, len(time_deltas)):
        cpu_ratio = cpu_deltas[i] / cpu_average
        energy_ratio = energy_deltas[i] / energy_average
        cpu_res.append(cpu_ratio)
        energy_res.append(energy_ratio)
    return cpu_res, energy_res


def plot_under_load_energy_vs_cpu(run_list, title):
    data_cpu = []
    data_energy = []
    for measurements, _, _, vms_in_experiment in run_list:
        for measurement in measurements:
            cpu_ratios, energy_ratios = get_ratios(measurement[0], measurement[1], measurement[2])
            data_cpu.extend(cpu_ratios)
            data_energy.extend(energy_ratios)


    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111)
    plt.title(title)

    # Creating plot
    ax.boxplot([data_energy, data_cpu], labels=["energy", "cpu"])
    ax.set_ylabel("Ratio between measurements")

    # show plot
    plt.show()


def filter_extremes(measurements):
    time_deltas, total_cpu_deltas, energy_deltas, usr_cpu_deltas, sys_cpu_deltas = ([], [], [], [], [])
    for i in range(len(measurements[0])):
        time_delta = measurements[0][i]
        total_cpu_delta = measurements[1][i]
        energy_delta = measurements[2][i]
        usr_cpu_delta = measurements[3][i]
        sys_cpu_delta = measurements[4][i]
        if total_cpu_delta > 100:
            continue
        time_deltas.append(time_delta)
        total_cpu_deltas.append(total_cpu_delta)
        energy_deltas.append(energy_delta)
        usr_cpu_deltas.append(usr_cpu_delta)
        sys_cpu_deltas.append(sys_cpu_delta)

    return time_deltas, total_cpu_deltas, energy_deltas, usr_cpu_deltas, sys_cpu_deltas


def normalize_time(measurements):
    time_deltas, total_cpu_deltas, energy_deltas, usr_cpu_deltas, sys_cpu_deltas = ([], [], [], [], [])
    for i in range(len(measurements[0])):
        time_delta = measurements[0][i]
        if time_delta == 0:
            time_delta = 1
        total_cpu_delta = measurements[1][i] / time_delta
        energy_delta = measurements[2][i] / time_delta
        usr_cpu_delta = measurements[3][i] / time_delta
        sys_cpu_delta = measurements[4][i] / time_delta

        time_deltas.append(i)
        total_cpu_deltas.append(total_cpu_delta)
        energy_deltas.append(energy_delta)
        usr_cpu_deltas.append(usr_cpu_delta)
        sys_cpu_deltas.append(sys_cpu_delta)

    return time_deltas, total_cpu_deltas, energy_deltas, usr_cpu_deltas, sys_cpu_deltas


if __name__ == '__main__':
    FOLDER_QEMU = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/qemu/'
    FOLDER_VIRTIOFSD = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/qemu_virtiofsd/'
    FOLDER_CPU100 = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/qemu_cpu100/'
    FOLDER_KUBE = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/kube/'
    FOLDER_KUBE100 = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/kube_cpu100/'
    FOLDER_PROM = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/kube_prom/'
    FOLDER_SCA = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/kube_sca/'
    FOLDER_DSB = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/kube_sca_dsb/'
    FOLDER_SCHED = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/kube_sca_sched/'
    FOLDER_DSB_SCHED = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/kube_sca_dsb_sched/'

    FOLDER_BASELINE1 = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/baseline1/'
    FOLDER_BASELINE4 = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/baseline4/'
    FOLDER_BASELINE8 = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/baseline8/'
    FOLDER_BASELINE12 = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/baseline12/'
    FOLDER_BASELINE16 = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/baseline16/'
    FOLDER_BASELINE20 = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/baseline20/'

    FOLDER_KUBE_SCHED = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/kube-scheduler/'
    FOLDER_ESCHED = '/home/tim/Documents/Projects/kube-power/continuum_offline_workbench/res/esched/'

    res_qemu = read_vals_folder(FOLDER_QEMU, 600)
    res_virtiofsd = read_vals_folder(FOLDER_VIRTIOFSD, 600)
    res_cpu100 = read_vals_folder(FOLDER_CPU100, 600)
    res_kube = read_vals_folder(FOLDER_KUBE, 600)
    res_kube100 = read_vals_folder(FOLDER_KUBE100, 600)
    res_prom = read_vals_folder(FOLDER_PROM, 600)
    res_sca = read_vals_folder(FOLDER_SCA, 600)
    res_dsb = read_vals_folder(FOLDER_DSB, 600)
    res_sched = read_vals_folder(FOLDER_SCHED, 600)
    res_dsb_sched = read_vals_folder(FOLDER_DSB_SCHED, 600)

    res_baseline1 = read_vals_folder(FOLDER_BASELINE1, 600, absolute=True)
    res_baseline4 = read_vals_folder(FOLDER_BASELINE4, 600, absolute=True)
    res_baseline8 = read_vals_folder(FOLDER_BASELINE8, 600, absolute=True)
    res_baseline12 = read_vals_folder(FOLDER_BASELINE12, 600, absolute=True)
    res_baseline20 = read_vals_folder(FOLDER_BASELINE20, 600, absolute=True)
    res_baseline16 = read_vals_folder(FOLDER_BASELINE16, 600, absolute=True)

    res_kube_sched = read_vals_folder(FOLDER_KUBE_SCHED, 3600)
    res_esched = read_vals_folder(FOLDER_ESCHED, 3600)

    all_idle_res_packed = [
        ("qemu", res_qemu),
        ("qemu_virtiofsd", res_virtiofsd),
        ("kube", res_kube),
        ("kube_prom", res_prom),
        ("kube_sca", res_sca),
        ("kube_dsb", res_dsb),
        ("kube_sched", res_sched),
        ("kube_dsb_sched", res_dsb_sched),
    ]

    all_cpu_res_packed = [
        ("qemu_cpu100", res_cpu100),
        ("kube_cpu100", res_kube100),
    ]

    # plot_all_different_runs(all_idle_res_packed, "Cumulative baseline overhead")
    # plot_all_different_runs(all_cpu_res_packed, "CPU stress test")

    # plot_baseline_nodes([
    #     res_baseline1,
    #     res_baseline4,
    #     res_baseline8,
    #     res_baseline12,
    #     res_baseline16,
    #     res_baseline20
    # ])

    # plot_under_load_energy_vs_cpu(res_cpu100, "Ratio between measurements qemu_cpu100")
    # plot_under_load_energy_vs_cpu(res_kube100, "Ratio between measurements kube_cpu100")

    scheduler_runs_packed = [
        ("kube-scheduler", res_kube_sched),
        ("Escheduler", res_esched),
    ]

    plot_all_different_runs(scheduler_runs_packed, "kube-scheduler vs Escheduler", baseline=False)

    # plot_all(res_kube_sched, 'kube-scheduler')
    # plot_all(res_esched, 'Escheduler')

    # res_qemu_long = read_vals_file(f'{FOLDER_QEMU}0_3060_METADATA.txt', f'{FOLDER_QEMU}0_3060_metrics.txt')
    #
    # plot(res_qemu_long[0], 'qemu long')
    #
    # res_qemu_long[0][0] = filter_extremes(res_qemu_long[0][0])
    # plot(res_qemu_long[0], 'qemu long')
    #
    # res_qemu_long[0][0] = normalize_time(filter_extremes(res_qemu_long[0][0]))
    # plot(res_qemu_long[0], 'qemu long')

    # plot(res_qemu[0][0], 'qemu')
    # plot(res_virtiofsd[0][0], 'virtiofsd')
    # plot(res_cpu100[0][0], 'cpu100')
    # plot(res_kube[0][0], 'kube')
    # plot(res_prom[0][0], 'prom')
    
    # plot_all(res_qemu, 'qemu')
    # plot_all(res_virtiofsd, 'virtiofsd')
    # plot_all(res_cpu100, 'cpu100')
    # plot_all(res_kube, 'kube')
    # plot_all(res_prom, 'prom')

    # plot_power_cpu(combine_res(res_qemu), "qemu")
    # plot_power_cpu(combine_res(res_virtiofsd), "virtiofsd")
    # plot_power_cpu(combine_res(res_cpu100), "cpu100")
    # plot_power_cpu(combine_res(res_kube), "kube")
    # plot_power_cpu(combine_res(res_prom), "prom")

    # plot_power_cpu((res_qemu[0][0]), "qemu")
    # plot_power_cpu((res_qemu[1][0]), "qemu")
    # plot_power_cpu((res_qemu[2][0]), "qemu")
    # plot_power_cpu((res_qemu[3][0]), "qemu")
    # plot_power_cpu((res_qemu[4][0]), "qemu")

    # plot_power_cpu((res_virtiofsd[0][0]), "virtiofsd")
    # plot_power_cpu((res_virtiofsd[1][0]), "virtiofsd")
    # plot_power_cpu((res_virtiofsd[2][0]), "virtiofsd")
    # plot_power_cpu((res_virtiofsd[3][0]), "virtiofsd")
    # plot_power_cpu((res_virtiofsd[4][0]), "virtiofsd")

    # plot(res_qemu[0][0], 'qemu0')
    # plot(res_qemu[1][0], 'qemu1')
    # plot(res_qemu[2][0], 'qemu2')
    # plot(res_qemu[3][0], 'qemu3')
    # plot(res_qemu[4][0], 'qemu4')

    # res_qemu[0][0][0] = normalize_time(res_qemu[0][0][0])
    # res_qemu[1][0][0] = normalize_time(res_qemu[1][0][0])
    # res_qemu[2][0][0] = normalize_time(res_qemu[2][0][0])
    # res_qemu[3][0][0] = normalize_time(res_qemu[3][0][0])
    # res_qemu[4][0][0] = normalize_time(res_qemu[4][0][0])
    # plot((res_qemu[0][0]), 'qemu0 norm')
    # plot((res_qemu[1][0]), 'qemu1 norm')
    # plot((res_qemu[2][0]), 'qemu2 norm')
    # plot((res_qemu[3][0]), 'qemu3 norm')
    # plot((res_qemu[4][0]), 'qemu4 norm')

    # plot(res_virtiofsd[0][0], 'virtiofsd0')
    # plot(res_virtiofsd[1][0], 'virtiofsd1')
    # plot(res_virtiofsd[2][0], 'virtiofsd2')
    # plot(res_virtiofsd[3][0], 'virtiofsd3')
    # plot(res_virtiofsd[4][0], 'virtiofsd4')

    # plot(res_cpu100[0][0], 'cpu100_0')
    # plot(res_cpu100[1][0], 'cpu100_1')
    # plot(res_cpu100[2][0], 'cpu100_2')
    # plot(res_cpu100[3][0], 'cpu100_3')
    # plot(res_cpu100[4][0], 'cpu100_4')

    # plot(res_kube[0][0], 'kube0')
    # plot(res_kube[1][0], 'kube1')
    # plot(res_kube[2][0], 'kube2')
    # plot(res_kube[3][0], 'kube3')
    # plot(res_kube[4][0], 'kube4')

    # plot(res_prom[0][0], 'prom0')
    # plot(res_prom[1][0], 'prom1')
    # plot(res_prom[2][0], 'prom2')
    # plot(res_prom[3][0], 'prom3')
    # plot(res_prom[4][0], 'prom4')

