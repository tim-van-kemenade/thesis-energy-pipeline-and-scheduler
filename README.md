This repository is a thesis submission and contains the following:
1. Escheduler: Located in the escheduler folder. Written in GoLang.
2. block_cpu: Located in the block_cpu folder. Written in Rust.
3. Automated experiments: Located in the continuum folder which also contains a
modified version of Continuum (https://github.com/atlarge-research/continuum).
    (a) Continuum fork: contains additional configurations in the configuration/tkemenade
folder, additional documentation (–enable-virtiofsd needs to be used when con-
figuring QEMU), adjusted code to enable virtiofsd, and adjusted code place the
mount to /var/lib/libvirt/scaphandre/{domain_name}.
    (b) Automated experiments main: energy_metrics.py performs the automated
experiments using Continuum to start the VMs and storing results in res and
storing additional configuration in res/config (res/config/write_as_file are files
used by the Python script to overwrite files in pulled git sources rather than
creating a new fork).
4. Graphing: Located in the root of the project, graphing.py, and uses the res folder
to pull results from and plot all uncommented plots.
5. Original results: Located in the res folder. We separated the original experiment
results in case anything is rerun to prevent confusion.