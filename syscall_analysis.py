import re
import argparse
import json
import csv
from collections import defaultdict
import urllib.request
import get_package_popularity

LIBOS_URL = "https://raw.githubusercontent.com/gramineproject/gramine/refs/heads/master/libos/src/arch/x86_64/libos_table.c"
LIBOS_SYSCALL_PATTERN = r"\(libos_syscall_t\)libos_syscall_"

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--implement_syscalls', type=str, help="file containing a list of implemented system calls, each on a new line")
    parser.add_argument('-s', '--stub_syscalls', type=str, help="file containing a list of stubbed system calls which work fine as stubbed")
    parser.add_argument('-t', '--top', type=int, help="list only the top N items", default=20)
    parser.add_argument('-c', '--syscall', action='store', help="list the packages using the syscall")
    parser.add_argument('-src', '--source', action='store', default='inst', help=argparse.SUPPRESS)
    parser.add_argument('-m', '--maintainers', nargs='*', help=argparse.SUPPRESS)
    return parser.parse_args()

def load_implemented_syscalls(implement_syscalls):
    """Load supported syscalls from the Gramine syscall table file."""
    supported_syscalls = []

    if not implement_syscalls:
        print(f'Analyzing Gramine from {LIBOS_URL} ...')
        data = urllib.request.urlopen(LIBOS_URL)
        for line in data:
            match = re.search(LIBOS_SYSCALL_PATTERN + r'(.+)', line.decode('utf-8'))
            if match:
                supported_syscalls.append(match.group(1).replace(',', '').strip())
    else:
        print(f'Analyzing against file {implement_syscalls} ...')
        with open(implement_syscalls, 'r') as f:
            supported_syscalls = [line.strip() for line in f if line.strip()]
    if not supported_syscalls:
        print("No supported syscalls found, check 'libos_table.c' path.")
        exit()
    return supported_syscalls

def load_excluded_syscalls(filepath):
    """Load syscalls to be excluded from a file."""
    with open(filepath, 'r') as file:
        return [line.strip() for line in file]

def load_api_usage(filename='data/api_usage.json'):
    """Load API usage data from JSON."""
    with open(filename) as f:
        return json.load(f)

def load_popularity_data(source, maintainers=None):
    """Load package popularity data based on source."""
    if source != 'ubuntu_inst':
        return load_debian_popularity_data(source, maintainers)
    else:
        inst_data, total_inst = load_ubuntu_popularity_data()
        return inst_data, total_inst, total_inst

def load_debian_popularity_data(source, maintainers):
    """Load Debian popularity data and filter by maintainers."""
    popcon_packages = get_package_popularity.get_package_popularity(source)
    inst_data, effective_total_inst = {}, 0
    for item in popcon_packages:
        if item['package_name'] == 'Total':
            total_inst = int(item[source])
        else:
            if not maintainers or item['maintainer'] in maintainers:
                inst_data[item['package_name']] = int(item[source])
                effective_total_inst += item[source]
    return inst_data, total_inst, effective_total_inst

def load_ubuntu_popularity_data(filename='data/ubuntu_package_popularity.csv'):
    """Load Ubuntu popularity data from a CSV file."""
    inst_data = {}
    with open(filename) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['package_name'] == 'Total':
                total_inst = int(row['inst'])
            else:
                inst_data[row['package_name']] = int(row['inst'])
    return inst_data, total_inst

def filter_packages_by_syscall(syscall, packages_in_api_usage, source, top_number, maintainers=None):
    """Filter and print packages requiring a specific syscall."""
    popcon_packages = get_package_popularity.get_package_popularity(source)
    num_packages_require_the_syscall = 0
    for item in popcon_packages:
        pkg = item['package_name']
        if pkg in packages_in_api_usage:
            if (not maintainers or item['maintainer'] in maintainers) and \
               syscall in packages_in_api_usage[pkg]['system call']:
                if num_packages_require_the_syscall < top_number:
                    print(f'{item["rank"]}. {pkg}')
                num_packages_require_the_syscall += 1
    print(f'Number of packages requiring {syscall}: {num_packages_require_the_syscall}')

def calculate_weighted_completeness(supported_syscalls, packages_in_api_usage, inst_data, total_pkg_expect, pkg_prob_dict):
    """Calculate the weighted completeness of syscall support."""
    total_syscalls = []
    not_supported_syscalls = []
    supported_packages = []
    supported_pkg_expect = 0.0

    for pkg in packages_in_api_usage:
        if pkg not in inst_data:
            continue
        missing_apis = []
        for api_name in packages_in_api_usage[pkg]['system call']:
            if api_name not in total_syscalls:
                total_syscalls.append(api_name)
            if api_name not in supported_syscalls:
                missing_apis.append(api_name)
                if api_name not in not_supported_syscalls:
                    not_supported_syscalls.append(api_name)
        if len(missing_apis) == 0:
            supported_pkg_expect += pkg_prob_dict[pkg]
            supported_packages.append(pkg)

    weighted_completeness = 100.0 * supported_pkg_expect / total_pkg_expect
    return weighted_completeness, total_syscalls, not_supported_syscalls, supported_packages

def calculate_curve(ordered_syscalls, top_number, supported_syscalls, api_required_package):
    """Calculate and print the curve of syscall importance."""
    top_syscalls = []
    not_supported_count = 0
    print(f'\nTop {top_number} not yet supported syscalls ordered by (API Importance)')
    for s in ordered_syscalls:
        top_syscalls.append(s[0])
        if s[0] not in supported_syscalls:
            if not_supported_count < top_number:
                not_supported_count += 1
                #print(f'{s[0]} needed by {len(api_required_package[s[0]])} packages (1 - {s[1]})')
                print("{:<18} used in {:>4} packages ({})".format(s[0], len(api_required_package[s[0]]), s[1]))
            else:
                break

def main():
    args = parse_arguments()
    
    supported_syscalls = load_implemented_syscalls(args.implement_syscalls)
    num_implemented_syscalls = len(supported_syscalls)
    num_stubbed_syscalls = 0
    if args.stub_syscalls:
        supported_syscalls.extend(load_excluded_syscalls(args.stub_syscalls))
        num_stubbed_syscalls = len(supported_syscalls) - num_implemented_syscalls

    packages_in_api_usage = load_api_usage()
    inst_data, total_inst, effective_total_inst = load_popularity_data(args.source, args.maintainers)

    api_required_package = defaultdict(list)
    pkg_prob_dict, total_pkg_expect = {}, 0.0
    for pkg in packages_in_api_usage:
        if pkg in inst_data:
            pkg_prob = inst_data[pkg] / total_inst
            pkg_prob_dict[pkg] = pkg_prob
            total_pkg_expect += pkg_prob
            for api_name in packages_in_api_usage[pkg]['system call']:
                api_required_package[api_name].append(pkg)

    if args.syscall:
        filter_packages_by_syscall(args.syscall, packages_in_api_usage, args.source, args.top, args.maintainers)
        return

    wc, total_syscalls, not_supported_syscalls, _ = calculate_weighted_completeness(
        supported_syscalls, packages_in_api_usage, inst_data, total_pkg_expect, pkg_prob_dict)
    print(f'\nImplemented/Stubbed syscalls: {num_implemented_syscalls}/{num_stubbed_syscalls}')
    print('Weighted Completeness = %.3lf %%' % wc)

    importance_list = []
    for syscall in total_syscalls:
        probability_not_used = 1
        for pkg in packages_in_api_usage:
            if pkg not in inst_data:
                continue
            if syscall in packages_in_api_usage[pkg]['system call']:
                probability_not_used *= (1- pkg_prob_dict[pkg])
        api_importance = 1 - probability_not_used
        importance_list.append((syscall, api_importance))

    sorted_importance_list = sorted(importance_list, key=lambda x: x[1], reverse=True)
    calculate_curve(sorted_importance_list, args.top, supported_syscalls, api_required_package)

if __name__ == "__main__":
    main()
