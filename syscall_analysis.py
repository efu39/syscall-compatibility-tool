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
    parser.add_argument('--type', type=str, help="static of dynamic", default="static")
    return parser.parse_args()

def load_implemented_syscalls(implement_syscalls_source):
    """Load supported syscalls from the Gramine syscall table file."""
    supported_syscalls = []

    if "libos_table.c" in implement_syscalls_source:
        print(f'Analyzing Gramine from {implement_syscalls_source} ...')
        data = urllib.request.urlopen(implement_syscalls_source)
        for line in data:
            match = re.search(LIBOS_SYSCALL_PATTERN + r'(.+)', line.decode('utf-8'))
            if match:
                supported_syscalls.append(match.group(1).replace(',', '').strip())
    else:
        print(f'Analyzing against file {implement_syscalls_source} ...')
        with open(implement_syscalls_source, 'r') as f:
            supported_syscalls = [line.strip() for line in f if line.strip()]
    if not supported_syscalls:
        print("No supported syscalls found, check 'libos_table.c' path.")
        exit()
    return supported_syscalls

def load_excluded_syscalls(filepath):
    """Load syscalls to be excluded from a file."""
    with open(filepath, 'r') as file:
        return [line.strip() for line in file if line.strip()]

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

def create_dummy_unweighted_pop(applications_dict):
    inst_data = {}
    for key in applications_dict.keys():
        inst_data[key] = 1
    return inst_data, len(applications_dict)

def filter_packages_by_syscall(syscall, packages_in_api_usage, source, maintainers=None):
    """Filter and print packages requiring a specific syscall."""
    popcon_packages = get_package_popularity.get_package_popularity(source)
    num_packages_require_the_syscall = 0
    for item in popcon_packages:
        pkg = item['package_name']
        if pkg in packages_in_api_usage:
            if (not maintainers or item['maintainer'] in maintainers) and \
                  syscall in packages_in_api_usage[pkg]['system call']:
                print(f'{pkg}')
                num_packages_require_the_syscall += 1
    print(f'Number of packages requiring {syscall}: {num_packages_require_the_syscall}')

def filter_apps_by_syscall(syscall, packages_in_api_usage):
    """Filter and print application requiring a specific syscall."""
    works_faked_apps = []
    used_apps = []
    for pkg in packages_in_api_usage:
        if syscall in packages_in_api_usage[pkg]['works faked']:
            works_faked_apps.append(pkg)
        elif syscall in packages_in_api_usage[pkg]['system call']:
            used_apps.append(pkg)
    print(f"Number of application requiring '{syscall}': {len(works_faked_apps)+len(used_apps)}")
    if len(works_faked_apps):
        print(f'Faked works in wrks:\n {works_faked_apps}')
    if len(used_apps):
        print(f'Required by wrks:\n {used_apps}')
    

def calculate_completeness_score(supported_syscalls, packages_in_api_usage, inst_data, total_pkg_expect, pkg_prob_dict):
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

def rank_syscall_api_importance(packages_in_api_usage, pkg_prob_dict, total_syscalls, inst_data):
    """Calculate and rank syscall importance."""
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
    return sorted(importance_list, key=lambda x: x[1], reverse=True)

def print_unimplemented_syscall(ordered_syscalls, type, top_number, supported_syscalls, api_required_package, api_faked_work_packages):
    """Print unimplemented syscalls"""
    if type == "dynamic":
        unit = 'wrks'
    else:
        unit = 'package'
    top_syscalls = []
    not_supported_count = 0
    print(f'\nTop {top_number} not yet supported syscalls ordered by (API Importance)')
    for s in ordered_syscalls:
        top_syscalls.append(s[0])
        if s[0] not in supported_syscalls:
            if not_supported_count >= top_number:
                break
            not_supported_count += 1
            faked_part_str = ""
            if type == "dynamic":
                faked_part_str = ", works faked in {} {}".format(len(api_faked_work_packages[s[0]]),unit)
            print("{:<18} used in {:>2} {}{}".format(s[0], len(api_required_package[s[0]]),unit, faked_part_str))
            #print("{:<18} ({:.5f}) used in {} {}{}".format(s[0], s[1], len(api_required_package[s[0]]),unit, faked_part_str)) # with API importance value

def main():
    args = parse_arguments()
    # load api_usage data
    if args.type == "static":
        packages_in_api_usage = load_api_usage()
        inst_data, total_inst, effective_total_inst = load_popularity_data(args.source, args.maintainers)
    else:
        packages_in_api_usage = load_api_usage('data/application_api_usage.json')
        inst_data, total_inst = create_dummy_unweighted_pop(packages_in_api_usage)

    # generate pkg_prob_dict and api_required_package for later use
    pkg_prob_dict, total_pkg_expect = {}, 0.0
    api_required_package = defaultdict(list)
    api_faked_work_packages = defaultdict(list)
    for pkg in packages_in_api_usage:
        if pkg in inst_data:
            pkg_prob = inst_data[pkg] / total_inst
            pkg_prob_dict[pkg] = pkg_prob
            total_pkg_expect += pkg_prob
            for api_name in packages_in_api_usage[pkg]['system call']:
                api_required_package[api_name].append(pkg)
            if args.type != "static":
                for api_name in packages_in_api_usage[pkg]['works faked']:
                    api_faked_work_packages[api_name].append(pkg)

    if args.syscall:
        # list packages/apps using the specified syscall
        if args.type == "static":
            filter_packages_by_syscall(args.syscall, packages_in_api_usage, args.source, args.maintainers)
        else:
            filter_apps_by_syscall(args.syscall, packages_in_api_usage)
        return
    
    # load implemented system calls from default URL or args -i
    implemented_syscalls_source = args.implement_syscalls if args.implement_syscalls else LIBOS_URL
    supported_syscalls = list(set(load_implemented_syscalls(implemented_syscalls_source)))
    num_implemented_syscalls = len(supported_syscalls)

    # load stubbed system calls that treated as dont-care
    num_stubbed_syscalls = 0
    if args.stub_syscalls:
        stubbed_syscalls = load_excluded_syscalls(args.stub_syscalls)
        supported_syscalls = list(set(supported_syscalls + stubbed_syscalls))
        num_stubbed_syscalls = len(supported_syscalls) - num_implemented_syscalls

    # calculate complete score
    wc, total_syscalls, not_supported_syscalls, _ = calculate_completeness_score(
        supported_syscalls, packages_in_api_usage, inst_data, total_pkg_expect, pkg_prob_dict)
    print(f'\nImplemented/Stubbed syscalls: {num_implemented_syscalls}/{num_stubbed_syscalls}')
    print('Weighted Completeness = %.3lf %%' % wc)

    # analyze api importance
    sorted_apis = rank_syscall_api_importance(packages_in_api_usage, pkg_prob_dict, total_syscalls, inst_data)
    print_unimplemented_syscall(sorted_apis, args.type, args.top, supported_syscalls, api_required_package, api_faked_work_packages)

if __name__ == "__main__":
    main()
