# Syscall Analysis Tool

This tool analyzes the support of system calls based on the [popularity of Debian packages](https://popcon.debian.org/) and the system call usage metrics. It calculates the weighted completeness of supported system calls, ranks unimplemented system calls by importance, and lists packages that depend on a specific syscall.

## Features

- **Analyze System Call Support**: Load and evaluate system calls implemented.
- **Filter by Popularity**: Rank packages using system calls based on Debian popularity metrics.
- **Weighted Completeness Calculation**: Calculate the weighted completeness of syscall support.
- **List Top Unimplemented System Calls**: Identify and rank unimplemented syscalls by their API importance.

### Arguments

| Argument               | Description                                                                                |
|------------------------|--------------------------------------------------------------------------------------------|
| `--type`                   | "dynamic" - Analyze against runtime data collected by Loupe, or "static" - Analyze against static data |
| `-i, --implement_syscalls` | Path to a file containing a list of implemented system calls (one per line).             |
| `-s, --stub_syscalls`      | Path to a file containing a list of stubbed system calls that can be ignored if missing. |
| `-t, --top`                | Limit the output to the top N items. Default is 20.                                     |
| `-c, --syscall`            | Specify a syscall name to list packages using it.                                       |


### Example Commands

```bash
# Analyze Gramine main branch syscalls with Loupe dynamic data
python syscall_analysis.py --type dynamic 

# Analyze Gramine main branch syscalls with list of "don't care" stubbed syscalls against static data
python syscall_analysis.py -s Gramine-stub.syscalls

# List packages that use a specific syscall
python syscall_analysis.py -c <syscall>
```

### Sample Output

#### Example output for completeness analysis and top unimplemented syscalls

##### Analyze Gramine main branch syscalls with Loupe data:
```
% python syscall_analysis.py --type dynamic 
Analyzing Gramine from https://raw.githubusercontent.com/gramineproject/gramine/refs/heads/master/libos/src/arch/x86_64/libos_table.c ...

Implemented/Stubbed syscalls: 177/0
Weighted Completeness = 65.854 %

Top 20 not yet supported syscalls ordered by (API Importance)
mremap             used in 11 wrks, works faked in 8 wrks
rseq               used in  9 wrks, works faked in 1 wrks
prctl              used in  7 wrks, works faked in 1 wrks
getrusage          used in  6 wrks, works faked in 2 wrks
shmat              used in  5 wrks, works faked in 2 wrks
statx              used in  5 wrks, works faked in 5 wrks
...
```

##### Example output for listing wrks/packages that use a specific syscall
```
% python syscall_analysis.py -c mremap --type dynamic                 
Number of application requiring 'mremap': 11
Faked works in wrks:
 ['rust-benchmark-rust-test', 'sqlite-benchmark-sqlite', 'sqlite-suite', 'memcached-suite', 'webassembly-benchmark-webassembly-test', 'ocrmypdf-benchmark-ocrmypdf-test', 'django-suite', 'ruby-suite']
Required by wrks:
 ['golang-pie-example-benchmark-golang-test', 'python-suite', 'gimp-benchmark-gimp-test']
```

##### Analyze Gramine main branch syscalls with list of stubbed syscalls against static data
```
% python syscall_analysis.py -s Gramine-stub.syscalls 
Analyzing Gramine from https://raw.githubusercontent.com/gramineproject/gramine/refs/heads/master/libos/src/arch/x86_64/libos_table.c ...

Implemented/Stubbed syscalls: 177/10
Weighted Completeness = 33.829 %

Top 20 not yet supported syscalls ordered by (API Importance)
link               used in 2313 packages (0.058335094442070856)
symlink            used in 1807 packages (0.04878473281819029)
utimes             used in 1475 packages (0.04234399477959372)
...
```

##### Analyze Freebsd with list of its supported system calls:
```
% python3 syscall_analysis.py  -i Freebsd.syscalls
Analyzing against file Freebsd.syscalls ...

Implemented/Stubbed syscalls: 295/0
Weighted Completeness = 65.667 %

Top 20 not yet supported syscalls ordered by (API Importance)
getxattr           used in 1379 packages (0.041738638354196334)
inotify_add_watch  used in 1948 packages (0.038895716714951956)
setxattr           used in 1357 packages (0.03705006792165233)
...
```

