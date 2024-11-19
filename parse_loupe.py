import os
import csv
import requests
import json

def get_syscall_map_x86_64():
    url = "https://raw.githubusercontent.com/torvalds/linux/v6.7/arch/x86/entry/syscalls/syscall_64.tbl"
    syscall_map_x86_64 = {}
    
    response = requests.get(url)
    if response.status_code == 200:
        for line in response.text.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0].isdigit():
                syscall_number = int(parts[0])
                syscall_name = parts[2]
                syscall_map_x86_64[syscall_number] = syscall_name
    
    return syscall_map_x86_64


def read_dyn_csv_files(root_directory):
    data_dict = {}

    # Walk through all folders and subfolders in the root directory
    for subdir, _, files in os.walk(root_directory):
        if os.path.basename(subdir) == "data":
            for file in files:
                if file == "dyn.csv":
                    file_path = os.path.join(subdir, file)
                    print(f"Reading file: {file_path}")
                    # Extract the 2-level subfolder name
                    subfolder_name1 = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(subdir))))
                    subfolder_name = subfolder_name1 + '-' + os.path.basename(os.path.dirname(os.path.dirname(subdir)))

                    # Open and read the CSV file, collect translated syscall names
                    with open(file_path, mode='r') as csv_file:
                        csv_reader = csv.reader(csv_file)
                        headers = next(csv_reader)  # Read header row
                        syscall_names = []
                        fake_syscall_names = []
                        for row in csv_reader:
                            # columns = {'works faked', 'works stubbed', 'works both'}
                            # Skip rows where the second value is 'N'
                            if len(row) > 1 and row[1].strip() == 'N':
                                continue
                            # Skip rows where the 4th value is 'Y', which means can be stubbed
                            elif len(row) > 1 and (row[2].strip() == 'Y' or row[4].strip() == 'Y'):
                                continue
                            # Translate syscall number in row[0] if it exists
                            syscall_number = int(row[0])
                            syscall_name = syscall_map_x86_64.get(syscall_number, f"unknown({syscall_number})")
                            if row[3].strip() == 'Y':
                                fake_syscall_names.append(syscall_name)
                            syscall_names.append(syscall_name)
                        
                        # Add data to dictionary
                        syscall_dict = {}
                        syscall_dict["system call"] = syscall_names
                        syscall_dict["works faked"] = fake_syscall_names
                        data_dict[subfolder_name] = syscall_dict
    
    return data_dict

def save_to_json(data, filename="data/application_api_usage.json"):
    with open(filename, 'w') as json_file:
        json.dump(data, json_file, indent=4)
    print(f"Data saved to {filename}")

syscall_map_x86_64 = get_syscall_map_x86_64()

# Usage
root_directory = "../loupedb"  # Change to your actual Loupedb repository path
data = read_dyn_csv_files(root_directory)
save_to_json(data)
